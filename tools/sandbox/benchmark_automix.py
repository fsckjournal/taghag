#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path
import json

import sqlite3
import random

from taghag_import.automix import AutomixEngine

def benchmark_track(flac_path: Path, spotify_id: str, cache_dir: Path):
    print(f"[*] Benchmarking Track: {flac_path.name}")
    print(f"    Spotify Ground Truth ID: {spotify_id}")
    
    # 1. Fetch Ground Truth (Spotify)
    try:
        spotify_payload = AutomixEngine.fetch_local_analysis(spotify_id, str(cache_dir))
    except FileNotFoundError:
        print(f"    [!] Error: Spotify payload {spotify_id}.json not found in cache.")
        return
        
    s_track = spotify_payload.get("track", {})
    s_tempo = s_track.get("tempo", 0.0)
    s_fade_in = s_track.get("end_of_fade_in", 0.0)
    s_fade_out = s_track.get("start_of_fade_out", 0.0)
    s_key = s_track.get("key")
    s_mode = s_track.get("mode")
    
    # 2. Generate Pure Offline Intelligence
    print("    Running Apple Music ML Analyzer offline...")
    try:
        offline_payload = AutomixEngine.generate_pure_offline_analysis(str(flac_path))
    except Exception as e:
        print(f"    [!] Error running offline analyzer: {e}")
        return
        
    o_track = offline_payload.get("track", {})
    o_tempo = o_track.get("tempo", 0.0)
    o_fade_in = o_track.get("end_of_fade_in", 0.0)
    o_fade_out = o_track.get("start_of_fade_out", 0.0)
    o_key = o_track.get("key")
    o_mode = o_track.get("mode")
    o_energy = o_track.get("energy", 0)
    
    # 3. Output Differential Report
    print("\n--- Benchmark Results ---")
    
    # Tempo Comparison
    tempo_diff = abs(s_tempo - o_tempo)
    if tempo_diff < 0.5:
        print(f"    [✔] Tempo:     {o_tempo:.2f} BPM (Matches Spotify {s_tempo:.2f})")
    else:
        print(f"    [X] Tempo:     {o_tempo:.2f} BPM (Spotify says {s_tempo:.2f}, diff {tempo_diff:.2f})")
        
    # Fade In Comparison
    fi_diff = abs(s_fade_in - o_fade_in)
    if fi_diff < 5.0:
        print(f"    [✔] Fade-In:   {o_fade_in:.3f}s (Matches Spotify {s_fade_in:.3f}s, diff {fi_diff:.3f}s)")
    else:
        print(f"    [X] Fade-In:   {o_fade_in:.3f}s (Spotify says {s_fade_in:.3f}s, diff {fi_diff:.3f}s)")
        
        
    # Fade Out Comparison
    fo_diff = abs(s_fade_out - o_fade_out)
    if fo_diff < 5.0:
        print(f"    [✔] Fade-Out:  {o_fade_out:.3f}s (Matches Spotify {s_fade_out:.3f}s, diff {fo_diff:.3f}s)")
    else:
        print(f"    [X] Fade-Out:  {o_fade_out:.3f}s (Spotify says {s_fade_out:.3f}s, diff {fo_diff:.3f}s)")
        
    # Key Comparison
    key_map = {0: "C", 1: "C#", 2: "D", 3: "D#", 4: "E", 5: "F", 6: "F#", 7: "G", 8: "G#", 9: "A", 10: "A#", 11: "B"}
    mode_map = {0: "Minor", 1: "Major"}
    
    s_key_str = f"{key_map.get(s_key, str(s_key))} {mode_map.get(s_mode, str(s_mode))}" if s_key is not None else "Unknown"
    o_key_str = f"{key_map.get(o_key, str(o_key))} {mode_map.get(o_mode, str(o_mode))}" if o_key is not None else "Unknown"
    
    if s_key == o_key and s_mode == o_mode:
        print(f"    [✔] Key:       {o_key_str} (Matches Spotify)")
    else:
        print(f"    [X] Key:       {o_key_str} (Spotify says {s_key_str})")
        
    print(f"    [i] Energy:    {o_energy}/10 (from Mixed In Key)")
        
    print("\n")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Pure Offline Automix against Spotify payloads")
    parser.add_argument("flac_path", nargs="?", help="Path to a FLAC file to analyze")
    parser.add_argument("spotify_id", nargs="?", help="Spotify ID of the track (must exist in automix_payloads cache)")
    parser.add_argument("--auto", type=int, default=0, help="Automatically benchmark N random tracks from the database")
    
    args = parser.parse_args()
    cache = Path(os.path.dirname(__file__)).parent.parent / "automix_payloads"
    
    if args.auto > 0:
        db_path = "/Users/g/Projects/tag/slut_db/FRESH_2026/music_v3.db"
        print(f"[*] Auto-benchmarking {args.auto} tracks from database...")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get tracks that have a FLAC file and a Spotify ID
        c.execute("""
            SELECT a.path, i.spotify_id 
            FROM asset_file a 
            JOIN asset_link l ON a.id = l.asset_id 
            JOIN track_identity i ON l.identity_id = i.id 
            WHERE i.spotify_id IS NOT NULL AND a.path LIKE '%.flac'
        """)
        rows = c.fetchall()
        conn.close()
        
        # Filter rows to only those we have a payload for
        valid_rows = []
        for path, sid in rows:
            sid = sid.strip()
            if (cache / f"{sid}.json").exists():
                valid_rows.append((path, sid))
                
        if not valid_rows:
            print("    [!] No tracks found with both a local FLAC and a cached Spotify payload.")
            sys.exit(1)
            
        # Select random sample
        sample_size = min(args.auto, len(valid_rows))
        sample = random.sample(valid_rows, sample_size)
        
        for i, (path, sid) in enumerate(sample, 1):
            print(f"\n==========================================")
            print(f"Test {i}/{sample_size}")
            print(f"==========================================")
            benchmark_track(Path(path), sid, cache)
            
    else:
        if not args.flac_path or not args.spotify_id:
            print("Error: Must provide flac_path and spotify_id, or use --auto N")
            sys.exit(1)
        benchmark_track(Path(args.flac_path), args.spotify_id, cache)
