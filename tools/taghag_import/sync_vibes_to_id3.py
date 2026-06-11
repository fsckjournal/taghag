from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mutagen.id3 import ID3, COMM, ID3NoHeaderError

from .db_client import TaghagDbClient

VIBE_PREFIX = "[TS:"
VIBE_PATTERN = re.compile(r"\[TS:\s*.*?\]")


def sync_vibes_to_file(path: Path, vibes: list[str], dry_run: bool = True) -> bool:
    if not path.exists():
        return False
    if not vibes:
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
        if old_text:
            new_text = f"{old_text} {vibe_str}".strip()
        else:
            new_text = vibe_str

    if old_text == new_text:
        return False

    target_frame.text = [new_text]

    print(f"{'DRY-RUN: ' if dry_run else ''}Updating {path.name}")
    print(f"  Old: {old_text}")
    print(f"  New: {new_text}")

    if not dry_run:
        audio.save(path, v2_version=3)

    return True


def sync_postgres_vibes_to_id3(
    db_client: TaghagDbClient,
    music_dir: str | Path,
    *,
    execute: bool = False
) -> int:
    music_dir = Path(music_dir).expanduser().resolve()
    owner_id = db_client._config.owner_user_id
    
    # Fetch all records from the unified sonic_analysis view
    analyses = db_client._get_postgrest_rows(
        "sonic_analysis",
        {"owner_user_id": f"eq.{owner_id}"}
    )
    
    # Fetch all audio files to resolve path
    audio_files = {
        f["id"]: f
        for f in db_client._get_postgrest_rows(
            "audio_file",
            {"owner_user_id": f"eq.{owner_id}"}
        )
    }

    updated_count = 0
    dry_run = not execute

    for record in analyses:
        file_id = record["audio_file_id"]
        if file_id not in audio_files:
            continue
            
        f_info = audio_files[file_id]
        abs_path = music_dir / f_info["path"]
        if not abs_path.exists():
            abs_path = Path(f_info["path"])
            if not abs_path.exists():
                continue

        # If pinned, sync human vibes. Otherwise, sync computed producer vibes.
        is_pinned = record.get("pinned", False)
        if is_pinned:
            vibes = record.get("human_vibes") or []
        else:
            vibes = record.get("producer_vibes") or []

        # Ensure vibes is a list of strings
        if isinstance(vibes, str):
            try:
                vibes = json.loads(vibes)
            except Exception:
                vibes = []

        if not isinstance(vibes, list):
            vibes = []

        if sync_vibes_to_file(abs_path, vibes, dry_run):
            updated_count += 1

    print(f"\nProcessed {len(analyses)} records, updated {updated_count} files.")
    return updated_count
