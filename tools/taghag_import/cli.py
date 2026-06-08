from __future__ import annotations

import argparse
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any
import uuid

from .audio_probe import probe_mp3
from .analysis_import import build_analysis_import_records
from .config import read_database_config
from .db_client import TaghagDbClient
from .discover import discover_audio_files
from .genre import classify_genre
from .postman_evidence import evidence_lookup_key, evidence_to_row, parse_postman_evidence
from .receipt import append_receipt, event, receipt_path_for_run, read_receipt, write_receipt
from .tags import compute_file_identity, extract_mp3_tags
from .stage import execute_stage, plan_stage
from .transcode import build_transcode_plan, execute_transcode_plan


MISSING_TAG_ISSUES = {
    "artist": "missing_artist",
    "title": "missing_title",
    "bpm": "missing_bpm",
    "musical_key": "missing_key",
    "label": "missing_label",
    "isrc": "missing_isrc",
}

DEFAULT_MP3_OUTPUT_ROOT = "/Volumes/LOSSY/taghag"


def _default_mp3_output_root() -> str:
    return os.environ.get("TAGHAG_MP3_OUTPUT_ROOT") or DEFAULT_MP3_OUTPUT_ROOT


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _metadata_issue_codes(tags: dict[str, Any], canonical: dict[str, object]) -> list[str]:
    issues = [issue for field, issue in MISSING_TAG_ISSUES.items() if not tags.get(field)]
    if not tags.get("genre") and not canonical.get("canonical_genre"):
        issues.append("missing_genre")
    if not tags.get("subgenre") and not canonical.get("canonical_subgenre"):
        issues.append("missing_subgenre")
    return issues


