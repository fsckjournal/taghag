from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
import uuid

from .audio_probe import probe_mp3
from .config import read_database_config
from .db_client import TaghagDbClient
from .discover import discover_audio_files
from .genre import classify_genre
from .postman_evidence import parse_postman_evidence
from .receipt import read_receipt, write_receipt
from .tags import extract_mp3_tags


def _build_scan_records(root: str, evidence_log: str | None = None) -> list[dict[str, object]]:
    found, skipped = discover_audio_files(root)
    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC).isoformat()

    records: list[dict[str, object]] = [
        {
            "record_type": "import_run",
            "import_run": {
                "id": run_id,
                "source_root": str(Path(root).expanduser().resolve()),
                "started_at": started_at,
                "status": "scanned",
            },
        }
    ]

    evidence_entries = parse_postman_evidence(evidence_log) if evidence_log else []
    for item in found:
        tag_data = extract_mp3_tags(item.path)
        probe_data = probe_mp3(item.path)
        genre_data = classify_genre(tag_data.get("genre"))
        records.append(
            {
                "record_type": "mp3_track",
                "import_run_id": run_id,
                "path": item.path,
                "relative_path": item.relative_path,
                "track": {
                    **tag_data,
                    **probe_data,
                    **genre_data,
                    "source_path": item.path,
                    "source_root": str(Path(root).expanduser().resolve()),
                },
            }
        )

    for item in skipped:
        records.append(
            {
                "record_type": "skipped_path",
                "import_run_id": run_id,
                **item.to_dict(),
            }
        )

    for entry in evidence_entries:
        records.append(
            {
                "record_type": "tag_evidence",
                "import_run_id": run_id,
                "evidence": entry,
            }
        )

    return records


def _scan(args: argparse.Namespace) -> int:
    records = _build_scan_records(args.root, args.evidence_log)
    write_receipt(args.out, records)
    print(f"Wrote {len(records)} receipt records to {args.out}")
    return 0


def _materialize_rows(records: Iterable[dict[str, object]], actor_id: str | None) -> tuple[dict[str, object], list[dict[str, object]]]:
    import_run_row: dict[str, object] | None = None
    track_rows: list[dict[str, object]] = []

    for record in records:
        if record["record_type"] == "import_run":
            payload = dict(record["import_run"])
            payload["started_by_user_id"] = actor_id
            import_run_row = payload
        elif record["record_type"] == "mp3_track":
            track = dict(record["track"])
            owner_user_id = actor_id or "00000000-0000-0000-0000-000000000001"
            track_rows.append(
                {
                    "owner_user_id": owner_user_id,
                    "import_run_id": record["import_run_id"],
                    "library_fingerprint": track["library_fingerprint"],
                    "file_name": track["file_name"],
                    "source_root": track["source_root"],
                    "relative_path_hint": record["relative_path"],
                    "file_size_bytes": track["file_size_bytes"],
                    "duration_seconds": track["duration_seconds"],
                    "bit_rate": track["bit_rate"],
                    "title": track["title"],
                    "artist": track["artist"],
                    "album": track["album"],
                    "raw_genre": track["genre"],
                    "normalized_genre": track["normalized_genre"],
                    "genre_family": track["genre_family"],
                    "bpm": track["bpm"],
                    "musical_key": track["musical_key"],
                    "release_year": track["year"],
                    "track_number": track["track_number"],
                    "composer": track["composer"],
                    "comment": track["comment"],
                    "decode_ok": track["decode_ok"],
                    "probe_ok": track["probe_ok"],
                    "raw_id3": track["raw_id3"],
                    "last_seen_at": datetime.now(UTC).isoformat(),
                }
            )

    if import_run_row is None:
        raise RuntimeError("receipt is missing import_run record")

    return import_run_row, track_rows


def _load(args: argparse.Namespace) -> int:
    config = read_database_config()
    client = TaghagDbClient(config)
    records = read_receipt(args.receipt)
    import_run_row, track_rows = _materialize_rows(records, config.actor_id)
    client.upsert_import_run(import_run_row)
    client.upsert_tracks(track_rows)
    print(f"Loaded 1 import run and {len(track_rows)} MP3 track records from {args.receipt}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taghag-import")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan a root directory for MP3 files")
    scan.add_argument("--root", required=True, help="Path to the local music library root")
    scan.add_argument("--out", required=True, help="Path to the JSONL receipt output")
    scan.add_argument(
        "--evidence-log",
        required=False,
        help="Optional text log containing [Tag Evidence JSON] marker lines",
    )
    scan.set_defaults(func=_scan)

    load = subparsers.add_parser("load", help="Load a JSONL receipt into the database")
    load.add_argument("--receipt", required=True, help="Path to a JSONL receipt file")
    load.set_defaults(func=_load)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
