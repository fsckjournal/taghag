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

d = json.load(open("samples/B__mella_dee__realisation.analyzer.json"))
loudness = parse_t(d["loudness"]["shortTerm"])
sections = [float(s["start"]["value"])/s["start"]["timescale"] for s in d["structure"]["sections"]]
print("Sections:", sections[:5])

# Print average loudness for the first 5 sections
for i in range(min(5, len(sections)-1)):
    s_start = sections[i]
    s_end = sections[i+1]
    mask = (loudness[:, 0] >= s_start) & (loudness[:, 0] < s_end)
    avg_loud = np.mean(loudness[mask, 1]) if np.any(mask) else 0
    print(f"Section {i} ({s_start:.2f}s - {s_end:.2f}s): avg loudness = {avg_loud:.2f}")