def _build_import_batch_records(
    root: str,
    *,
    run_name: str | None = None,
    postman_evidence: str | None = None,
    unsafe_title_artist_evidence_match: bool = False,
) -> list[dict[str, object]]:
    root_path = Path(root).expanduser().resolve()
    found, skipped = discover_audio_files(root_path)
    run_id = str(uuid.uuid4())
    started_at = _now()
    records: list[dict[str, object]] = [
        event(
            "import_run_start",
            run_id=run_id,
            import_run={
                "id": run_id,
                "run_name": run_name,
                "source_root": str(root_path),
                "status": "running",
                "started_at": started_at,
                "tool_versions_json": {"taghag_import": "0.1.0"},
                "summary_json": {},
            },
        )
    ]

    file_keys_by_isrc: dict[str, str] = {}
    file_keys_by_title_artist: dict[tuple[str, str], str] = {}
    observed_count = 0
    issue_counts: dict[str, int] = {}

    for item in found:
        tags = extract_mp3_tags(item.path)
        identity = compute_file_identity(item.path, item.relative_path)
        probe = probe_mp3(item.path)
        canonical = classify_genre(tags.get("genre") or tags.get("subgenre"))
        issue_codes = sorted(
            set(
                list(identity.get("issue_codes", []))
                + list(probe.get("issue_codes", []))
                + _metadata_issue_codes(tags, canonical)
            )
        )
        for issue_code in issue_codes:
            issue_counts[issue_code] = issue_counts.get(issue_code, 0) + 1

        file_key = str(identity["file_key"])
        if tags.get("isrc"):
            file_keys_by_isrc[str(tags["isrc"]).strip().upper()] = file_key
        if tags.get("title") and tags.get("artist"):
            file_keys_by_title_artist[(str(tags["title"]).casefold(), str(tags["artist"]).casefold())] = file_key

        mp3_file = {
            "file_key": file_key,
            "path": item.path,
            "filename": Path(item.path).name,
            "size_bytes": identity["size_bytes"],
            "mtime_ns": identity["mtime_ns"],
            "duration_s": probe["duration_s"],
            "bitrate_kbps": probe["bitrate_kbps"],
            "codec": "mp3",
            "checksum_sha256": identity["checksum_sha256"],
            "checksum_prefix": identity["checksum_prefix"],
            "identity_source": identity["identity_source"],
            "identity_confidence": identity["identity_confidence"],
            "last_seen_at": started_at,
        }
        dj_tag = {
            "artist": tags.get("artist"),
            "title": tags.get("title"),
            "album": tags.get("album"),
            "label": tags.get("label"),
            "catalog_number": tags.get("catalog_number"),
            "release_date": tags.get("release_date"),
            "year": int(str(tags["year"])[:4]) if str(tags.get("year") or "")[:4].isdigit() else None,
            "bpm": float(tags["bpm"]) if str(tags.get("bpm") or "").replace(".", "", 1).isdigit() else None,
            "musical_key": tags.get("musical_key"),
            "canonical_genre": canonical.get("canonical_genre"),
            "canonical_subgenre": canonical.get("canonical_subgenre"),
            "isrc": tags.get("isrc"),
            "compilation": tags.get("compilation"),
            "rating": tags.get("rating"),
            "energy": tags.get("energy"),
            "tag_source": "local_id3",
        }
        mp3_observation = {
            "import_run_id": run_id,
            "observed_path": item.path,
            "observed_size_bytes": identity["size_bytes"],
            "observed_mtime_ns": identity["mtime_ns"],
            "observed_checksum_sha256": identity["checksum_sha256"],
            "status": "observed",
            "issue_json": {"issue_codes": issue_codes},
        }
        records.append(
            event(
                "mp3_observed",
                run_id=run_id,
                file_key=file_key,
                path=item.path,
                relative_path=item.relative_path,
                raw_id3=tags.get("raw_id3", {}),
                mp3_file=mp3_file,
                mp3_observation=mp3_observation,
                dj_tag=dj_tag,
            )
        )
        records.append(
            event(
                "quality_check",
                run_id=run_id,
                file_key=file_key,
                quality_check={
                    "import_run_id": run_id,
                    "decode_ok": probe["decode_ok"],
                    "duration_ok": probe["duration_ok"],
                    "bitrate_ok": probe["bitrate_ok"],
                    "missing_tag_flags_json": [
                        issue for issue in issue_codes if issue.startswith("missing_")
                    ],
                    "duplicate_flags_json": [
                        issue for issue in issue_codes if issue.startswith("duplicate_")
                    ],
                    "issue_codes_json": issue_codes,
                    "tool_name": "taghag_import",
                    "tool_version": "0.1.0",
                    "checked_at": _now(),
                },
            )
        )
        observed_count += 1

    for item in skipped:
        issue_counts["out_of_scope_audio"] = issue_counts.get("out_of_scope_audio", 0) + 1
        records.append(event("out_of_scope_audio", run_id=run_id, **item.to_dict()))

    if postman_evidence:
        seen: set[str] = set()
        for evidence in parse_postman_evidence(postman_evidence):
            lookup_key = evidence_lookup_key(evidence).strip().upper()
            file_key = file_keys_by_isrc.get(lookup_key)
            lookup_type = "isrc"
            if not file_key and unsafe_title_artist_evidence_match:
                title = str(evidence.get("title") or evidence.get("canonical_title") or "").casefold()
                artist = str(
                    evidence.get("artist") or evidence.get("canonical_artist_credit") or ""
                ).casefold()
                file_key = file_keys_by_title_artist.get((title, artist))
                lookup_type = "unsafe_title_artist"
                lookup_key = f"{title}|{artist}" if title or artist else lookup_key

            raw_key = repr(evidence)
            row = evidence_to_row(evidence, lookup_type=lookup_type, lookup_key=lookup_key)
            if raw_key in seen:
                row["status"] = "duplicate"
            seen.add(raw_key)
            records.append(event("tag_evidence", run_id=run_id, file_key=file_key, tag_evidence=row))

    records.append(
        event(
            "import_run_summary",
            run_id=run_id,
            summary={
                "mp3_observed": observed_count,
                "out_of_scope_audio": len(skipped),
                "issue_counts": issue_counts,
            },
        )
    )
    return records


