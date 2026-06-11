import argparse
import json
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from pathlib import Path

from taghag_import.tags import extract_mp3_tags
from taghag_import.config import read_database_config
from taghag_import.db_client import TaghagDbClient

def parse_rekordbox_xml(xml_path: str) -> dict[str, list[dict]]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    collection = root.find("COLLECTION")
    file_to_cues = {}
    if collection is None:
        return file_to_cues
        
    for track in collection.findall("TRACK"):
        location_uri = track.get("Location")
        if not location_uri:
            continue
            
        if location_uri.startswith("file://localhost"):
            location_path = location_uri[len("file://localhost"):]
        elif location_uri.startswith("file://"):
            location_path = location_uri[len("file://"):]
        else:
            location_path = location_uri
        location_path = unquote(location_path)
        
        cues = []
        for pm in track.findall("POSITION_MARK"):
            num_val = int(pm.get("Num", "-1"))
            if num_val < 0:
                continue
            start_sec = float(pm.get("Start", "0"))
            name = pm.get("Name", "Cue")
            cues.append({
                "time_ms": int(start_sec * 1000),
                "name": name,
                "cue_family": name,
                "cue_kind": "hot",
                "cue_type": "hot_cue",
                "source_system": "mixedinkey",
            })
        if cues:
            file_to_cues[location_path] = cues
    return file_to_cues

