import argparse
import os
import re
import shutil
from pathlib import Path
from collections import defaultdict
import concurrent.futures

from mutagen.flac import FLAC

def sanitize(s: str) -> str:
    if not s:
        return ""
    s = str(s).replace("–", "-").replace("—", "-")
    
    # Remove trailing Beatport/Traxsource catalog identifiers
    # e.g., "DJ-Kicks [K7255DTMM]" or "Some Album (XYZ123)"
    # We use a non-greedy match and explicit word boundaries to be safe.
    # The regex targets space followed by brackets/parentheses containing 4-20 alphanumeric chars at the end of string.
    s = re.sub(r'\s*[\(\[][A-Za-z0-9_ -]{4,20}[\)\]]\s*$', '', s)
    
    # Remove specific substrings like "Beatport" or "Traxsource" if they got embedded
    s = re.sub(r'\s*-\s*Beatport.*$', '', s, flags=re.IGNORECASE)
    
    # Remove invalid characters for file paths
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

def process_flac(flac_path: Path, root_dir: Path, heuristic_compilations: set, args: argparse.Namespace) -> tuple[int, list]:
    logs = []
    try:
        audio = FLAC(flac_path)
    except Exception as e:
        logs.append(f"[ERROR] Failed to read {flac_path.name}: {e}")
        return 0, logs
        
    artist = get_tag(audio, "artist", "Unknown Artist")
    title = get_tag(audio, "title", "Unknown Title")
    album = get_tag(audio, "album", "Unknown Album")
    album_artist = get_tag(audio, "albumartist")
    compilation_flag = get_tag(audio, "compilation")
    date = get_tag(audio, "date")
    label = get_tag(audio, "organization") or get_tag(audio, "label")
    tracknumber = get_tag(audio, "tracknumber", "01")
    
    # Clean track number (e.g. "01/12" -> "01")
    try:
        nn = f"{int(str(tracknumber).split('/')[0]):02d}"
    except:
        nn = "01"
        
    year_str = "UNKNOWN_YEAR"
    if date:
        match = re.search(r'\b(19|20)\d{2}\b', str(date))
        if match:
            year_str = match.group(0)

    # Detect Compilation
    is_comp = False
    if compilation_flag in ["1", "true", "yes"]:
        is_comp = True
    elif album_artist.lower() in ["va", "various", "various artists"]:
        is_comp = True
    elif album in heuristic_compilations:
        is_comp = True
        
    # Sanitize tags
    new_artist = sanitize(artist)
    new_title = sanitize(title)
    new_album = sanitize(album)
    
    if is_comp:
        new_album_artist = "Various Artists"
        folder_artist = sanitize(label) if label else "Various Artists"
        rel_path = Path("Compilations") / folder_artist / f"[{year_str}] {new_album}" / f"{nn} - {new_artist} - {new_title}.flac"
    else:
        new_album_artist = sanitize(album_artist) if album_artist else new_artist
        rel_path = Path("Artists") / new_album_artist / f"[{year_str}] {new_album}" / f"{nn} - {new_artist} - {new_title}.flac"

    dest_flac = root_dir / rel_path
    
    modifications = 0
    
    # Verbose logging for tag mutations
    if new_artist != artist:
        logs.append(f"  [RETAG] Artist: '{artist}' -> '{new_artist}'")
        modifications += 1
    if new_title != title:
        logs.append(f"  [RETAG] Title: '{title}' -> '{new_title}'")
        modifications += 1
    if new_album != album:
        logs.append(f"  [RETAG] Album: '{album}' -> '{new_album}'")
        modifications += 1
    if new_album_artist != album_artist:
        logs.append(f"  [RETAG] AlbumArtist: '{album_artist}' -> '{new_album_artist}'")
        modifications += 1
    if is_comp and compilation_flag != "1":
        logs.append(f"  [RETAG] Compilation: '{compilation_flag}' -> '1'")
        modifications += 1

    if dest_flac.absolute() != flac_path.absolute():
        logs.append(f"  [MOVE] '{flac_path.relative_to(root_dir)}' -> '{rel_path}'")
        modifications += 1

    if args.dry_run:
        if modifications > 0:
            logs.insert(0, f"\n[FILE] {flac_path.name}")
        return modifications, logs

    # Execute changes
    if modifications > 0:
        logs.insert(0, f"\n[FILE] {flac_path.name}")
        try:
            if new_artist != artist: set_tag(audio, "artist", new_artist)
            if new_title != title: set_tag(audio, "title", new_title)
            if new_album != album: set_tag(audio, "album", new_album)
            if new_album_artist != album_artist: set_tag(audio, "albumartist", new_album_artist)
            if is_comp and compilation_flag != "1": set_tag(audio, "compilation", "1")
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
        try:
            audio = FLAC(flac_path)
            alb = get_tag(audio, "album").strip()
            art = get_tag(audio, "artist").strip().lower()
            if alb and art:
                album_artists[alb].add(art)
        except:
            continue
            
    heuristic_compilations = {alb for alb, arts in album_artists.items() if len(arts) > 1}
    print(f"Detected {len(heuristic_compilations)} compilations via heuristic grouping.")
    
    if args.dry_run:
        print("\n--- BEGIN DRY RUN ---")
    else:
        print("\n--- EXECUTING CHANGES ---")

    total_modified = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(process_flac, p, root_dir, heuristic_compilations, args): p for p in flacs}
        for future in concurrent.futures.as_completed(futures):
            mod_count, logs = future.result()
            if mod_count > 0:
                total_modified += 1
                for log in logs:
                    print(log)
                    
    print(f"\nFinished processing. {total_modified} files {'would be' if args.dry_run else 'were'} modified/moved.")

if __name__ == "__main__":
    main()
