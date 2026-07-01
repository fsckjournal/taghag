import os
import json
import time
import requests
import sys
import argparse
import socket
from pathlib import Path

os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

try:
    from librespot.core import Session
    from librespot.zeroconf import ZeroconfServer
except ImportError:
    print("Error: librespot is not installed.")
    sys.exit(1)

_orig_gethostbyname = socket.gethostbyname

def _patched_gethostbyname(hostname):
    try:
        return _orig_gethostbyname(hostname)
    except socket.gaierror:
        return '127.0.0.1'

socket.gethostbyname = _patched_gethostbyname

def get_token():
    print("[*] Broadcasting for Spotify Connect login...")
    print(">>> OPEN SPOTIFY MAC APP AND TAP 'DEVICES' TO CONNECT <<<")
    zs = ZeroconfServer.Builder().create()
    while not zs._ZeroconfServer__session:
        time.sleep(1)
    session = zs._ZeroconfServer__session
    print("[+] Successfully connected to Spotify session.")
    return session

def batch_fetch(track_ids: list[str], output_dir: str, delay: float):
    os.makedirs(output_dir, exist_ok=True)
    
    def get_headers():
        token = session.tokens().get('playlist-read')
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        
    web_api_token = None
    tokens_path = os.path.expanduser("~/.config/tagslut/tokens.json")
    if os.path.exists(tokens_path):
        try:
            with open(tokens_path, 'r') as f:
                web_api_token = json.load(f).get('spotify', {}).get('access_token')
        except Exception:
            pass

    def get_search_headers():
        if web_api_token:
            return {
                'Authorization': f'Bearer {web_api_token}',
                'Accept': 'application/json'
            }
        return get_headers()
    
    success_count = 0
    pending_tracks = []
    
    for t in track_ids:
        t = t.strip()
        if not t:
            continue
        if len(t) == 22 and os.path.exists(os.path.join(output_dir, f"{t}.json")):
            continue
        pending_tracks.append(t)
        
    print(f"\n[*] Pre-filtered {len(track_ids) - len(pending_tracks)} already downloaded/failed tracks.")
    print(f"[*] Starting batch fetch for {len(pending_tracks)} remaining tracks...")
    
    for i, track_id in enumerate(pending_tracks, 1):
        isrc = None
        if len(track_id) != 22:
            isrc = track_id
            print(f"[{i}/{len(pending_tracks)}] Resolving ISRC {isrc}...")
            search_url = f"https://api.spotify.com/v1/search?type=track&q=isrc:{isrc}"
            
            try:
                res = requests.get(search_url, headers=get_search_headers())
                if res.status_code == 200:
                    items = res.json().get('tracks', {}).get('items', [])
                    if items:
                        track_id = items[0]['id']
                        print(f"  -> Resolved to Spotify ID: {track_id} ({items[0]['name']})")
                    else:
                        print(f"  -> ❌ No Spotify track found for ISRC {isrc}")
                        continue
                elif res.status_code == 429:
                    print("  -> 🚨 RATE LIMITED ON SEARCH! Backing off for 10s...")
                    time.sleep(10)
                    pending_tracks.append(track_id) # Retry at the end
                    continue
                elif res.status_code == 401:
                    print("  -> 🚨 Web API Token expired or invalid! Check your tokens.json.")
                    continue
                else:
                    print(f"  -> ❌ Search failed: HTTP {res.status_code}")
                    continue
            except Exception as e:
                print(f"  -> ❌ Network error during search: {e}")
                continue
                
        out_path = os.path.join(output_dir, f"{track_id}.json")
        if os.path.exists(out_path):
            print(f"[{i}/{len(pending_tracks)}] Skipping {track_id} (already downloaded)")
            continue
            
        url = f"https://spclient.wg.spotify.com/audio-attributes/v1/audio-analysis/{track_id}"
        if isrc:
            print("  -> Fetching audio analysis...")
        else:
            print(f"[{i}/{len(pending_tracks)}] Fetching {track_id}...")
            
        try:
            resp = requests.get(url, headers=get_headers())
            if resp.status_code == 200:
                with open(out_path, 'wb') as f:
                    f.write(resp.content)
                print(f"  -> Success! Saved {len(resp.content)} bytes.")
                success_count += 1
            elif resp.status_code == 401:
                print("  -> 🚨 Token expired (HTTP 401)! Forcing refresh and retrying...")
                time.sleep(2)
                pending_tracks.append(track_id) # Retry at the end
                continue
            elif resp.status_code == 429:
                print("  -> 🚨 RATE LIMITED! Spotify returned 429 Too Many Requests.")
                print("  -> Backing off for 10 seconds...")
                time.sleep(10)
                pending_tracks.append(track_id) # Retry at the end
                continue
            elif resp.status_code == 404:
                print("  -> ❌ Failed: HTTP 404 (Not Found). Marking as failed to skip in future.")
                with open(out_path, 'w') as f:
                    f.write('{"error": 404, "message": "Not found in Spotify Automix backend"}')
            else:
                print(f"  -> ❌ Failed: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  -> ❌ Network error: {e}")
            
        if i < len(pending_tracks):
            time.sleep(delay)
            
    print(f"\n[+] Batch complete! Successfully fetched {success_count} new track analyses.")

def extract_tracks_from_jsonl(jsonl_path: str) -> list[str]:
    """Pull fetch targets from a JSONL file. Prefers a pre-resolved 22-char
    ``spotify_id`` (the fetch loop uses it directly, skipping the rate-limited
    ISRC->search step); otherwise falls back to ISRC (top-level or under the
    legacy ``original_tags`` pool-backup shape). Returns a mixed list of
    spotify_ids and ISRCs, both of which batch_fetch() already handles.
    """
    spotify_ids, isrcs = set(), set()
    with open(jsonl_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            sid = data.get('spotify_id')
            if isinstance(sid, str) and len(sid) == 22:
                spotify_ids.add(sid)
                continue
            isrc_val = data.get('isrc') or data.get('original_tags', {}).get('isrc')
            if isinstance(isrc_val, list):
                isrc_val = isrc_val[0] if isrc_val else None
            if isrc_val:
                isrcs.add(isrc_val.strip().upper())
    # spotify_ids first so the no-search path runs before search-bound ISRCs
    return sorted(spotify_ids) + sorted(isrcs)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Batch fetch Spotify Automix data via spclient')
    parser.add_argument('input_file', help='JSONL metadata backup file OR text file with track IDs/ISRCs')
    parser.add_argument('--out', default='automix_payloads', help='Output directory for the JSON files')
    parser.add_argument('--delay', type=float, default=1.0, help='Seconds to sleep between requests (rate limiting)')
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)
        
    tracks = []
    if args.input_file.endswith('.jsonl'):
        print(f"[*] Extracting fetch targets from JSONL: {args.input_file}")
        tracks = extract_tracks_from_jsonl(args.input_file)
        n_sid = sum(1 for t in tracks if len(t) == 22)
        print(f"[*] {n_sid} pre-resolved spotify_ids (skip search) + "
              f"{len(tracks) - n_sid} ISRCs (need search)")
    else:
        with open(args.input_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    tracks.append(line)
                    
    if not tracks:
        print("No valid tracks found in input file.")
        sys.exit(1)
        
    session = get_token()
    batch_fetch(tracks, args.out, args.delay)
    sys.exit(0)