def parse_m3u8(playlist_path: str) -> list[str]:
    paths = []
    with open(playlist_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                paths.append(line)
    return paths

def build_tags_cache(file_paths: set[str], cache_file: str) -> dict[str, str]:
    cache_path = Path(cache_file)
    cache = {}
    if cache_path.exists():
        with open(cache_path, "r") as f:
            cache = json.load(f)
            
    updated = False
    for path_str in file_paths:
        if path_str not in cache:
            p = Path(path_str)
            if p.exists():
                tags = extract_mp3_tags(p)
                isrc = tags.get("isrc")
                if isrc:
                    cache[path_str] = str(isrc).strip().upper()
                    updated = True
                    
    if updated:
        with open(cache_path, "w") as f:
            json.dump(cache, f, indent=2)
            
    return cache

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", help="Path to rekordbox_mikcues_001.xml")
    parser.add_argument("--m3u-dir", help="Directory containing .m3u8 playlists")
    parser.add_argument("--tags-cache", default="tags_cache.json", help="Path to JSON file to collect and reuse tags locally")
    parser.add_argument("--path-replace", help="Replace prefix in parsed paths, format: old_prefix:new_prefix (e.g. /Volumes/MUSIC:/Volumes/LOSSY/taghag/mp3s)")
    parser.add_argument("--dry-run", action="store_true", help="Print operations without executing")
    args = parser.parse_args()
    
    config = read_database_config()
    db = TaghagDbClient(config)
    
    file_to_cues = {}
    if args.xml:
        print(f"Parsing XML {args.xml}...")
        raw_cues = parse_rekordbox_xml(args.xml)
        
        # Apply path replacements if provided
        if args.path_replace and ":" in args.path_replace:
            old_prefix, new_prefix = args.path_replace.split(":", 1)
            for old_path, cues in raw_cues.items():
                if old_path.startswith(old_prefix):
                    new_path = new_prefix + old_path[len(old_prefix):]
                    file_to_cues[new_path] = cues
                else:
                    file_to_cues[old_path] = cues
            print(f"Applied path replacement: '{old_prefix}' -> '{new_prefix}'")
        else:
            file_to_cues = raw_cues
            
        print(f"Found {len(file_to_cues)} tracks with hot cues.")
        
    m3u_playlists = {}
    if args.m3u_dir:
        m3u_dir = Path(args.m3u_dir)
        print(f"Scanning for M3U8 playlists in {m3u_dir}...")
        for p in m3u_dir.glob("*.m3u8"):
            parsed_paths = parse_m3u8(str(p))
            if args.path_replace and ":" in args.path_replace:
                old_prefix, new_prefix = args.path_replace.split(":", 1)
                replaced_paths = []
                for old_path in parsed_paths:
                    if old_path.startswith(old_prefix):
                        replaced_paths.append(new_prefix + old_path[len(old_prefix):])
                    else:
                        replaced_paths.append(old_path)
                m3u_playlists[p.stem] = replaced_paths
            else:
                m3u_playlists[p.stem] = parsed_paths
            print(f"Found playlist {p.stem} with {len(m3u_playlists[p.stem])} tracks.")
            
    all_files = set(file_to_cues.keys())
    for paths in m3u_playlists.values():
        all_files.update(paths)
        
    print(f"Found {len(all_files)} unique file paths. Checking local cache {args.tags_cache}...")
    
    # Custom cache builder that checks for .mp3 alternative
    cache_path = Path(args.tags_cache)
    cache = {}
    if cache_path.exists():
        with open(cache_path, "r") as f:
            cache = json.load(f)
            
    updated = False
    extracted_count = 0
    
    for path_str in all_files:
        if path_str not in cache:
            p = Path(path_str)
            if not p.exists() and p.suffix.lower() != ".mp3":
                # Try falling back to an .mp3 version (in case of transcodes)
                fallback_p = p.with_suffix(".mp3")
                if fallback_p.exists():
                    p = fallback_p
                    
            if p.exists():
                tags = extract_mp3_tags(p)
                isrc = tags.get("isrc")
                if isrc:
                    cache[path_str] = str(isrc).strip().upper()
                    updated = True
                    extracted_count += 1
        else:
            extracted_count += 1
                    
    if updated:
        with open(cache_path, "w") as f:
            json.dump(cache, f, indent=2)
            
    isrc_cache = cache
    print(f"Extracted/loaded ISRC for {extracted_count} files out of {len(all_files)}.")
    
    unique_isrcs = set(isrc_cache.values())
    if not unique_isrcs:
        print("No ISRCs found. Exiting.")
        return
        
    print(f"Looking up {len(unique_isrcs)} unique ISRCs in Supabase...")
    isrc_to_audio_file = {}
    try:
        query = {
            "select": "isrc,audio_file_id",
            "isrc": f"in.({','.join(unique_isrcs)})"
        }
        res = db._get_postgrest_rows("dj_tag", query)
        for row in res:
            if row.get("isrc") and row.get("audio_file_id"):
                isrc_to_audio_file[row["isrc"].strip().upper()] = row["audio_file_id"]
    except Exception as e:
        print(f"Warning: Failed to fetch dj_tag from Supabase: {e}")
        
    print(f"Mapped {len(isrc_to_audio_file)} ISRCs to audio_file_ids.")
    
    track_cue_rows = []
    for file_path, cues in file_to_cues.items():
        isrc = isrc_cache.get(file_path)
        if not isrc: continue
        audio_file_id = isrc_to_audio_file.get(isrc)
        if not audio_file_id: continue
        
        for cue in cues:
            track_cue_rows.append({
                "owner_user_id": config.owner_user_id,
                "audio_file_id": audio_file_id,
                "time_ms": cue["time_ms"],
                "name": cue["name"],
                "cue_family": cue["cue_family"],
                "cue_kind": cue["cue_kind"],
                "cue_type": cue["cue_type"],
                "source_system": cue["source_system"],
                "confidence": 1.0
            })
            
    print(f"Prepared {len(track_cue_rows)} track_cue rows.")
    
    if args.dry_run:
        print("\n[DRY RUN] Summary:")
        print(f" - Would insert {len(track_cue_rows)} cues.")
        if track_cue_rows: print("   Sample:", track_cue_rows[0])
        print("Skipping insert.")
        return
        
    if track_cue_rows:
        batch_size = 500
        inserted = 0
        for i in range(0, len(track_cue_rows), batch_size):
            batch = track_cue_rows[i:i + batch_size]
            db._postgrest_request("track_cue", batch)
            inserted += len(batch)
            print(f"Inserted {inserted}/{len(track_cue_rows)} cues...")

    print("Done!")

if __name__ == "__main__":
    main()
