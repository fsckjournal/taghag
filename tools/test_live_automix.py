#!/usr/bin/env python3
import json
import os
import sys
from taghag_import.automix import AutomixEngine

def test_transition(id_a, id_b, cache_dir):
    print(f"[*] Testing transition from Track A ({id_a}) to Track B ({id_b}) using local offline cache...")
    
    try:
        analysis_a = AutomixEngine.fetch_local_analysis(id_a, cache_dir)
        analysis_b = AutomixEngine.fetch_local_analysis(id_b, cache_dir)
    except FileNotFoundError as e:
        print(f"[!] Error: {e}")
        return

    engine = AutomixEngine(analysis_a, analysis_b)
    result = engine.compute_transition()
    
    print("\n[+] Transition Computed Successfully!")
    print(f"    - Track A Tempo:  {analysis_a.get('track', {}).get('tempo'):.2f} BPM")
    print(f"    - Track B Tempo:  {analysis_b.get('track', {}).get('tempo'):.2f} BPM")
    print(f"    - Transition Duration: {result['transition_duration']}s")
    
    print("\n--- Track A (Outro) ---")
    print(f"    Start Mix-Out: {result['track_a']['start_point']}s")
    print(f"    End Mix-Out:   {result['track_a']['end_point']}s")
    
    print("\n--- Track B (Intro) ---")
    print(f"    Start Mix-In:  {result['track_b']['start_point']}s")
    print(f"    End Mix-In:    {result['track_b']['end_point']}s")
    
    print("\n[+] The 'mixslice/render_transition.py' Baker can now pre-render this overlap seamlessly.")

if __name__ == "__main__":
    cache_dir = os.path.join(os.path.dirname(__file__), "..", "automix_payloads")
    
    # Grab the first two payloads from the directory as a test
    payloads = [f.replace(".json", "") for f in os.listdir(cache_dir) if f.endswith(".json")][:2]
    
    if len(payloads) < 2:
        print("Need at least 2 payloads in automix_payloads/")
        sys.exit(1)
        
    test_transition(payloads[0], payloads[1], cache_dir)
