#!/usr/bin/env python3
"""Build the live transition spec layer over a linear render plan.

This script takes an identity-keyed render_plan.json (e.g., from Beatport grids)
and generates the exact transition instructions (A -> B crossfade markers, 
stretch flags, overlap duration) needed by the live automix engine.

It supports two strategies:
1. `beatport`: Uses the `mix_in_ms` and `mix_out_ms` directly from the input plan.
2. `spotify`: Reads the Spotify Automix payloads to determine acoustic fade boundaries
   (`start_of_fade_out` and `end_of_fade_in`), overriding the grid's phrasing points.

Usage:
  python build_transition_spec.py render_plan.json [OUT.json] --strategy spotify
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

def get_isrc_to_spotify_mapping(db_path: str) -> dict:
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT isrc, spotify_id FROM track_identity WHERE isrc IS NOT NULL AND spotify_id IS NOT NULL")
    mapping = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return mapping

def load_spotify_payload(automix_dir: Path, spotify_id: str) -> dict:
    p = automix_dir / f"{spotify_id}.json"
    if p.exists():
        with open(p, "r") as f:
            return json.load(f)
    return {}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_in", type=str, help="Input render_plan.json")
    parser.add_argument("plan_out", type=str, nargs="?", default="live_render_plan.json", help="Output live render plan")
    parser.add_argument("--strategy", choices=["beatport", "spotify"], default="spotify", 
                        help="Authority strategy for mix points (default: spotify)")
    parser.add_argument("--automix-dir", type=str, default="../../automix_payloads",
                        help="Path to downloaded Spotify JSON payloads")
    parser.add_argument("--db-path", type=str, default="/Users/g/Projects/tag/slut_db/FRESH_2026/music_v3.db",
                        help="Path to tagslut database")
    parser.add_argument("--overlap-beats", type=int, default=32,
                        help="Number of beats to overlap during transition (default 32)")
    
    args = parser.parse_args()
    
    plan_path = Path(args.plan_in).resolve()
    if not plan_path.exists():
        print(f"Error: {plan_path} not found.")
        return 1
        
    with open(plan_path, "r") as f:
        plan = json.load(f)
        
    tracks = plan.get("tracks", [])
    if not tracks:
        print("No tracks found in plan.")
        return 1

    automix_dir = Path(args.automix_dir).resolve()
    
    mapping = {}
    if args.strategy == "spotify":
        mapping = get_isrc_to_spotify_mapping(args.db_path)
        print(f"Loaded {len(mapping)} ISRC->Spotify mappings from DB")

    transitions = []
    
    # Iterate through consecutive pairs
    for i in range(len(tracks) - 1):
        t1 = tracks[i]
        t2 = tracks[i+1]
        
        # Skip if they failed upstream decode
        if not t1.get("decode_ok") or not t2.get("decode_ok"):
            continue
            
        bpm1 = float(t1.get("bpm", 120.0))
        bpm2 = float(t2.get("bpm", 120.0))
        
        # Start with Beatport defaults
        mix_out_ms = t1.get("mix_out_ms")
        mix_in_ms = t2.get("mix_in_ms")
        note = f"{args.strategy} default"
        
        if args.strategy == "spotify":
            isrc1 = t1.get("isrc")
            isrc2 = t2.get("isrc")
            sid1 = mapping.get(isrc1)
            sid2 = mapping.get(isrc2)
            
            p1 = load_spotify_payload(automix_dir, sid1) if sid1 else {}
            p2 = load_spotify_payload(automix_dir, sid2) if sid2 else {}
            
            # Note: Spotify payload stores boundaries in seconds
            if "track" in p1 and "start_of_fade_out" in p1["track"]:
                val_s = p1["track"]["start_of_fade_out"]
                if val_s > 0:
                    mix_out_ms = val_s * 1000.0
                    note += "; T1 spotify fade_out"
            elif "start_of_fade_out" in p1: # root level fallback
                val_s = p1["start_of_fade_out"]
                if val_s > 0:
                    mix_out_ms = val_s * 1000.0
                    note += "; T1 spotify fade_out"
                    
            if "track" in p2 and "end_of_fade_in" in p2["track"]:
                val_s = p2["track"]["end_of_fade_in"]
                mix_in_ms = val_s * 1000.0
                note += "; T2 spotify fade_in"
            elif "end_of_fade_in" in p2: # root level fallback
                val_s = p2["end_of_fade_in"]
                mix_in_ms = val_s * 1000.0
                note += "; T2 spotify fade_in"
            
        # Basic stretch check
        bpm_delta = abs(bpm1 - bpm2)
        stretch_required = bpm_delta > 0.05
        
        # Overlap duration in ms (relative to T1's BPM)
        overlap_ms = (args.overlap_beats * 60.0 / bpm1) * 1000.0
        
        if mix_out_ms is not None: mix_out_ms = round(mix_out_ms, 2)
        if mix_in_ms is not None: mix_in_ms = round(mix_in_ms, 2)
        
        transitions.append({
            "from_seq": t1["seq"],
            "to_seq": t2["seq"],
            "from_isrc": t1.get("isrc"),
            "to_isrc": t2.get("isrc"),
            "mix_out_ms": mix_out_ms,
            "mix_in_ms": mix_in_ms,
            "overlap_ms": round(overlap_ms, 2),
            "overlap_beats": args.overlap_beats,
            "bpm_delta": round(bpm_delta, 3),
            "stretch_required": stretch_required,
            "strategy": args.strategy,
            "note": note
        })

    plan["transitions"] = transitions
    plan["transition_strategy"] = args.strategy
    
    with open(args.plan_out, "w") as f:
        json.dump(plan, f, indent=2)
        
    print(f"Wrote {args.plan_out} with {len(transitions)} transitions using '{args.strategy}' strategy.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
