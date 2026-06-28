#!/usr/bin/env python3
"""Chain the render plan into ONE continuous FLAC + CUE sheet (the Roon deliverable).

Streaming: holds at most two tracks in RAM, appends each segment to the output as it
goes, so a 200-track / 6-hour mix uses bounded memory. Each track plays its body at
its native tempo; only the ~32-beat blend into the next track is warped (single
constant ratio = no wobble) and equal-power crossfaded.

    chain_mix.py render_plan.json OUT.flac [MAX_TRACKS]
"""
from __future__ import annotations
import json, os, re, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

OVERLAP = 32          # beats
INTRO_SKIP_S = 8.0    # how far into track 0 to start
CEIL = 0.84


def energy(name):
    m = re.search(r'(\d+)', name or ''); return int(m.group(1)) if m else 0


def pick_cue(cues, lo, hi, dur, default):
    c = [(cu["start"], cu["name"]) for cu in cues if lo * dur <= cu["start"] <= hi * dur]
    if not c:
        return default
    c.sort(key=lambda x: (-energy(x[1]), x[0]))
    return c[0][0]


def load(path, out_sr):
    a, sr = sf.read(path, dtype="float64", always_2d=True)
    if sr != out_sr:
        from math import gcd
        g = gcd(out_sr, sr); a = resample_poly(a, out_sr // g, sr // g, axis=0)
    return a


def cue_time(frames, sr):
    t = frames / sr; m = int(t // 60); s = t - 60 * m; fr = int(round((s - int(s)) * 75))
    return f"{m:02d}:{int(s):02d}:{fr:02d}"


def main():
    plan = json.load(open(sys.argv[1]))["tracks"]
    out_path = sys.argv[2]
    if len(sys.argv) > 3:
        plan = plan[:int(sys.argv[3])]
    out_sr = 44100
    ch = 2
    f = lambda t: int(round(t * out_sr))
    fade = lambda n: (np.cos(np.linspace(0, np.pi/2, n))[:, None], np.sin(np.linspace(0, np.pi/2, n))[:, None])

    snk = sf.SoundFile(out_path, 'w', out_sr, ch, subtype='PCM_24')
    cue = ['FILE "%s" WAVE' % os.path.basename(out_path)]
    pos = 0          # output frame cursor
    carry = None     # (audio, mixout_time_s, period_s) of the pending outgoing track

    def write(seg):
        nonlocal pos
        if seg.shape[1] != ch:
            seg = np.repeat(seg, ch, axis=1) if seg.shape[1] == 1 else seg[:, :ch]
        pk = float(np.max(np.abs(seg))) if len(seg) else 0.0
        if pk > 1.0:
            seg = seg * (CEIL / pk)
        snk.write(seg); pos += len(seg)

    def add_cue(idx, frame, t):
        n = idx + 1
        cue.append("  TRACK %02d AUDIO" % n)
        cue.append('    TITLE "%s"' % t["title"].replace('"', "'"))
        cue.append('    PERFORMER "%s"' % t["artist"].replace('"', "'"))
        cue.append("    INDEX 01 %s" % cue_time(frame, out_sr))

    for i, t in enumerate(plan):
        if not t.get("bpm") or not os.path.exists(t["path"]):
            continue
        a = load(t["path"], out_sr); dur = len(a) / out_sr
        per = 60.0 / t["bpm"]; phase = t["phase_s"] or 0.0
        beats = phase + np.arange(int((dur - phase) / per) + 1) * per

        def snap(target):
            j = int(np.argmin(np.abs(beats - target))); return max(0, j - j % 4)

        last = (i == len(plan) - 1)
        in_t = pick_cue(t["cues"], 0.05, 0.30, dur, beats[snap(INTRO_SKIP_S)])
        out_t = pick_cue(t["cues"], 0.65, 0.92, dur, dur - OVERLAP * per - 4) if not last else dur
        j_in = snap(in_t); j_out = snap(out_t)
        j_in = min(j_in, max(0, len(beats) - OVERLAP - 1))
        in_beat = beats[j_in]

        # --- blend the previous outgoing track into THIS track's mix-in ---
        if carry is not None:
            pa, a_out, a_per = carry
            n = f(OVERLAP * a_per)
            t1 = pa[f(a_out):f(a_out) + n]
            raw2 = a[f(in_beat):f(in_beat) + f(OVERLAP * per)]
            rate = per / a_per
            t2 = (__import__("pyrubberband").time_stretch(raw2, out_sr, rate).astype(np.float64)
                  if abs(rate - 1.0) > 1e-4 else raw2)
            m = min(len(t1), len(t2), n)
            fo, fi = fade(m)
            add_cue(i, pos, t)            # the new track "starts" at the blend-in
            write(t1[:m] * fo + t2[:m] * fi)
            body_start = in_beat + OVERLAP * per
        else:
            add_cue(i, pos, t)
            body_start = beats[snap(INTRO_SKIP_S)]

        # --- this track's solo body (native tempo) ---
        body_end = dur if last else (beats[j_out] if j_out > j_in else dur)
        write(a[f(body_start):f(body_end)])
        carry = None if last else (a, beats[j_out], per)

    snk.close()
    open(out_path.rsplit('.', 1)[0] + '.cue', 'w').write("\n".join(cue) + "\n")
    print(json.dumps({"out": out_path, "cue": out_path.rsplit('.', 1)[0] + '.cue',
                      "tracks": (len(cue) - 1) // 4 if False else sum(1 for x in cue if x.startswith("  TRACK")),
                      "duration_min": round(pos / out_sr / 60, 1)}, indent=1))


if __name__ == "__main__":
    main()