def _import_batch(args: argparse.Namespace) -> int:
    records = _build_import_batch_records(
        args.root,
        run_name=args.run_name,
        postman_evidence=args.postman_evidence,
        unsafe_title_artist_evidence_match=args.unsafe_title_artist_evidence_match,
    )
    run_id = str(records[0]["run_id"])
    receipt_path = receipt_path_for_run(args.receipt_dir, run_id)
    write_receipt(receipt_path, records)

    if args.verbose:
        print(f"Wrote receipt before upload: {receipt_path}")

    if args.dry_run or args.no_upload:
        print(f"Wrote receipt to {receipt_path}")
        return 0

    try:
        client = TaghagDbClient(read_database_config())
        result = client.upload_receipt_events(records)
        append_receipt(receipt_path, [event("upload_result", run_id=run_id, status="uploaded", result=result)])
        print(f"Uploaded import run {run_id}; receipt: {receipt_path}")
        return 0
    except Exception as exc:
        append_receipt(
            receipt_path,
            [event("upload_result", run_id=run_id, status="failed", error=str(exc))],
        )
        print(f"Upload failed after receipt was written: {exc}")
        return 1


def _scan(args: argparse.Namespace) -> int:
    records = _build_import_batch_records(args.root, postman_evidence=args.evidence_log)
    write_receipt(args.out, records)
    print(f"Wrote {len(records)} receipt records to {args.out}")
    return 0


def _load(args: argparse.Namespace) -> int:
    config = read_database_config()
    client = TaghagDbClient(config)
    records = read_receipt(args.receipt)
    result = client.upload_receipt_events(records)
    print(f"Uploaded receipt {args.receipt}: {result}")
    return 0


def _import_analysis(args: argparse.Namespace) -> int:
    records = build_analysis_import_records(args.input)
    run_id = str(records[0]["run_id"])
    receipt_path = receipt_path_for_run(args.receipt_dir, run_id)
    write_receipt(receipt_path, records)

    if args.no_upload or args.dry_run:
        print(f"Wrote receipt to {receipt_path}")
        return 0

    try:
        client = TaghagDbClient(read_database_config())
        result = client.upload_analysis_events(records)
        append_receipt(receipt_path, [event("upload_result", run_id=run_id, status="uploaded", result=result)])
        print(f"Uploaded analysis import {run_id}; receipt: {receipt_path}")
        return 0
    except Exception as exc:
        append_receipt(receipt_path, [event("upload_result", run_id=run_id, status="failed", error=str(exc))])
        print(f"Upload failed after receipt was written: {exc}")
        return 1


def _transcode(args: argparse.Namespace) -> int:
    try:
        plan = build_transcode_plan(args.source, args.output)
        result = execute_transcode_plan(plan, dry_run=args.dry_run, verbose=args.verbose)
    except (OSError, ValueError) as exc:
        print(f"Transcode planning failed: {exc}")
        return 1

    print(f"FLACs discovered: {len(plan)}")
    print(f"Planned:          {result['planned']}")
    print(f"Existing:         {result['existing']}")
    print(f"Transcoded:       {result['transcoded']}")
    print(f"Failed:           {result['failed']}")
    print(f"Output:           {Path(args.output).expanduser().resolve()}")
    if args.dry_run:
        print("Dry run: no directories or MP3 files were written.")
    return 1 if result["failed"] else 0


