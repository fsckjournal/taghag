from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .audio_probe import probe_flac
from .discover import DiscoveryRecord, discover_audio_files
from .flac import extract_flac_tags
from .genre import classify_genre
from .provider_runner import normalize_isrc


MISSING_TAG_ISSUES = {
    "artist": "missing_artist",
    "title": "missing_title",
    "bpm": "missing_bpm",
    "musical_key": "missing_key",
    "label": "missing_label",
    "isrc": "missing_isrc",
}

CSV_FIELDS = [
    "path",
    "relative_path",
    "filename",
    "artist",
    "title",
    "album",
    "label",
    "catalog_number",
    "release_date",
    "year",
    "genre",
    "subgenre",
    "canonical_genre",
    "canonical_subgenre",
    "bpm",
    "musical_key",
    "isrc",
    "duration_s",
    "bitrate_kbps",
    "codec",
    "sample_rate_hz",
    "channels",
    "decode_ok",
    "probe_ok",
    "probe_error",
    "decode_error",
    "issue_codes",
]


@dataclass(frozen=True)
class AuditResult:
    output_dir: Path
    jsonl_path: Path
    csv_path: Path
    summary_path: Path
    summary: dict[str, object]


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def default_audit_output_dir() -> Path:
    return Path("artifacts") / "audio_audit" / _timestamp()


def is_malformed_isrc(value: object) -> bool:
    """True when a tag's ISRC value is not exactly one well-formed ISRC.

    Legacy Picard passes sometimes concatenated several historical ISRCs into
    one semicolon-joined tag value. Acquisition-time tagging always yields a
    single valid ISRC, so anything that fails strict normalization is treated
    as untrustworthy rather than salvaged.
    """
    text = str(value or "").strip()
    if not text:
        return False
    try:
        normalize_isrc(text)
    except ValueError:
        return True
    return False


def metadata_issue_codes(
    tags: dict[str, Any],
    canonical: dict[str, object],
) -> list[str]:
    issues = [issue for field, issue in MISSING_TAG_ISSUES.items() if not tags.get(field)]
    if is_malformed_isrc(tags.get("isrc")):
        issues.append("malformed_isrc")
    if not tags.get("genre") and not canonical.get("canonical_genre"):
        issues.append("missing_genre")
    if not tags.get("subgenre") and not canonical.get("canonical_subgenre"):
        issues.append("missing_subgenre")
    return sorted(set(issues))


def _write_jsonl(path: Path, records: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _issue_counts(records: Iterable[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for issue in record.get("issue_codes", []) or []:
            issue_code = str(issue)
            counts[issue_code] = counts.get(issue_code, 0) + 1
    return dict(sorted(counts.items()))


def _audit_record(item: DiscoveryRecord) -> dict[str, object]:
    path = Path(item.path)
    tags = extract_flac_tags(path)
    probe = probe_flac(path)
    canonical = classify_genre(tags.get("genre") or tags.get("subgenre"))
    issue_codes = sorted(
        set(list(probe.get("issue_codes", []) or []) + metadata_issue_codes(tags, canonical))
    )
    return {
        "event_type": "audio_audit",
        "path": item.path,
        "relative_path": item.relative_path,
        "filename": path.name,
        "extension": item.extension,
        "artist": tags.get("artist") or "",
        "title": tags.get("title") or "",
        "album": tags.get("album") or "",
        "label": tags.get("label") or "",
        "catalog_number": tags.get("catalog_number") or "",
        "release_date": tags.get("release_date") or "",
        "year": tags.get("year") or "",
        "genre": tags.get("genre") or "",
        "subgenre": tags.get("subgenre") or "",
        "canonical_genre": canonical.get("canonical_genre") or "",
        "canonical_subgenre": canonical.get("canonical_subgenre") or "",
        "bpm": tags.get("bpm") or "",
        "musical_key": tags.get("musical_key") or "",
        "isrc": tags.get("isrc") or "",
        "track_number": tags.get("track_number") or "",
        "duration_s": probe.get("duration_s"),
        "bitrate_kbps": probe.get("bitrate_kbps"),
        "codec": probe.get("codec"),
        "sample_rate_hz": probe.get("sample_rate_hz"),
        "channels": probe.get("channels"),
        "decode_ok": probe.get("decode_ok"),
        "probe_ok": probe.get("probe_ok"),
        "probe_error": probe.get("probe_error"),
        "decode_error": probe.get("decode_error"),
        "duration_ok": probe.get("duration_ok"),
        "bitrate_ok": probe.get("bitrate_ok"),
        "issue_codes": issue_codes,
        "raw_id3": tags.get("raw_id3", {}),
    }


def _csv_row(record: dict[str, object]) -> dict[str, object]:
    row = {field: record.get(field, "") for field in CSV_FIELDS}
    row["issue_codes"] = ",".join(str(issue) for issue in record.get("issue_codes", []) or [])
    return row


def run_audio_audit(
    root: str | Path,
    output_dir: str | Path | None = None,
) -> AuditResult:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(root_path)
    if not root_path.is_dir():
        raise ValueError(f"FLAC audit root is not a directory: {root_path}")

    resolved_output = (
        Path(output_dir).expanduser().resolve() if output_dir else default_audit_output_dir().resolve()
    )
    resolved_output.mkdir(parents=True, exist_ok=True)

    found, skipped = discover_audio_files(root_path)
    audit_records = [_audit_record(item) for item in found]
    skipped_records = [
        {"event_type": "skipped_input", **item.to_dict()}
        for item in skipped
    ]
    records = [*audit_records, *skipped_records]
    issue_counts = _issue_counts(audit_records)
    summary: dict[str, object] = {
        "root": str(root_path),
        "audio_files": len(audit_records),
        "skipped_files": len(skipped_records),
        "issue_counts": issue_counts,
    }

    jsonl_path = resolved_output / "audio_audit.jsonl"
    csv_path = resolved_output / "audio_audit.csv"
    summary_path = resolved_output / "summary.json"
    _write_jsonl(jsonl_path, records)
    _write_csv(csv_path, [_csv_row(record) for record in audit_records])
    summary_path.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return AuditResult(
        output_dir=resolved_output,
        jsonl_path=jsonl_path,
        csv_path=csv_path,
        summary_path=summary_path,
        summary=summary,
    )
