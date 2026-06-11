from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from mutagen.id3 import ID3

from .db_client import TaghagDbClient

TS_VIBE_PATTERN = re.compile(r"\[TS:\s*(.*?)\]")


def extract_vibes_from_id3(audio_path: Path) -> set[str]:
    """Scans ID3 comments for [TS: vibe] tags."""
    vibes: set[str] = set()
    try:
        audio = ID3(str(audio_path))
    except Exception:
        return vibes

    for frame in audio.getall("COMM"):
        for text in getattr(frame, "text", []) or []:
            match = TS_VIBE_PATTERN.search(str(text))
            if not match:
                continue
            vibe_str = match.group(1).replace("dynamic_evolution", "")
            vibes.update(v.strip() for v in vibe_str.split("|") if v.strip())
            
    return vibes


def apply_human_corrections(
    db_client: TaghagDbClient,
    music_dir: str | Path,
    *,
    execute: bool = False
) -> int:
    music_dir = Path(music_dir).expanduser().resolve()
    owner_id = db_client._config.owner_user_id
    
    # 1. Fetch all audio files
    audio_files = db_client._get_postgrest_rows(
        "audio_file",
        {"owner_user_id": f"eq.{owner_id}"}
    )
    
    # Fetch all curations
    curations = {
        c["audio_file_id"]: c 
        for c in db_client._get_postgrest_rows(
            "track_curation",
            {"owner_user_id": f"eq.{owner_id}"}
        )
    }

    changed = 0
    curation_rows = []

    for file_record in audio_files:
        file_id = file_record["id"]
        rel_path = file_record["path"]
        
        # Resolve physical path
        abs_path = music_dir / rel_path
        if not abs_path.exists():
            abs_path = Path(rel_path)
            if not abs_path.exists():
                continue

        ts_vibes = extract_vibes_from_id3(abs_path)
        if not ts_vibes:
            continue

        # Get existing curation/vibe
        curation = curations.get(file_id)
        if curation:
            existing_vibes = set(curation.get("human_vibes_json") or [])
            is_pinned = curation.get("pinned", False)
        else:
            existing_vibes = set()
            is_pinned = False

        if ts_vibes != existing_vibes or not is_pinned:
            print(
                f"{'EXECUTE' if execute else 'DRY-RUN'} correction for {abs_path.name}: "
                f"{sorted(existing_vibes)} -> {sorted(ts_vibes)}"
            )
            
            if execute:
                curation_rows.append({
                    "owner_user_id": owner_id,
                    "audio_file_id": file_id,
                    "pinned": True,
                    "human_vibes_json": sorted(ts_vibes),
                    "corrected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
            changed += 1

    if execute and curation_rows:
        db_client.upsert_track_curation(curation_rows)
        print(f"Successfully applied {len(curation_rows)} human corrections to Supabase.")
    else:
        print(f"Found {changed} human corrections (dry-run; database unchanged).")

    return changed
