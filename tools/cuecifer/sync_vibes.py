from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from mutagen.id3 import COMM, ID3, ID3NoHeaderError

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taghag_import.config import read_database_config

from cuecifer.db import dict_cursor, open_database
from cuecifer.sonic_discovery import VECTOR_SCHEMA


VIBE_PREFIX = "[TS:"
VIBE_PATTERN = re.compile(r"\[TS:.*?\]")


def _json_to_vibes(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def sync_vibes_to_file(path: Path, vibes: list[str], *, dry_run: bool = True) -> bool:
    if not path.exists() or not vibes:
        return False

    vibe_str = f"{VIBE_PREFIX} {' | '.join(vibes)}]"

    try:
        audio = ID3(path)
    except ID3NoHeaderError:
        audio = ID3()

    comm_frames = audio.getall("COMM")
    target_frame = None
    for frame in comm_frames:
        if frame.desc == "" or frame.desc.lower() == "comment":
            target_frame = frame
            break

    if target_frame is None:
        target_frame = COMM(encoding=3, lang="eng", desc="", text=[])
        audio.add(target_frame)

    old_text = target_frame.text[0] if target_frame.text else ""
    if VIBE_PATTERN.search(old_text):
        new_text = VIBE_PATTERN.sub(vibe_str, old_text).strip()
    else:
        new_text = f"{old_text} {vibe_str}".strip() if old_text else vibe_str

    if old_text == new_text:
        return False

    target_frame.text = [new_text]

    print(f"{'DRY-RUN: ' if dry_run else ''}Updating {path.name}")
    print(f"  Old: {old_text}")
    print(f"  New: {new_text}")

    if not dry_run:
        audio.save(path, v2_version=3)

    return True


def _load_rows() -> list[dict[str, object]]:
    config = read_database_config()
    owner_user_id = config.owner_user_id
    if not owner_user_id:
        raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

    sql = """
        select
            af.path,
            case
                when tc.pinned then coalesce(tc.human_vibes_json, '[]'::jsonb)
                else coalesce(te.producer_vibes_json, '[]'::jsonb)
            end as resolved_vibes_json
        from public.audio_file af
        left join public.track_embedding te
          on te.audio_file_id = af.id
         and te.owner_user_id = af.owner_user_id
         and te.vector_schema = %s
        left join public.track_curation tc
          on tc.audio_file_id = af.id
         and tc.owner_user_id = af.owner_user_id
        where af.owner_user_id = %s
        order by af.path
    """
    with open_database(config) as conn:
        with dict_cursor(conn) as cur:
            cur.execute(sql, (VECTOR_SCHEMA, owner_user_id))
            return list(cur.fetchall())


def sync_all(*, execute: bool = False) -> int:
    rows = _load_rows()
    updated_count = 0
    for row in rows:
        vibes = _json_to_vibes(row.get("resolved_vibes_json"))
        if sync_vibes_to_file(Path(str(row["path"])), vibes, dry_run=not execute):
            updated_count += 1
    print(f"\nProcessed {len(rows)} files, updated {updated_count} files.")
    return updated_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync resolved Cuecifer vibes to MP3 ID3 comments")
    parser.add_argument("--execute", action="store_true", help="Actually write tags (default is dry-run)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.execute:
        print("Running in DRY-RUN mode. Pass --execute to write changes.")
    sync_all(execute=args.execute)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
