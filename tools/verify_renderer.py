#!/usr/import/env python3
import json
import sys
from taghag_import.automix import AutomixEngine
from taghag_import.audio_renderer import render_transition

def main():
    if len(sys.argv) < 3:
        print("Usage: verify_renderer.py <track_a.flac> <track_b.flac>")
        sys.exit(1)
        
    track_a = sys.argv[1]
    track_b = sys.argv[2]
    out_path = "test_transition.flac"
    
    print(f"Generating offline analysis for Track A: {track_a}")
    payload_a = AutomixEngine.generate_pure_offline_analysis(track_a)
    
    print(f"Generating offline analysis for Track B: {track_b}")
    payload_b = AutomixEngine.generate_pure_offline_analysis(track_b)
    
    print("Computing transition payload...")
    engine = AutomixEngine(payload_a, payload_b)
    transition_payload = engine.compute_transition()
    
    print("Transition Payload:")
    print(json.dumps(transition_payload, indent=2))
    
    print("Rendering transition...")
    render_transition(track_a, track_b, transition_payload, out_path)
    
    print(f"Success! Mixed track saved to {out_path}")

if __name__ == "__main__":
    main()