def _stage(args: argparse.Namespace) -> int:
    try:
        plan = plan_stage(args.source, args.output)
        result = execute_stage(plan, dry_run=args.dry_run, verbose=args.verbose)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Stage failed: {exc}")
        return 1
    for label in (
        "discovered",
        "admitted",
        "duplicates_blocked",
        "invalid",
        "planned",
        "existing",
        "transcoded",
        "failed",
    ):
        print(f"{label.replace('_', ' ').title()}: {result[label]}")
    print(f"Output: {Path(args.output).expanduser().resolve()}")
    if args.dry_run:
        print("Dry run: no output files were written.")
    return 1 if result["invalid"] or result["failed"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taghag-import")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_batch = subparsers.add_parser("import-batch", help="Scan local MP3 files and upload metadata")
    import_batch.add_argument("--root", required=True, help="Path to the local MP3 batch root")
    import_batch.add_argument("--run-name", help="Optional human-readable import run name")
    import_batch.add_argument("--dry-run", action="store_true", help="Write receipt only and skip upload")
    import_batch.add_argument("--no-upload", action="store_true", help="Write receipt only and skip upload")
    import_batch.add_argument("--receipt-dir", default="artifacts/import_runs", help="Receipt root directory")
    import_batch.add_argument("--postman-evidence", help="Optional log containing [Tag Evidence JSON] lines")
    import_batch.add_argument(
        "--unsafe-title-artist-evidence-match",
        action="store_true",
        help="Allow experimental title/artist evidence matching when ISRC is missing",
    )
    import_batch.add_argument("--verbose", action="store_true", help="Print extra progress")
    import_batch.set_defaults(func=_import_batch)

    scan = subparsers.add_parser("scan", help="Compatibility wrapper: scan and write a JSONL receipt")
    scan.add_argument("--root", required=True, help="Path to the local music library root")
    scan.add_argument("--out", required=True, help="Path to the JSONL receipt output")
    scan.add_argument("--evidence-log", required=False, help="Optional [Tag Evidence JSON] log")
    scan.set_defaults(func=_scan)

    load = subparsers.add_parser("load", help="Compatibility wrapper: upload a JSONL receipt")
    load.add_argument("--receipt", required=True, help="Path to a JSONL receipt file")
    load.set_defaults(func=_load)

    import_analysis = subparsers.add_parser("import-analysis", help="Import local Essentia metadata sidecar")
    import_analysis.add_argument("--input", required=True, help="Path to essentia-lexicon-sidecar/2 JSON")
    import_analysis.add_argument("--receipt-dir", default="artifacts/analysis_imports", help="Receipt root directory")
    import_analysis.add_argument("--dry-run", action="store_true", help="Write receipt only and skip upload")
    import_analysis.add_argument("--no-upload", action="store_true", help="Write receipt only and skip upload")
    import_analysis.set_defaults(func=_import_analysis)

    transcode = subparsers.add_parser(
        "transcode",
        help="Transcode local FLAC files to mirrored 320 kbps MP3s without database access",
    )
    transcode.add_argument("--source", required=True, help="Source directory containing FLAC files")
    transcode.add_argument(
        "--output",
        default=_default_mp3_output_root(),
        help=f"Destination root for mirrored MP3 files (default: {_default_mp3_output_root()})",
    )
    transcode.add_argument("--dry-run", action="store_true", help="Print counts without writing files")
    verbosity = transcode.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=True,
        help="Print each transcode or existing-file decision (default)",
    )
    verbosity.add_argument(
        "--quiet",
        dest="verbose",
        action="store_false",
        help="Print summary only",
    )
    transcode.set_defaults(func=_transcode)

    stage = subparsers.add_parser(
        "stage",
        help="Validate, deduplicate, transcode, and receipt local FLAC files without database access",
    )
    stage.add_argument("--source", required=True, help="FLAC file or directory")
    stage.add_argument(
        "--output",
        default=_default_mp3_output_root(),
        help=f"Taghag batch output root (default: {_default_mp3_output_root()})",
    )
    stage.add_argument("--dry-run", action="store_true", help="Plan without writing output files")
    stage_verbosity = stage.add_mutually_exclusive_group()
    stage_verbosity.add_argument("--verbose", dest="verbose", action="store_true", default=True)
    stage_verbosity.add_argument("--quiet", dest="verbose", action="store_false")
    stage.set_defaults(func=_stage)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
