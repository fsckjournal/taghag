"""Backfill rendition_time_offset for existing human<->mixonset cue pairs.

For every audio_file that already carries both ``human`` and ``mixonset`` cues,
vote the mixonset grid against the human grid (``time_base.reconcile_offset``),
upsert the reconciled offset, and stamp the mixonset cues/segments with
``time_base='rendition'`` + ``measured_against_file_id`` so the canonical views
re-zero them. Additive and idempotent: re-running recomputes and upserts.

This corrects history; new imports are reconciled inline by ``MixonsetImporter``.

    python -m scripts.backfill_rendition_offsets [--dry-run]
"""

from __future__ import annotations

import argparse

from taghag_import.config import DatabaseConfig
from taghag_import.db_client import TaghagDbClient
from taghag_import.time_base import reconcile_offset


def _pairs(db: TaghagDbClient, owner_user_id: str) -> dict[str, dict[str, list[float]]]:
    """audio_file_id -> {'human': [...ms], 'mixonset': [...ms]} for tracks with both."""
    by_file: dict[str, dict[str, list[float]]] = {}
    offset = 0
    while True:
        rows = db._get_postgrest_rows(
            "track_cue",
            {
                "select": "audio_file_id,source_system,time_ms",
                "owner_user_id": f"eq.{owner_user_id}",
                "source_system": "in.(human,mixonset)",
                "limit": "1000",
                "offset": str(offset),
            },
        )
        if not rows:
            break
        for r in rows:
            slot = by_file.setdefault(str(r["audio_file_id"]), {"human": [], "mixonset": []})
            slot[str(r["source_system"])].append(float(r["time_ms"]))
        offset += 1000
    return {fid: g for fid, g in by_file.items() if g["human"] and g["mixonset"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="compute, don't write")
    args = ap.parse_args()

    config = DatabaseConfig.from_env()
    db = TaghagDbClient(config)
    owner_user_id = config.owner_user_id

    pairs = _pairs(db, owner_user_id)
    print(f"Found {len(pairs)} tracks with both human and mixonset cues.")

    reconciled = skipped = 0
    for fid, grids in sorted(pairs.items()):
        offset = reconcile_offset(
            canonical_file_id=fid,
            source_file_id=fid,
            source_system="mixonset",
            canonical_cues_ms=grids["human"],
            source_cues_ms=grids["mixonset"],
        )
        if offset is None:
            skipped += 1
            print(f"  SKIP {fid}: too little overlap to vote")
            continue
        print(
            f"  {fid}: offset={offset.offset_ms:+.2f}ms "
            f"residual={offset.residual_ms} conf={offset.confidence} "
            f"({offset.offset_method})"
        )
        if args.dry_run:
            reconciled += 1
            continue
        db.upsert_rendition_time_offsets([offset.to_row(owner_user_id)])
        # Stamp the cues/segments so the canonical views pick up the offset.
        for table in ("track_cue", "track_segment"):
            db._patch_postgrest_rows(
                table,
                {
                    "audio_file_id": f"eq.{fid}",
                    "owner_user_id": f"eq.{owner_user_id}",
                    "source_system": "eq.mixonset",
                },
                {"time_base": "rendition", "measured_against_file_id": fid},
            )
        reconciled += 1

    print(f"Done. reconciled={reconciled} skipped={skipped} "
          f"{'(dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
