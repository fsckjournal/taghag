from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .audio_probe import probe_mp3
from .flac import discover_flacs, extract_flac_tags, pcm_sha256, probe_flac, sha256_file
from .genre import classify_genre
from .receipt import event, write_receipt
from .tags import compute_file_identity, extract_mp3_tags
from .transcode import TranscodeJob, execute_transcode_plan


@dataclass(frozen=True)
class StageItem:
    source: Path
    relative_path: str
    destination: Path
    status: str
    file_sha256: str | None
    pcm_sha256: str | None
    duplicate_of: Path | None
    tags: dict[str, Any]
    probe: dict[str, object]


@dataclass(frozen=True)
class StagePlan:
    source_root: Path
    output_root: Path
    items: list[StageItem]
    metadata_candidates: list[dict[str, str]]


def _normalized(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _relative(source: Path, source_root: Path) -> Path:
    return Path(source.name) if source_root.is_file() else source.relative_to(source_root)


def _existing_pcm_index(output_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    index_path = output_root / "reports" / "fingerprint_index.json"
    if not index_path.is_file():
        return index
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return index
    for fingerprint, path in payload.items():
        if isinstance(fingerprint, str) and isinstance(path, str):
            index[fingerprint] = Path(path).expanduser().resolve()
    return index


def plan_stage(source: str | Path, output: str | Path) -> StagePlan:
    source_root = Path(source).expanduser().resolve()
    output_root = Path(output).expanduser().resolve()
    flacs = discover_flacs(source_root)
    existing_pcm = _existing_pcm_index(output_root)
    keepers: dict[str, Path] = dict(existing_pcm)
    items: list[StageItem] = []

    for path in flacs:
        rel = _relative(path, source_root)
        destination = (output_root / "mp3" / rel).with_suffix(".mp3")
        probe = probe_flac(path)
        tags = extract_flac_tags(path)
        if not probe.get("valid"):
            items.append(StageItem(path, str(rel), destination, "invalid", None, None, None, tags, probe))
            continue
        file_hash = sha256_file(path)
        pcm_hash = pcm_sha256(path)
        duplicate_of = keepers.get(pcm_hash)
        if duplicate_of is not None:
            status = "audio-duplicate-blocked"
        else:
            keepers[pcm_hash] = path
            status = "existing" if destination.is_file() and destination.stat().st_size > 0 else "admitted"
        items.append(StageItem(path, str(rel), destination, status, file_hash, pcm_hash, duplicate_of, tags, probe))

    candidates: list[dict[str, str]] = []
    for field, key_fn in (
        ("isrc", lambda item: _normalized(item.tags.get("isrc"))),
        (
            "artist_title",
            lambda item: f"{_normalized(item.tags.get('artist'))}|{_normalized(item.tags.get('title'))}",
        ),
    ):
        groups: dict[str, list[StageItem]] = {}
        for item in items:
            key = key_fn(item)
            if key and key != "|":
                groups.setdefault(key, []).append(item)
        for key, group in groups.items():
            if len(group) > 1 and len({item.pcm_sha256 for item in group}) > 1:
                for item in group:
                    candidates.append({"type": field, "key": key, "path": str(item.source)})
    return StagePlan(source_root, output_root, items, candidates)


def execute_stage(plan: StagePlan, *, dry_run: bool = False, verbose: bool = True) -> dict[str, int]:
    jobs = [
        TranscodeJob(item.source, item.destination, "existing" if item.status == "existing" else "ready")
        for item in plan.items
        if item.status in {"admitted", "existing"}
    ]
    transcode_result = execute_transcode_plan(jobs, dry_run=dry_run, verbose=verbose)
    summary = {
        "discovered": len(plan.items),
        "admitted": sum(item.status in {"admitted", "existing"} for item in plan.items),
        "duplicates_blocked": sum(item.status == "audio-duplicate-blocked" for item in plan.items),
        "invalid": sum(item.status == "invalid" for item in plan.items),
        **transcode_result,
    }
    if dry_run:
        return summary

    reports = plan.output_root / "reports"
    receipts = plan.output_root / "receipts"
    reports.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)

    with (reports / "audio_duplicates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "duplicate_of", "pcm_sha256"])
        writer.writeheader()
        for item in plan.items:
            if item.status == "audio-duplicate-blocked":
                writer.writerow(
                    {
                        "path": str(item.source),
                        "duplicate_of": str(item.duplicate_of),
                        "pcm_sha256": item.pcm_sha256,
                    }
                )
    with (reports / "metadata_candidates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["type", "key", "path"])
        writer.writeheader()
        writer.writerows(plan.metadata_candidates)

    records: list[dict[str, object]] = [
        event("stage_start", source=str(plan.source_root), output=str(plan.output_root), started_at=datetime.now(UTC).isoformat())
    ]
    validated_fingerprints: dict[str, Path] = {}
    for item in plan.items:
        row = asdict(item)
        row["source"] = str(item.source)
        row["destination"] = str(item.destination)
        row["duplicate_of"] = str(item.duplicate_of) if item.duplicate_of else None
        if item.status in {"admitted", "existing"} and item.destination.is_file():
            mp3_probe = probe_mp3(item.destination)
            row["mp3_probe"] = mp3_probe
            valid_mp3 = (
                mp3_probe.get("codec") == "mp3"
                and mp3_probe.get("decode_ok") is True
                and mp3_probe.get("duration_ok") is True
                and mp3_probe.get("bitrate_ok") is True
            )
            row["admitted_to_receipt"] = valid_mp3
            if valid_mp3 and item.pcm_sha256:
                mp3_tags = extract_mp3_tags(item.destination)
                row["mp3_file"] = compute_file_identity(item.destination, item.relative_path)
                row["mp3_tags"] = mp3_tags
                row["canonical_genre"] = classify_genre(
                    mp3_tags.get("genre") or mp3_tags.get("subgenre")
                )
                validated_fingerprints[item.pcm_sha256] = item.destination
            elif not valid_mp3:
                summary["failed"] += 1
        records.append(event("stage_file", **row))
    records.append(event("stage_summary", summary=summary))
    write_receipt(receipts / "stage.jsonl", records)
    (reports / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fingerprint_index = _existing_pcm_index(plan.output_root)
    fingerprint_index.update(validated_fingerprints)
    (reports / "fingerprint_index.json").write_text(
        json.dumps(
            {fingerprint: str(path) for fingerprint, path in sorted(fingerprint_index.items())},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary
