from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
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
from .audio_audit import metadata_issue_codes, run_audio_audit
from .postman_evidence import evidence_lookup_key, evidence_to_row, parse_postman_evidence
from .extract_dj_slice import extract_dj_slice
from .provider_runner import (
    ProviderRunnerConfig,
    build_postman_command,
    display_command,
    run_provider_batch,
    verify_provider_config,
)
from .flac import extract_flac_tags
from .receipt import append_receipt, event, receipt_path_for_run, read_receipt, write_receipt
from .tags import (
    apply_mp3_tag_updates,
    compute_file_identity,
    dump_mp3_tags,
    extract_mp3_tags,
)
from .stage import execute_stage, plan_stage, plan_stage_manifest
from .transcode import build_transcode_plan, execute_transcode_plan


DEFAULT_MP3_OUTPUT_ROOT = "/Volumes/LOSSY/taghag"


def _extract_tags(path: str | Path) -> dict[str, Any]:
    """Dispatch to the right tag reader based on file extension."""
    if Path(path).suffix.lower() == ".flac":
        tags = extract_flac_tags(path)
        # Normalize: add fields expected by the pipeline that flac.py doesn't set
        tags.setdefault("year", None)
        tags.setdefault("rating", None)
        tags.setdefault("energy", None)
        tags.setdefault("composer", None)
        tags.setdefault("raw_id3", {})
        return tags
    return extract_mp3_tags(path)


def _default_mp3_output_root() -> str:
    return os.environ.get("TAGHAG_MP3_OUTPUT_ROOT") or DEFAULT_MP3_OUTPUT_ROOT


