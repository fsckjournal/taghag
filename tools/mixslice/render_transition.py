#!/usr/bin/env python3
"""Render one beatmatched crossfade transition between two FLAC tracks.

Vertical slice for the automated beatmatched mixer. Uses the native
cuecifer-analyzer JSON (FLAC-anchored beat grid + 32-beat section phrasing) to:

  1. pick a 32-beat "section" boundary in the outgoing track (mix-out) and the
     incoming track (mix-in), snapped to the nearest real beat;
  2. align those two anchor beats to the same output sample;
  3. micro-stretch the incoming overlap with rubberband ONLY if the two grids
     disagree enough to drift audibly (>STRETCH_TOL_MS over the overlap);
  4. equal-power (constant-energy) crossfade over the overlap;
  5. emit an excerpt FLAC plus a verification report (residual beat offset).

Grids are in seconds (CMTime value/timescale), so sample-rate differences
between the two files do not affect alignment math; audio is resampled to a
common rate before mixing.

Usage:
    render_transition.py T1.flac T2.flac T1.json T2.json OUT.flac [options]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

OUT_SR = 44100
OVERLAP_BEATS = 32          # one section / DJ phrase
LEAD_IN_S = 16.0            # outgoing groove before the blend
LEAD_OUT_S = 16.0           # incoming groove after the blend
STRETCH_TOL_MS = 6.0        # drift over the overlap above which we rubberband


@dataclass
class Grid:
    bpm: float
    beats: np.ndarray       # beat onsets, seconds
    sections: np.ndarray    # 32-beat section starts, seconds
    duration: float


def _ct_seconds(ct: dict) -> float:
    return ct["value"] / ct["timescale"]


def load_grid(path: str) -> Grid:
    d = json.load(open(path))
    rhythm = d["rhythm"]
    beats = np.array([_ct_seconds(b) for b in rhythm["beats"]], dtype=np.float64)
    sections = np.array(
        [_ct_seconds(s["start"]) for s in d["structure"]["sections"]],
        dtype=np.float64,
    )
    return Grid(
        bpm=float(rhythm["beatsPerMinute"]),
        beats=beats,
        sections=sections,
        duration=float(beats[-1]) if len(beats) else 0.0,
    )


def load_audio(path: str) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path, dtype="float64", always_2d=True)
    return audio, sr


def to_out_sr(audio: np.ndarray, sr: int) -> np.ndarray:
    if sr == OUT_SR:
        return audio
    from math import gcd

    g = gcd(OUT_SR, sr)
    return resample_poly(audio, OUT_SR // g, sr // g, axis=0)


def nearest_beat(beats: np.ndarray, t: float) -> tuple[int, float]:
    i = int(np.argmin(np.abs(beats - t)))
    return i, float(beats[i])


def pick_section(grid: Grid, target_s: float) -> float:
    """Section start nearest a target time (seconds)."""
    i = int(np.argmin(np.abs(grid.sections - target_s)))
    return float(grid.sections[i])


def equal_power_fades(n: int) -> tuple[np.ndarray, np.ndarray]:
    t = np.linspace(0.0, np.pi / 2, n, dtype=np.float64)
    return np.cos(t), np.sin(t)  # (fade_out, fade_in), sum of squares == 1


def sec_to_frame(t: float) -> int:
    return int(round(t * OUT_SR))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("t1_flac")
    ap.add_argument("t2_flac")
    ap.add_argument("t1_json")
    ap.add_argument("t2_json")
    ap.add_argument("out_flac")
    ap.add_argument("--mixout-s", type=float, default=None,
                    help="approx mix-out time in T1 (s); default ~78%% of T1")
    ap.add_argument("--mixin-s", type=float, default=None,
                    help="approx mix-in time in T2 (s); default = 2nd section")
    ap.add_argument("--overlap-beats", type=int, default=OVERLAP_BEATS)
    ap.add_argument("--click", action="store_true",
                    help="overlay panned clicks at each track's analyzer beats "
                         "(T1=left, T2=right) so you can HEAR if beats land on "
                         "the kicks and coincide in the overlap")
    ap.add_argument("--stems", action="store_true",
                    help="also write each track isolated on the mix timeline "
                         "(<out>.trackA.flac / .trackB.flac); they sum to the mix")
    args = ap.parse_args()

    g1 = load_grid(args.t1_json)
    g2 = load_grid(args.t2_json)

    # --- choose anchors on real section boundaries, snapped to a real beat ----
    mixout_target = args.mixout_s if args.mixout_s is not None else g1.duration * 0.78
    mixin_target = args.mixin_s if args.mixin_s is not None else (
        g2.sections[1] if len(g2.sections) > 1 else g2.sections[0]
    )
    a1_sec = pick_section(g1, mixout_target)
    a2_sec = pick_section(g2, mixin_target)
    i1, a1 = nearest_beat(g1.beats, a1_sec)
    i2, a2 = nearest_beat(g2.beats, a2_sec)

    nb = args.overlap_beats
    if i1 + nb >= len(g1.beats) or i2 + nb >= len(g2.beats):
        print("ERROR: not enough beats after anchor for the requested overlap",
              file=sys.stderr)
        return 2

    over1 = float(g1.beats[i1 + nb] - g1.beats[i1])   # overlap duration in T1
    over2 = float(g2.beats[i2 + nb] - g2.beats[i2])   # overlap duration in T2
    drift_ms = (over1 - over2) * 1000.0

    # --- load + resample to common rate ---------------------------------------
    a1_audio = to_out_sr(*load_audio(args.t1_flac))
    a2_audio = to_out_sr(*load_audio(args.t2_flac))
    ch = max(a1_audio.shape[1], a2_audio.shape[1])

    def fit_ch(x):
        if x.shape[1] == ch:
            return x
        return np.repeat(x, ch, axis=1) if x.shape[1] == 1 else x[:, :ch]

    a1_audio, a2_audio = fit_ch(a1_audio), fit_ch(a2_audio)

    # --- slice the regions ----------------------------------------------------
    pre_start = sec_to_frame(max(0.0, a1 - LEAD_IN_S))
    a1_anchor_f = sec_to_frame(a1)
    over_n = sec_to_frame(a1 + over1) - a1_anchor_f  # overlap length in frames (T1 grid)

    pre = a1_audio[pre_start:a1_anchor_f]
    t1_over = a1_audio[a1_anchor_f:a1_anchor_f + over_n]

    a2_anchor_f = sec_to_frame(a2)
    over2_n = sec_to_frame(a2 + over2) - a2_anchor_f
    t2_over_raw = a2_audio[a2_anchor_f:a2_anchor_f + over2_n]

    # micro-stretch incoming overlap to match outgoing overlap if it would drift
    stretched = False
    if abs(drift_ms) > STRETCH_TOL_MS and over2_n > 0:
        import pyrubberband as pyrb
        rate = over2 / over1  # output length = len/rate -> matches over1
        t2_over = pyrb.time_stretch(t2_over_raw, OUT_SR, rate)
        stretched = True
    else:
        t2_over = t2_over_raw

    # strict length matching: pad with zeros if too short, truncate if too long
    if len(t1_over) < over_n:
        t1_over = np.pad(t1_over, ((0, over_n - len(t1_over)), (0, 0)))
    else:
        t1_over = t1_over[:over_n]
        
    if len(t2_over) < over_n:
        t2_over = np.pad(t2_over, ((0, over_n - len(t2_over)), (0, 0)))
    else:
        t2_over = t2_over[:over_n]

    n = over_n

    fade_out, fade_in = equal_power_fades(n)
    mixed = t1_over * fade_out[:, None] + t2_over * fade_in[:, None]

    post_start = a2_anchor_f + over2_n
    post = a2_audio[post_start:post_start + sec_to_frame(LEAD_OUT_S)]

    out = np.concatenate([pre, mixed, post], axis=0)

    # --- isolated per-track stems on the mix timeline (a_stem + b_stem == out) -
    a_stem = b_stem = None
    if args.stems:
        p = len(pre)
        a_stem = np.zeros_like(out)
        b_stem = np.zeros_like(out)
        a_stem[:p] = pre
        a_stem[p:p + n] = t1_over * fade_out[:, None]
        b_stem[p:p + n] = t2_over * fade_in[:, None]
        b_stem[p + n:] = post

    # --- optional: panned click track to validate beats-vs-audio by ear -------
    if args.click and out.shape[1] >= 2:
        out_anchor_f = len(pre)

        def click_burst() -> np.ndarray:
            n = int(0.008 * OUT_SR)
            t = np.arange(n) / OUT_SR
            env = np.exp(-t * 600.0)
            return 0.5 * np.sin(2 * np.pi * 2000.0 * t) * env

        burst = click_burst()

        def stamp(beat_times, anchor, lo, hi, chan, stretch=1.0):
            for tb in beat_times:
                rel = tb - anchor
                if rel < lo or rel > hi:
                    continue
                f = out_anchor_f + int(round(rel * stretch * OUT_SR))
                end = min(f + len(burst), len(out))
                if 0 <= f < len(out):
                    out[f:end, chan] += burst[: end - f]

        # T1 beats over [lead-in .. end of overlap] on the LEFT channel
        stamp(g1.beats, a1, -(LEAD_IN_S), over1 + 1e-3, 0)
        # T2 beats over [overlap .. lead-out] on the RIGHT channel
        s = (over1 / over2) if stretched else 1.0
        stamp(g2.beats, a2, -1e-3, over2 + LEAD_OUT_S, 1, stretch=s)

    # guard against clipping from summed energy (one scale across mix + stems
    # so the two isolated stems still sum exactly to the written mix)
    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    scale = 0.999 / peak if peak > 1.0 else 1.0
    out = out * scale

    sf.write(args.out_flac, out, OUT_SR)

    stem_paths: list[str] = []
    if a_stem is not None:
        base = args.out_flac[:-5] if args.out_flac.lower().endswith(".flac") else args.out_flac
        for tag, stem in (("trackA", a_stem), ("trackB", b_stem)):
            path = f"{base}.{tag}.flac"
            sf.write(path, stem * scale, OUT_SR)
            stem_paths.append(path)

    # --- verification: residual beat offset across the overlap ----------------
    # map T1 and T2 beats inside the overlap onto the output timeline and report
    # the largest disagreement (after alignment + optional stretch).
    out_anchor = len(pre)  # output frame where both anchors coincide
    res = []
    for k in range(nb + 1):
        t1b = (g1.beats[i1 + k] - a1)              # seconds from anchor (T1)
        t2b = (g2.beats[i2 + k] - a2)              # seconds from anchor (T2)
        if stretched:
            t2b *= over1 / over2                    # apply the same stretch
        res.append((t2b - t1b) * 1000.0)
    res = np.array(res)

    report = {
        "out_file": args.out_flac,
        "t1_bpm": g1.bpm, "t2_bpm": g2.bpm,
        "mixout_anchor_s": round(a1, 3), "mixin_anchor_s": round(a2, 3),
        "overlap_beats": nb,
        "overlap_dur_t1_s": round(over1, 4), "overlap_dur_t2_s": round(over2, 4),
        "grid_drift_over_overlap_ms": round(drift_ms, 3),
        "stretched": stretched,
        "residual_beat_offset_ms": {
            "max_abs": round(float(np.max(np.abs(res))), 3),
            "mean_abs": round(float(np.mean(np.abs(res))), 3),
            "final_beat": round(float(res[-1]), 3),
        },
        "excerpt_seconds": round(len(out) / OUT_SR, 2),
        "out_sr": OUT_SR, "channels": ch, "peak": round(peak, 4),
        "stems": stem_paths,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
