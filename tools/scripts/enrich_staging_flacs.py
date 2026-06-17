import sys
import os
import re
import shutil
import argparse
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

# cleanroom-audit: allow-start
sys.path.insert(0, "/Users/g/Projects/tagslut")
from tagslut.metadata.enricher import Enricher
from tagslut.metadata.auth import TokenManager
from tagslut.metadata.models.types import LocalFileInfo
# cleanroom-audit: allow-end
from mutagen.flac import FLAC

def sanitize(s: str) -> str:
    if not s:
        return ""
    s = str(s).replace("–", "-").replace("—", "-")
    s = re.sub(r'[<>:"/\\|?*]', '_', s)
    return s.strip()

def get_tag(audio: FLAC, key: str, default: str = "") -> str:
    val = audio.get(key)
    return str(val[0]) if val else default

def set_tag(audio: FLAC, key: str, value: str):
    if value:
        audio[key] = [str(value)]
    else:
        audio.pop(key, None)

def extract_local_info_flac(flac_path: Path) -> tuple[LocalFileInfo, dict]:
    try:
        audio = FLAC(flac_path)
    except Exception:
        return None, {}
        
    duration = audio.info.length
    artist = get_tag(audio, "artist")
    title = get_tag(audio, "title")
    album = get_tag(audio, "album")
    isrc = get_tag(audio, "isrc")
    
    date = get_tag(audio, "date")
    year = None
    if date:
        match = re.search(r'\b(19|20)\d{2}\b', str(date))
        if match:
            year = int(match.group(0))
            
    info = LocalFileInfo(
        path=str(flac_path),
        measured_duration_s=duration,
        tag_artist=artist,
        tag_title=title,
        tag_album=album,
        tag_isrc=isrc,
        tag_year=year,
        tag_label=get_tag(audio, "organization") or get_tag(audio, "label")
    )
    
    raw_tags = {
        "albumartist": get_tag(audio, "albumartist", artist),
        "track": get_tag(audio, "tracknumber", "01"),
        "compilation": get_tag(audio, "compilation", "0"),
        "audio_obj": audio
    }
    return info, raw_tags

