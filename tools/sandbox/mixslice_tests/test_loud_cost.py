import json
import numpy as np

def parse_t(arr):
    pts = []
    for item in arr:
        val = float(item.get("value", 0.0))
        t = item.get("time", {})
        ts = float(t.get("value", 0)) / max(1.0, float(t.get("timescale", 48000)))
        pts.append([ts, val])
    return np.array(pts)

d1 = json.load(open("samples/A__mike_shannon__search_party.analyzer.json"))
l1 = parse_t(d1["loudness"]["shortTerm"])
beats1 = np.array([float(b["value"])/b["timescale"] for b in d1["rhythm"]["beats"]])
sec1 = np.array([float(s["start"]["value"])/s["start"]["timescale"] for s in d1["structure"]["sections"]])

d2 = json.load(open("samples/B__mella_dee__realisation.analyzer.json"))
l2 = parse_t(d2["loudness"]["shortTerm"])
beats2 = np.array([float(b["value"])/b["timescale"] for b in d2["rhythm"]["beats"]])
sec2 = np.array([float(s["start"]["value"])/s["start"]["timescale"] for s in d2["structure"]["sections"]])

def nearest_beat(beats, t):
    i = int(np.argmin(np.abs(beats - t)))
    return i, float(beats[i])

nb = 32

print("T1 mixout candidates:")
dur1 = sec1[-1]
for s in sec1:
    if s >= dur1 * 0.70:
        i, b = nearest_beat(beats1, s)
        if i + nb < len(beats1):
            bend = beats1[i+nb]
            ls = np.interp(b, l1[:,0], l1[:,1])
            le = np.interp(bend, l1[:,0], l1[:,1])
            print(f"s={s:.2f} ls={ls:.2f} le={le:.2f} drop={le-ls:.2f}")

print("\nT2 mixin candidates:")
dur2 = sec2[-1]
for s in sec2:
    if s <= dur2 * 0.35:
        i, b = nearest_beat(beats2, s)
        if i + nb < len(beats2):
            bend = beats2[i+nb]
            ls = np.interp(b, l2[:,0], l2[:,1])
            le = np.interp(bend, l2[:,0], l2[:,1])
            mask = (l2[:,0] >= b) & (l2[:,0] <= bend)
            avg = np.mean(l2[mask, 1]) if np.any(mask) else 0
            print(f"s={s:.2f} ls={ls:.2f} le={le:.2f} rise={le-ls:.2f} avg={avg:.2f}")