def _now() -> str:
    return datetime.now(UTC).isoformat()


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
        tags = _extract_tags(item.path)
        identity = compute_file_identity(item.path, item.relative_path)
        probe = probe_mp3(item.path)
        canonical = classify_genre(tags.get("genre") or tags.get("subgenre"))
        issue_codes = sorted(
            set(
                list(identity.get("issue_codes", []))
                + list(probe.get("issue_codes", []))
                + metadata_issue_codes(tags, canonical)
            )
        )
        for issue_code in issue_codes:
            issue_counts[issue_code] = issue_counts.get(issue_code, 0) + 1

        file_key = str(identity["file_key"])
        if tags.get("isrc"):
            file_keys_by_isrc[str(tags["isrc"]).strip().upper()] = file_key
        if tags.get("title") and tags.get("artist"):
            file_keys_by_title_artist[(str(tags["title"]).casefold(), str(tags["artist"]).casefold())] = file_key

        audio_file = {
            "file_key": file_key,
            "path": item.path,
            "filename": Path(item.path).name,
            "size_bytes": identity["size_bytes"],
            "mtime_ns": identity["mtime_ns"],
            "duration_s": probe["duration_s"],
            "bitrate_kbps": probe["bitrate_kbps"],
            "codec": "flac" if Path(item.path).suffix.lower() == ".flac" else "mp3",
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
            "release_date": (tags.get("release_date") + "-01-01" if len(str(tags.get("release_date") or "")) == 4 else (tags.get("release_date") + "-01" if len(str(tags.get("release_date") or "")) == 7 else tags.get("release_date"))) if tags.get("release_date") else None,
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
        audio_observation = {
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
                "audio_observed",
                run_id=run_id,
                file_key=file_key,
                path=item.path,
                relative_path=item.relative_path,
                raw_id3=tags.get("raw_id3", {}),
                audio_file=audio_file,
                audio_observation=audio_observation,
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
                "audio_observed": observed_count,
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
    output_root = Path(args.output).expanduser().resolve()
    failure_ledger = output_root / "reports" / "transcode_failures.jsonl"
    state_file = output_root / "reports" / "transcode_state.json"
    
    try:
        plan = build_transcode_plan(args.source, args.output, failure_ledger_path=failure_ledger)
        result = execute_transcode_plan(
            plan, 
            dry_run=args.dry_run, 
            verbose=args.verbose, 
            workers=args.workers,
            state_file_path=state_file,
            failure_ledger_path=failure_ledger,
        )
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
    output_root = Path(args.output).expanduser().resolve()
    failure_ledger = output_root / "reports" / "transcode_failures.jsonl"
    state_file = output_root / "reports" / "transcode_state.json"
    try:
        if args.manifest:
            plan = plan_stage_manifest(args.manifest, args.output, failure_ledger_path=failure_ledger)
        else:
            plan = plan_stage(args.source, args.output, failure_ledger_path=failure_ledger)
        result = execute_stage(
            plan, 
            dry_run=args.dry_run, 
            verbose=args.verbose,
            workers=args.workers,
            state_file_path=state_file,
            failure_ledger_path=failure_ledger,
        )
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


def _audit_mp3(args: argparse.Namespace) -> int:
    try:
        result = run_audio_audit(args.root, args.output_dir)
    except (OSError, ValueError) as exc:
        print(f"MP3 audit failed: {exc}")
        return 1

    print(f"MP3 files:    {result.summary['audio_files']}")
    print(f"Skipped:      {result.summary['skipped_files']}")
    print(f"JSONL report: {result.jsonl_path}")
    print(f"CSV report:   {result.csv_path}")
    print(f"Summary:      {result.summary_path}")
    return 0


def _explicit_mp3_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".mp3":
        raise ValueError(f"not an MP3 file: {path}")
    return path


def _dump_input_paths(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    if args.root:
        found, _skipped = discover_audio_files(args.root)
        paths.extend(Path(item.path) for item in found)
    elif args.paths:
        paths.extend(_explicit_mp3_path(value) for value in args.paths)
    elif args.paths_file:
        paths_file = Path(args.paths_file).expanduser().resolve()
        for line in paths_file.read_text(encoding="utf-8-sig").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                paths.append(_explicit_mp3_path(value))

    unique = {str(path.resolve()): path.resolve() for path in paths}
    return [unique[key] for key in sorted(unique)]


def _dump_tags(args: argparse.Namespace) -> int:
    try:
        paths = _dump_input_paths(args)
        output = Path(args.out).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for path in paths:
                record = {"path": str(path), "tags": dump_mp3_tags(path)}
                handle.write(json.dumps(record, sort_keys=True) + "\n")
    except (OSError, ValueError) as exc:
        print(f"Tag dump failed: {exc}")
        return 1

    print(f"Wrote {len(paths)} MP3 tag record(s) to {output}")
    return 0


def _load_write_plan(path: str | Path) -> dict[Path, dict[str, str]]:
    plan_path = Path(path).expanduser().resolve()
    grouped: dict[Path, dict[str, str]] = {}
    with plan_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"path", "field", "value"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("write plan must contain path,field,value columns")
        for row_number, row in enumerate(reader, start=2):
            raw_path = str(row.get("path") or "").strip()
            field = str(row.get("field") or "").strip()
            value = str(row.get("value") or "").strip()
            if not raw_path or not field:
                raise ValueError(f"invalid write plan row {row_number}")
            file_path = _explicit_mp3_path(raw_path)
            grouped.setdefault(file_path, {})[field] = value
    return grouped


def _write_tags(args: argparse.Namespace) -> int:
    try:
        plan = _load_write_plan(args.plan)
        results = [
            apply_mp3_tag_updates(
                path,
                updates,
                execute=args.execute,
                force=args.force,
            )
            for path, updates in sorted(plan.items(), key=lambda item: str(item[0]))
        ]
    except (OSError, ValueError) as exc:
        print(f"Tag write failed: {exc}")
        return 1

    planned = sum(len(result.planned_fields) for result in results)
    applied = sum(len(result.applied_fields) for result in results)
    skipped = sum(len(result.skipped_fields) for result in results)
    print(f"Files:   {len(results)}")
    print(f"Planned: {planned}")
    print(f"Applied: {applied}")
    print(f"Skipped: {skipped}")
    print(f"Mode:    {'execute' if args.execute else 'dry-run'}")
    return 0


def _collect_isrc_values(args: argparse.Namespace) -> list[str]:
    values = list(args.isrcs or [])
    if args.isrc_file:
        source = Path(args.isrc_file).expanduser().resolve()
        if source.suffix.lower() == ".csv":
            with source.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    value = row.get("isrc") or row.get("lookup_isrc")
                    if value:
                        values.append(str(value))
        elif source.suffix.lower() in {".jsonl", ".json"}:
            text = source.read_text(encoding="utf-8")
            payloads = (
                [json.loads(line) for line in text.splitlines() if line.strip()]
                if source.suffix.lower() == ".jsonl"
                else [json.loads(text)]
            )
            for payload in payloads:
                if not isinstance(payload, dict):
                    continue
                for candidate in (
                    payload.get("isrc"),
                    payload.get("lookup_isrc"),
                    (payload.get("dj_tag") or {}).get("isrc")
                    if isinstance(payload.get("dj_tag"), dict)
                    else None,
                ):
                    if candidate:
                        values.append(str(candidate))
                        break
        else:
            for line in source.read_text(encoding="utf-8-sig").splitlines():
                value = line.strip()
                if value and not value.startswith("#"):
                    values.append(value)
    if not values:
        raise ValueError("provide --isrc or --isrc-file")
    return values


def _provider_evidence(args: argparse.Namespace) -> int:
    collection = args.collection or os.environ.get("TAGHAG_POSTMAN_COLLECTION")
    environment = args.environment or os.environ.get("TAGHAG_POSTMAN_ENVIRONMENT")
    if not collection or not environment:
        print(
            "Provider evidence failed: provide --collection and --environment "
            "or set TAGHAG_POSTMAN_COLLECTION and TAGHAG_POSTMAN_ENVIRONMENT"
        )
        return 1

    output_dir = args.output_dir or (
        Path("artifacts") / "provider_evidence" / datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    )
    config = ProviderRunnerConfig(
        postman_bin=args.postman_bin,
        collection_path=Path(collection),
        environment_path=Path(environment),
        output_dir=Path(output_dir),
        timeout_s=args.timeout,
        prepare_only=args.prepare_only,
    )
    try:
        isrcs = _collect_isrc_values(args)
        verify_provider_config(config)
        for isrc in isrcs:
            command = build_postman_command(isrc, config)
            print(f"Verified command: {display_command(command, config.secret_keys)}")
        result = run_provider_batch(isrcs, config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Provider evidence failed: {exc}")
        return 1

    print(f"Evidence log: {result.evidence_log}")
    print(f"Summary:      {result.summary_path}")
    print(f"Succeeded:    {result.summary['succeeded']}")
    print(f"Failed:       {result.summary['failed']}")
    print(f"Prepared:     {result.summary['prepared']}")
    return 1 if result.summary["failed"] else 0


def _extract_dj_slice_command(args: argparse.Namespace) -> int:
    try:
        summary = extract_dj_slice(args.sqlite_db)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"DJ slice backfill failed: {exc}")
        return 1

    if args.verbose:
        print(
            "read={read} eligible={eligible} inserted_audio_file={audio} inserted_dj_tag={tag} "
            "skipped={skipped} skipped_missing_identity={missing} skipped_file_key_conflicts={conflicts}".format(
                read=summary.source_rows,
                eligible=summary.eligible_rows,
                audio=summary.inserted_audio_files,
                tag=summary.inserted_dj_tags,
                skipped=summary.skipped_rows,
                missing=summary.skipped_missing_identity,
                conflicts=summary.skipped_file_key_conflicts,
            )
        )
    else:
        print(
            f"read={summary.source_rows} inserted={summary.inserted_audio_files} skipped={summary.skipped_rows}"
        )
    return 0


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
    transcode.add_argument("--workers", type=int, help="Number of concurrent transcode workers (default: min(cpu_count, 8))")
    transcode.set_defaults(func=_transcode)

    stage = subparsers.add_parser(
        "stage",
        help="Validate, deduplicate, transcode, and receipt local FLAC files without database access",
    )
    stage_input = stage.add_mutually_exclusive_group(required=True)
    stage_input.add_argument("--source", help="FLAC file or directory")
    stage_input.add_argument("--manifest", help="JSONL allowlist of absolute FLAC source paths")
    stage.add_argument(
        "--output",
        default=_default_mp3_output_root(),
        help=f"Taghag batch output root (default: {_default_mp3_output_root()})",
    )
    stage.add_argument("--dry-run", action="store_true", help="Plan without writing output files")
    stage_verbosity = stage.add_mutually_exclusive_group()
    stage_verbosity.add_argument("--verbose", dest="verbose", action="store_true", default=True)
    stage_verbosity.add_argument("--quiet", dest="verbose", action="store_false")
    stage.add_argument("--workers", type=int, help="Number of concurrent transcode workers (default: min(cpu_count, 8))")
    stage.set_defaults(func=_stage)

    audit_mp3 = subparsers.add_parser(
        "audit-mp3",
        help="Audit a local MP3 tree and write metadata-only reports",
    )
    audit_mp3.add_argument("--root", required=True, help="Local MP3 root to audit")
    audit_mp3.add_argument(
        "--output-dir",
        help="Report directory (default: artifacts/audio_audit/<timestamp>)",
    )
    audit_mp3.set_defaults(func=_audit_mp3)

    dump_tags = subparsers.add_parser(
        "dump-tags",
        help="Write a metadata-only JSONL dump of MP3 ID3 frames",
    )
    dump_input = dump_tags.add_mutually_exclusive_group(required=True)
    dump_input.add_argument("--root", help="Discover MP3 files under this root")
    dump_input.add_argument(
        "--path",
        dest="paths",
        action="append",
        help="Explicit MP3 path; repeat for multiple files",
    )
    dump_input.add_argument("--paths-file", help="Text file containing one MP3 path per line")
    dump_tags.add_argument("--out", required=True, help="Output JSONL path")
    dump_tags.set_defaults(func=_dump_tags)

    write_tags = subparsers.add_parser(
        "write-tags",
        help="Apply a path,field,value CSV plan to MP3 ID3 tags",
    )
    write_tags.add_argument("--plan", required=True, help="CSV plan with path,field,value columns")
    write_tags.add_argument(
        "--execute",
        action="store_true",
        help="Write ID3 changes; default is dry-run",
    )
    write_tags.add_argument(
        "--force",
        action="store_true",
        help="Overwrite requested non-empty fields",
    )
    write_tags.set_defaults(func=_write_tags)

    provider_evidence = subparsers.add_parser(
        "provider-evidence",
        help="Run exact Postman ISRC lookups and write an importer-compatible evidence log",
    )
    provider_evidence.add_argument(
        "--isrc",
        dest="isrcs",
        action="append",
        help="ISRC to resolve; repeat for multiple tracks",
    )
    provider_evidence.add_argument(
        "--isrc-file",
        help="Text, CSV, JSON, or JSONL file containing ISRC values",
    )
    provider_evidence.add_argument(
        "--collection",
        help="Postman collection file/directory (or TAGHAG_POSTMAN_COLLECTION)",
    )
    provider_evidence.add_argument(
        "--environment",
        help="Postman environment file (or TAGHAG_POSTMAN_ENVIRONMENT)",
    )
    provider_evidence.add_argument(
        "--postman-bin",
        default=os.environ.get("TAGHAG_POSTMAN_BIN", "postman"),
        help="Postman CLI executable",
    )
    provider_evidence.add_argument(
        "--output-dir",
        help="Output directory (default: artifacts/provider_evidence/<timestamp>)",
    )
    provider_evidence.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Per-ISRC Postman timeout in seconds",
    )
    provider_evidence.add_argument(
        "--prepare-only",
        action="store_true",
        help="Verify and print commands without running the provider batch",
    )
    provider_evidence.set_defaults(func=_provider_evidence)

    extract_dj_slice_parser = subparsers.add_parser(
        "extract-dj-slice",
        help="Backfill the legacy DJ slice from music_v3.db into audio_file and dj_tag",
    )
    extract_dj_slice_parser.add_argument(
        "--sqlite-db",
        required=True,
        help="Path to the legacy music_v3.db SQLite database",
    )
    extract_dj_slice_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a compact summary after completion",
    )
    extract_dj_slice_parser.set_defaults(func=_extract_dj_slice_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