def process_flac(flac_path: Path, root_dir: Path, enricher: Enricher, heuristic_compilations: set, args: argparse.Namespace) -> tuple[int, list]:
    logs = []
    modifications = 0
    info, raw = extract_local_info_flac(flac_path)
    if not info:
        logs.append(f"[ERROR] Failed to read {flac_path.name}")
        return 0, logs
        
    audio = raw["audio_obj"]
    
    # Compilation check
    is_comp = False
    if raw["compilation"] in ["1", "true", "yes"] or raw["albumartist"].lower() in ["va", "various", "various artists"]:
        is_comp = True
    if info.tag_album and info.tag_album.strip() in heuristic_compilations:
        is_comp = True
        
    info.compilation_locked = is_comp

    # API ENRICHMENT
    result = enricher.resolve_file(info)
    
    artist = result.canonical_artist or info.tag_artist or "Unknown Artist"
    title = result.canonical_title or info.tag_title or "Unknown Title"
    year_str = str(result.canonical_year or info.tag_year) if (result.canonical_year or info.tag_year) else "UNKNOWN_YEAR"
    label = result.canonical_label or info.tag_label or ""
    
    try:
        nn = f"{int(str(raw['track']).split('/')[0]):02d}"
    except:
        nn = "01"

    if result.canonical_is_compilation:
        is_comp = True

    if is_comp:
        album_artist = "Various Artists"
        album = info.tag_album or "Unknown Album"
        folder_artist = label if label else "Various Artists"
        rel_path = Path("Compilations") / sanitize(folder_artist) / f"[{year_str}] {sanitize(album)}" / f"{nn} - {sanitize(artist)} - {sanitize(title)}.flac"
    else:
        album_artist = raw["albumartist"]
        album = result.canonical_album or info.tag_album or "Unknown Album"
        rel_path = Path("Artists") / sanitize(album_artist) / f"[{year_str}] {sanitize(album)}" / f"{nn} - {sanitize(artist)} - {sanitize(title)}.flac"
        
    dest_flac = root_dir / rel_path
    
    # Verbose logging
    def check_diff(field, old, new):
        nonlocal modifications
        if str(old) != str(new):
            logs.append(f"  [API ENRICH] {field}: '{old}' -> '{new}'")
            modifications += 1

    check_diff("Title", info.tag_title, title)
    check_diff("Artist", info.tag_artist, artist)
    check_diff("Album", info.tag_album, album)
    check_diff("AlbumArtist", raw["albumartist"], album_artist)
    if is_comp and raw["compilation"] != "1":
        check_diff("Compilation", raw["compilation"], "1")
    if result.canonical_genre:
        check_diff("Genre", get_tag(audio, "genre"), result.canonical_genre)
    if result.canonical_isrc and result.canonical_isrc != info.tag_isrc:
        check_diff("ISRC", info.tag_isrc, result.canonical_isrc)
        
    if dest_flac.absolute() != flac_path.absolute():
        logs.append(f"  [MOVE] '{flac_path.relative_to(root_dir)}' -> '{rel_path}'")
        modifications += 1
        
    if args.dry_run:
        if modifications > 0:
            logs.insert(0, f"\n[FILE] {flac_path.name}")
        return modifications, logs
        
    if modifications > 0:
        logs.insert(0, f"\n[FILE] {flac_path.name}")
        try:
            set_tag(audio, "title", title)
            set_tag(audio, "artist", artist)
            set_tag(audio, "album", album)
            set_tag(audio, "albumartist", album_artist)
            set_tag(audio, "date", year_str)
            if label: set_tag(audio, "organization", label)
            if result.canonical_genre: set_tag(audio, "genre", result.canonical_genre)
            if result.canonical_isrc: set_tag(audio, "isrc", result.canonical_isrc)
            if is_comp: set_tag(audio, "compilation", "1")
            
            if result.beatport_id: set_tag(audio, "beatport_track_id", str(result.beatport_id))
            if result.spotify_id: set_tag(audio, "spotify_id", str(result.spotify_id))
            if result.tidal_id: set_tag(audio, "tidal_id", str(result.tidal_id))
            
            audio.save()
            
            if dest_flac.absolute() != flac_path.absolute():
                dest_flac.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(flac_path), str(dest_flac))
                
        except Exception as e:
            logs.append(f"  [ERROR] Execution failed: {e}")
            
    return modifications, logs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Path to staging FLACs")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without executing")
    args = parser.parse_args()
    
    root_dir = Path(args.source)
    if not root_dir.exists():
        print(f"Error: {root_dir} does not exist.")
        return
        
    print(f"Scanning for FLAC files in {root_dir}...")
    flacs = list(root_dir.rglob("*.flac"))
    print(f"Found {len(flacs)} FLACs.")
    
    print("Running heuristic compilation pre-scan...")
    album_artists = defaultdict(set)
    for flac_path in flacs:
        info, _ = extract_local_info_flac(flac_path)
        if info and info.tag_album and info.tag_artist:
            alb = info.tag_album.strip()
            art = info.tag_artist.strip().lower()
            if alb:
                album_artists[alb].add(art)
                
    heuristic_compilations = {alb for alb, arts in album_artists.items() if len(arts) > 1}
    print(f"Detected {len(heuristic_compilations)} compilations via heuristic grouping.")
    
    print("Initializing API Enricher (Spotify, Tidal, Beatport, Qobuz)...")
    token_manager = TokenManager()
    enricher = Enricher(db_path=Path("__standalone__"), token_manager=token_manager, providers=["beatport", "tidal", "spotify", "qobuz"], dry_run=args.dry_run, mode="hoarding")
    
    if args.dry_run:
        print("\n--- BEGIN DRY RUN ---")
    else:
        print("\n--- EXECUTING CHANGES ---")

    total_modified = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(process_flac, p, root_dir, enricher, heuristic_compilations, args): p for p in flacs}
        for future in concurrent.futures.as_completed(futures):
            mod_count, logs = future.result()
            if mod_count > 0:
                total_modified += 1
                for log in logs:
                    print(log)
                    
    print(f"\nFinished processing. {total_modified} files {'would be' if args.dry_run else 'were'} modified/moved.")

if __name__ == "__main__":
    main()
