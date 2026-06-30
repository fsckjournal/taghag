import json
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from taghag_import.apple_handoff import score_apple_transition

def parse_t(arr):
    pts = []
    for item in arr:
        val = float(item.get("value", 0.0))
        t = item.get("time", {})
        ts = float(t.get("value", 0)) / max(1.0, float(t.get("timescale", 48000)))
        pts.append([ts, val])
    return np.array(pts)

def extract_apple_features(d: dict) -> dict[str, float]:
    features = {}
    if "loudness" in d and "integrated" in d["loudness"]:
        features["loudness_integrated"] = float(d["loudness"]["integrated"].get("value", 0.0))
    pace_vals = []
    if "pace" in d and "ranges" in d["pace"]:
        for p in d["pace"]["ranges"]:
            pace_vals.append(float(p.get("value", 0.0)))
    if pace_vals:
        features["pace_mean"] = float(np.mean(pace_vals))
        features["pace_volatility"] = float(np.std(pace_vals))
    vocals = []
    if "instrumentActivity" in d and "activity" in d["instrumentActivity"]:
        if "vocal" in d["instrumentActivity"]["activity"]:
            for v in d["instrumentActivity"]["activity"]["vocal"]:
                vocals.append(float(v.get("value", 0.0)))
    if vocals:
        features["vocal_intensity_mean"] = float(np.mean(vocals))
    features["bpm_agreement_score"] = 1.0 
    features["key_stable"] = True
    return features


d1 = json.load(open("samples/A__mike_shannon__search_party.analyzer.json"))
l1 = parse_t(d1["loudness"]["shortTerm"])
v1 = parse_t(d1.get("instrumentActivity", {}).get("activity", {}).get("vocal", []))
beats1 = np.array([float(b["value"])/b["timescale"] for b in d1["rhythm"]["beats"]])
sec1 = np.array([float(s["start"]["value"])/s["start"]["timescale"] for s in d1["structure"]["sections"]])
af1 = extract_apple_features(d1)

d2 = json.load(open("samples/B__mella_dee__realisation.analyzer.json"))
l2 = parse_t(d2["loudness"]["shortTerm"])
v2 = parse_t(d2.get("instrumentActivity", {}).get("activity", {}).get("vocal", []))
beats2 = np.array([float(b["value"])/b["timescale"] for b in d2["rhythm"]["beats"]])
sec2 = np.array([float(s["start"]["value"])/s["start"]["timescale"] for s in d2["structure"]["sections"]])
af2 = extract_apple_features(d2)

def nearest_beat(beats, t):
    i = int(np.argmin(np.abs(beats - t)))
    return i, float(beats[i])

nb = 32
dur1 = beats1[-1]
min_mixout = dur1 * 0.70
max_mixout = dur1 - (nb * 60.0 / 127.0)
mixout_cands = [s for s in sec1 if min_mixout <= s <= max_mixout]
if not mixout_cands:
    mixout_cands = [sec1[-2]]

dur2 = beats2[-1]
max_mixin = dur2 * 0.35
mixin_cands = [s for s in sec2 if s <= max_mixin]
if not mixin_cands:
    mixin_cands = [sec2[1]]

apple_score = score_apple_transition(af1, af2, from_segment={"role":"phrase"}, to_segment={"role":"phrase"})
base_cost = apple_score.total_cost

results = []
for s1 in mixout_cands:
    for s2 in mixin_cands:
        i1, beat1 = nearest_beat(beats1, s1)
        if i1 + nb >= len(beats1): continue
        over1_end = float(beats1[i1 + nb])
        
        i2, beat2 = nearest_beat(beats2, s2)
        if i2 + nb >= len(beats2): continue
        over2_end = float(beats2[i2 + nb])
        
        overlap_dur = min(over1_end - beat1, over2_end - beat2)
        steps = int(overlap_dur * 10) # 100ms
        if steps < 1: continue
        t_grid = np.linspace(0, overlap_dur, steps)
        
        v1_interp = np.interp(beat1 + t_grid, v1[:,0], v1[:,1])
        v2_interp = np.interp(beat2 + t_grid, v2[:,0], v2[:,1])
        vocal_cost = (np.sum(v1_interp * v2_interp) / steps) * 100.0
        
        l1_s = np.interp(beat1, l1[:,0], l1[:,1])
        l1_e = np.interp(over1_end, l1[:,0], l1[:,1])
        t1_loud_drop = l1_e - l1_s
        
        l2_s = np.interp(beat2, l2[:,0], l2[:,1])
        l2_e = np.interp(over2_end, l2[:,0], l2[:,1])
        t2_loud_rise = l2_e - l2_s
        
        mask2 = (l2[:,0] >= beat2) & (l2[:,0] <= over2_end)
        avg2 = np.mean(l2[mask2, 1]) if np.any(mask2) else -100.0
        
        # Avoid mixing into a completely silent or low-loudness region
        naked_beat_penalty = max(0, -15.0 - avg2) * 5.0 
        
        # Reward T1 dropping and T2 rising
        loud_cost = t1_loud_drop - t2_loud_rise
        
        total = base_cost + vocal_cost + loud_cost + naked_beat_penalty
        results.append({
            "s1": s1, "s2": s2,
            "drop": t1_loud_drop, "rise": t2_loud_rise,
            "avg2": avg2, "naked_pen": naked_beat_penalty,
            "vocal": vocal_cost, "total": total
        })

results.sort(key=lambda x: x["total"])
for i in range(5):
    print(results[i])
