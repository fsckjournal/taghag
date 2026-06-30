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
# check loudness around 0.148
for row in loudness[:10]:
    print(row)
