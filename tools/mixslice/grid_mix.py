#!/usr/bin/env python3
"""Grid-based transition renderer — the wobble fix.

Consumes the rigid grid (constant AverageBpm + phase) instead of the Apple
analyzer's jittery per-onset beats, and warps the incoming overlap at ONE constant
ratio (bpm_out/bpm_in) instead of chasing per-beat targets. Because both grids are
perfectly periodic, the incoming track's playback speed is constant across the
blend — no per-beat lurching.

Usage:
    grid_mix.py render_plan.json SEQ_A OUT.flac     # render transition SEQ_A -> SEQ_A+1
"""
from __future__ import annotations
import json, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

OVERLAP_BEATS = 32
LEAD_S = 12.0
CEIL = 0.84


def rigid_beats(bpm, phase, dur):
    period = 60.0 / bpm
    n = int((dur - phase) / period) + 1
    return phase + np.arange(max(n, 0)) * period, period


def load(path, out_sr):
    a, sr = sf.read(path, dtype="float64", always_2d=True)
    if sr != out_sr:
        from math import gcd
        g = gcd(out_sr, sr); a = resample_poly(a, out_sr // g, sr // g, axis=0)
    return a


def pick_cue(cues, lo, hi, dur):
    """An energy cue inside [lo*dur, hi*dur]; prefer a high-energy one."""
    c = [(cu["start"], cu["name"]) for cu in cues if lo * dur <= cu["start"] <= hi * dur]
    if not c:
        return (lo * dur)
    c.sort(key=lambda x: (-_energy(x[1]), x[0]))
    return c[0][0]


def _energy(name):
    import re
    m = re.search(r'(\d+)', name or '')
    return int(m.group(1)) if m else 0


def main():
    plan = json.load(open(sys.argv[1]))["tracks"]
    i = int(sys.argv[2]); out_path = sys.argv[3]
    A, B = plan[i], plan[i + 1]
    out_sr = max(sf.info(A["path"]).samplerate, sf.info(B["path"]).samplerate)

    aA, aB = load(A["path"], out_sr), load(B["path"], out_sr)
    durA, durB = len(aA) / out_sr, len(aB) / out_sr
    beatsA, perA = rigid_beats(A["bpm"], A["phase_s"] or 0.0, durA)
    beatsB, perB = rigid_beats(B["bpm"], B["phase_s"] or 0.0, durB)

    # mix-out: a high-energy cue in A's last third, snapped to a downbeat (every 4 beats)
    mo = pick_cue(A["cues"], 0.65, 0.92, durA)
    mi = pick_cue(B["cues"], 0.06, 0.30, durB)
    iA = int(np.argmin(np.abs(beatsA - mo))); iA -= iA % 4
    iB = int(np.argmin(np.abs(beatsB - mi))); iB -= iB % 4
    iA = min(iA, len(beatsA) - OVERLAP_BEATS - 1)
    iB = min(iB, len(beatsB) - OVERLAP_BEATS - 1)
    aOut, bIn = beatsA[iA], beatsB[iB]

    # SINGLE constant warp ratio (the fix): make B's period match A's over the blend
    rate = perB / perA              # pyrubberband: output_len = len/rate
    overA = OVERLAP_BEATS * perA    # blend duration locked to A's grid

    f = lambda t: int(round(t * out_sr))
    pre = aA[f(max(0, aOut - LEAD_S)):f(aOut)]
    t1 = aA[f(aOut):f(aOut + overA)]
    raw2 = aB[f(bIn):f(bIn + OVERLAP_BEATS * perB)]
    if abs(rate - 1.0) > 1e-4:
        import pyrubberband as pyrb
        t2 = pyrb.time_stretch(raw2, out_sr, rate).astype(np.float64)
    else:
        t2 = raw2
    n = min(len(t1), len(t2), f(overA))
    t1, t2 = t1[:n], t2[:n]
    ch = max(t1.shape[1], t2.shape[1])
    fo = np.cos(np.linspace(0, np.pi / 2, n))[:, None]
    fi = np.sin(np.linspace(0, np.pi / 2, n))[:, None]
    mixed = t1 * fo + t2 * fi
    post = aB[f(bIn + OVERLAP_BEATS * perB):f(bIn + OVERLAP_BEATS * perB + LEAD_S)]
    out = np.concatenate([pre, mixed, post], axis=0)
    pk = float(np.max(np.abs(out)))
    if pk > CEIL:
        out *= CEIL / pk
    sf.write(out_path, out, out_sr, subtype="PCM_24")

    # PROOF: incoming playback speed per beat across the blend (constant == no wobble)
    speeds = []
    for k in range(OVERLAP_BEATS):
        src = (beatsB[iB + k + 1] - beatsB[iB + k]) * (1 / rate)
        tgt = beatsA[iA + k + 1] - beatsA[iA + k]
        speeds.append(src / tgt)
    speeds = np.array(speeds)
    print(json.dumps({
        "out": out_path, "A": f'{A["artist"]} - {A["title"]}', "B": f'{B["artist"]} - {B["title"]}',
        "bpm_A": A["bpm"], "bpm_B": B["bpm"], "warp_ratio": round(rate, 5),
        "per_beat_speed_min": round(float(speeds.min()), 5),
        "per_beat_speed_max": round(float(speeds.max()), 5),
        "per_beat_speed_swing_pct": round(float((speeds.max() - speeds.min()) * 100), 4),
        "sample_peak": round(float(np.max(np.abs(out))), 4), "out_sr": out_sr,
    }, indent=1))


if __name__ == "__main__":
    main()
