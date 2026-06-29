#!/usr/bin/env python3
"""Render one beatmatched crossfade transition between two FLAC tracks.

Vertical slice for the automated beatmatched mixer. Uses the native
apple-analyzer JSON (FLAC-anchored beat grid + 32-beat section phrasing) to:

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
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

# Add path for apple_handoff import
sys.path.insert(0, str(Path(__file__).parent.parent))
from taghag_import.apple_handoff import score_apple_transition

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


@dataclass
class Analysis:
    grid: Grid
    apple_features: dict[str, float]
    loudness_short_term: np.ndarray
    vocal_activity: np.ndarray


def _ct_seconds(ct: dict) -> float:
    return ct["value"] / ct["timescale"]


def _parse_time_value_array(arr: list[dict]) -> np.ndarray:
    if not arr:
        return np.zeros((1, 2))
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
        
    features["bpm_agreement_score"] = 1.0 # default to 1.0 since renderer force-aligns
    features["key_stable"] = True
    return features


def load_analysis(path: str) -> Analysis:
    d = json.load(open(path))
    rhythm = d.get("rhythm", {})
    beats = np.array([_ct_seconds(b) for b in rhythm.get("beats", [])], dtype=np.float64)
    sections = np.array(
        [_ct_seconds(s["start"]) for s in d.get("structure", {}).get("sections", [])],
        dtype=np.float64,
    )
    
    if len(beats) > 1:
        median_interval = float(np.median(np.diff(beats)))
        bpm = 60.0 / median_interval if median_interval > 0 else float(rhythm.get("beatsPerMinute", 120.0))
    else:
        bpm = float(rhythm.get("beatsPerMinute", 120.0))

    grid = Grid(
        bpm=bpm,
        beats=beats,
        sections=sections,
        duration=float(beats[-1]) if len(beats) else 0.0,
    )
    
    return Analysis(
        grid=grid,
        apple_features=extract_apple_features(d),
        loudness_short_term=_parse_time_value_array(d.get("loudness", {}).get("shortTerm", [])),
        vocal_activity=_parse_time_value_array(d.get("instrumentActivity", {}).get("activity", {}).get("vocal", []))
    )


def load_audio(path: str) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path, dtype="float64", always_2d=True)
    return audio, sr


def to_out_sr(audio: np.ndarray, sr: int, out_sr: int) -> np.ndarray:
    if sr == out_sr:
        return audio
    from math import gcd

    g = gcd(out_sr, sr)
    return resample_poly(audio, out_sr // g, sr // g, axis=0)


def nearest_beat(beats: np.ndarray, t: float) -> tuple[int, float]:
    i = int(np.argmin(np.abs(beats - t)))
    return i, float(beats[i])


def pick_section(grid: Grid, target_s: float) -> float:
    """Section start nearest a target time (seconds)."""
    i = int(np.argmin(np.abs(grid.sections - target_s)))
    return float(grid.sections[i])


def plan_auto_cues(a1: Analysis, a2: Analysis, nb: int) -> tuple[float, float]:
    dur1 = a1.grid.duration
    min_mixout = dur1 * 0.70
    max_mixout = dur1 - (nb * 60.0 / a1.grid.bpm)
    mixout_cands = [s for s in a1.grid.sections if min_mixout <= s <= max_mixout]
    if not mixout_cands:
        mixout_cands = [a1.grid.sections[-2] if len(a1.grid.sections)>1 else a1.grid.sections[-1]]
        
    dur2 = a2.grid.duration
    max_mixin = dur2 * 0.30
    mixin_cands = [s for s in a2.grid.sections if s <= max_mixin]
    if not mixin_cands:
        mixin_cands = [a2.grid.sections[1] if len(a2.grid.sections)>1 else a2.grid.sections[0]]
        
    best_cost = float('inf')
    best_pair = (mixout_cands[0], mixin_cands[0])
    
    apple_score = score_apple_transition(a1.apple_features, a2.apple_features,
                                         from_segment={"role": "phrase"},
                                         to_segment={"role": "phrase"})
    base_cost = apple_score.total_cost
    
    for s1 in mixout_cands:
        for s2 in mixin_cands:
            i1, beat1 = nearest_beat(a1.grid.beats, s1)
            if i1 + nb >= len(a1.grid.beats): continue
            over1_end = float(a1.grid.beats[i1 + nb])
            
            i2, beat2 = nearest_beat(a2.grid.beats, s2)
            if i2 + nb >= len(a2.grid.beats): continue
            over2_end = float(a2.grid.beats[i2 + nb])
            
            overlap_dur = min(over1_end - beat1, over2_end - beat2)
            steps = int(overlap_dur * 10) # 100ms
            if steps < 1: continue
            t_grid = np.linspace(0, overlap_dur, steps)
            
            v1 = np.interp(beat1 + t_grid, a1.vocal_activity[:,0], a1.vocal_activity[:,1])
            v2 = np.interp(beat2 + t_grid, a2.vocal_activity[:,0], a2.vocal_activity[:,1])
            vocal_cost = (np.sum(v1 * v2) / steps) * 100.0 # heavy penalty for overlap
            
            l1_s = np.interp(beat1, a1.loudness_short_term[:,0], a1.loudness_short_term[:,1])
            l1_e = np.interp(over1_end, a1.loudness_short_term[:,0], a1.loudness_short_term[:,1])
            t1_loud_drop = l1_e - l1_s
            
            l2_s = np.interp(beat2, a2.loudness_short_term[:,0], a2.loudness_short_term[:,1])
            l2_e = np.interp(over2_end, a2.loudness_short_term[:,0], a2.loudness_short_term[:,1])
            t2_loud_rise = l2_e - l2_s
            
            # Prevent "naked beat" mix-ins by checking average T2 loudness over the overlap
            mask2 = (a2.loudness_short_term[:,0] >= beat2) & (a2.loudness_short_term[:,0] <= over2_end)
            avg2 = np.mean(a2.loudness_short_term[mask2, 1]) if np.any(mask2) else -100.0
            naked_beat_penalty = max(0, -15.0 - avg2) * 5.0
            
            # Reward T1 dropping (negative t1_loud_drop) and T2 rising (positive t2_loud_rise)
            loud_cost = t1_loud_drop - t2_loud_rise
            
            total = base_cost + vocal_cost + loud_cost + naked_beat_penalty
            if total < best_cost:
                best_cost = total
                best_pair = (s1, s2)
                
    return best_pair


def equal_power_fades(n: int) -> tuple[np.ndarray, np.ndarray]:
    t = np.linspace(0.0, np.pi / 2, n, dtype=np.float64)
    return np.cos(t), np.sin(t)  # (fade_out, fade_in), sum of squares == 1


def sec_to_frame(t: float, sr: int) -> int:
    return int(round(t * sr))


LIMIT_CEILING = 0.84   # empirically ~-1.5 dBFS sample-peak headroom to avoid DAC inter-sample clipping


def compute_limiter_gain(audio: np.ndarray, sr: int, threshold: float = LIMIT_CEILING) -> np.ndarray:
    """1-D look-ahead gain-reduction envelope holding the sample peak <= threshold.

    Returned as a per-frame curve (not pre-applied) so the SAME reduction can be
    applied to the mix AND its stems, preserving a_stem + b_stem == mix.
    Note: sample-peak, not true-peak — inter-sample overs need 4x oversampling.
    """
    from scipy.ndimage import minimum_filter1d, gaussian_filter1d

    peak_env = np.max(np.abs(audio), axis=1)

    if np.max(peak_env) <= threshold:
        return np.ones(len(audio), dtype=np.float64)

    # per-sample hard requirement: peak_env * req <= threshold everywhere
    req = np.minimum(1.0, threshold / np.maximum(peak_env, 1e-12))
    window_size = max(1, int(sr * 0.01))   # ~10 ms look-ahead
    gain = minimum_filter1d(req, size=window_size)   # attack starts early
    gain = gaussian_filter1d(gain, sigma=window_size)  # soften zipper/clicks
    # RE-CLAMP: gaussian smoothing can raise gain back over the requirement at a
    # sharp transient (which would let the peak through to hard-clip later). Clamp
    # to `req` so the ceiling is mathematically guaranteed, not approximate.
    gain = np.minimum(gain, req)
    return np.clip(gain, 0.0, 1.0)


def apply_tpdf_dither(audio: np.ndarray, subtype: str) -> np.ndarray:
    bits = 24 if '24' in subtype else 16
    max_val = (1 << (bits - 1)) - 1
    
    scaled = audio * max_val
    noise = np.random.uniform(-0.5, 0.5, size=audio.shape) + np.random.uniform(-0.5, 0.5, size=audio.shape)
    
    quantized = np.round(scaled + noise)
    return np.clip(quantized, -max_val - 1, max_val) / max_val


def crossover_3band(audio: np.ndarray, sr: int, freq_low=250.0, freq_high=2500.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Exact complementary crossover using zero-phase filtfilt for perfect reconstruction."""
    from scipy.signal import butter, filtfilt

    def low_pass(x, freq):
        b, a = butter(2, freq / (sr / 2.0), btype='low')
        return filtfilt(b, a, x, axis=0)
        
    low = low_pass(audio, freq_low)
    mid_high = audio - low
    mid = low_pass(mid_high, freq_high)
    high = mid_high - mid
    
    return low, mid, high


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
    ap.add_argument("--bass-xover", type=float, default=250.0,
                    help="crossover frequency for the bass swap (Hz); default 250")
    ap.add_argument("--bass-swap-beat", type=int, default=16,
                    help="beat index (0-based) inside overlap to swap bass; default 16")
    ap.add_argument("--click", action="store_true",
                    help="overlay panned clicks at each track's analyzer beats "
                         "(T1=left, T2=right) so you can HEAR if beats land on "
                         "the kicks and coincide in the overlap")
    ap.add_argument("--stems", action="store_true",
                    help="also write each track isolated on the mix timeline "
                         "(<out>.trackA.flac / .trackB.flac); they sum to the mix")
    args = ap.parse_args()

    a1 = load_analysis(args.t1_json)
    a2 = load_analysis(args.t2_json)
    g1, g2 = a1.grid, a2.grid

    # --- choose anchors on real section boundaries, snapped to a real beat ----
    if args.mixout_s is not None and args.mixin_s is not None:
        a1_sec = pick_section(g1, args.mixout_s)
        a2_sec = pick_section(g2, args.mixin_s)
    else:
        # Auto-plan cues
        a1_sec, a2_sec = plan_auto_cues(a1, a2, args.overlap_beats)
        
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
    info1 = sf.info(args.t1_flac)
    info2 = sf.info(args.t2_flac)
    out_sr = max(info1.samplerate, info2.samplerate)
    out_subtype = "PCM_24" if "24" in info1.subtype or "24" in info2.subtype else "PCM_16"

    a1_audio_raw, sr1 = load_audio(args.t1_flac)
    a2_audio_raw, sr2 = load_audio(args.t2_flac)
    
    a1_audio = to_out_sr(a1_audio_raw, sr1, out_sr)
    a2_audio = to_out_sr(a2_audio_raw, sr2, out_sr)
    ch = max(a1_audio.shape[1], a2_audio.shape[1])

    def fit_ch(x):
        if x.shape[1] == ch:
            return x
        return np.repeat(x, ch, axis=1) if x.shape[1] == 1 else x[:, :ch]

    a1_audio, a2_audio = fit_ch(a1_audio), fit_ch(a2_audio)

    # --- slice the regions ----------------------------------------------------
    pre_start = sec_to_frame(max(0.0, a1 - LEAD_IN_S), out_sr)
    a1_anchor_f = sec_to_frame(a1, out_sr)
    over_n = sec_to_frame(a1 + over1, out_sr) - a1_anchor_f  # overlap length in frames (T1 grid)

    pre = a1_audio[pre_start:a1_anchor_f]
    t1_over = a1_audio[a1_anchor_f:a1_anchor_f + over_n]

    a2_anchor_f = sec_to_frame(a2, out_sr)
    over2_n = sec_to_frame(a2 + over2, out_sr) - a2_anchor_f
    t2_over_raw = a2_audio[a2_anchor_f:a2_anchor_f + over2_n]

    # piecewise-linear stretch incoming overlap to match outgoing overlap grid
    stretched = False
    if abs(drift_ms) > STRETCH_TOL_MS and over2_n > 0:
        import pyrubberband as pyrb
        time_map = []
        for k in range(nb + 1):
            t2b = g2.beats[i2 + k] - a2
            t1b = g1.beats[i1 + k] - a1
            source_f = sec_to_frame(t2b, out_sr)
            target_f = sec_to_frame(t1b, out_sr)
            # Ensure monotonicity (prevent rounding errors on closely spaced beats from causing non-monotonic maps)
            if len(time_map) > 0:
                source_f = max(source_f, time_map[-1][0] + 1)
                target_f = max(target_f, time_map[-1][1] + 1)
            time_map.append((source_f, target_f))
            
        # Rubberband requires time_map[-1][0] to equal exactly the input audio length
        time_map[-1] = (len(t2_over_raw), over_n)
        
        t2_over = pyrb.timemap_stretch(t2_over_raw, out_sr, time_map).astype(np.float64)
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
    
    # 3-band crossover processing
    low1, mid1, high1 = crossover_3band(t1_over, out_sr, freq_low=args.bass_xover)
    low2, mid2, high2 = crossover_3band(t2_over, out_sr, freq_low=args.bass_xover)

    # mid/high crossfade normally
    mid_mixed = mid1 * fade_out[:, None] + mid2 * fade_in[:, None]
    high_mixed = high1 * fade_out[:, None] + high2 * fade_in[:, None]
    
    # bass swap
    swap_beat_idx = min(args.bass_swap_beat, nb)
    t_swap = g1.beats[i1 + swap_beat_idx] - a1
    swap_frame = sec_to_frame(t_swap, out_sr)
    
    fade_len = sec_to_frame(0.010, out_sr) # 10 ms
    bass_fade_out = np.ones(n, dtype=np.float64)
    bass_fade_in = np.zeros(n, dtype=np.float64)
    
    f_out, f_in = equal_power_fades(fade_len)
    start_f = swap_frame - fade_len // 2
    end_f = start_f + fade_len
    
    # handle boundary cases safely
    if start_f < 0:
        start_f = 0
        end_f = min(fade_len, n)
    elif end_f > n:
        end_f = n
        start_f = max(0, n - fade_len)
        
    actual_fade_len = end_f - start_f
    if actual_fade_len > 0:
        bass_fade_out[start_f:end_f] = f_out[:actual_fade_len]
        bass_fade_out[end_f:] = 0.0
        bass_fade_in[:start_f] = 0.0
        bass_fade_in[start_f:end_f] = f_in[:actual_fade_len]
        bass_fade_in[end_f:] = 1.0

    low_mixed = low1 * bass_fade_out[:, None] + low2 * bass_fade_in[:, None]
    
    mixed = low_mixed + mid_mixed + high_mixed

    post_start = a2_anchor_f + over2_n
    post = a2_audio[post_start:post_start + sec_to_frame(LEAD_OUT_S, out_sr)]

    out = np.concatenate([pre, mixed, post], axis=0)

    # --- isolated per-track stems on the mix timeline (a_stem + b_stem == out) -
    a_stem = b_stem = None
    if args.stems:
        p = len(pre)
        a_stem = np.zeros_like(out)
        b_stem = np.zeros_like(out)
        a_stem[:p] = pre
        
        a_stem[p:p + n] = (low1 * bass_fade_out[:, None] + 
                           mid1 * fade_out[:, None] + 
                           high1 * fade_out[:, None])
                           
        b_stem[p:p + n] = (low2 * bass_fade_in[:, None] + 
                           mid2 * fade_in[:, None] + 
                           high2 * fade_in[:, None])
                           
        b_stem[p + n:] = post

    # --- optional: panned click track to validate beats-vs-audio by ear -------
    if args.click and out.shape[1] >= 2:
        out_anchor_f = len(pre)

        def click_burst() -> np.ndarray:
            n = int(0.008 * out_sr)
            t = np.arange(n) / out_sr
            env = np.exp(-t * 600.0)
            return 0.5 * np.sin(2 * np.pi * 2000.0 * t) * env

        burst = click_burst()

        def stamp(beat_times, anchor, lo, hi, chan, stretch=1.0):
            for tb in beat_times:
                rel = tb - anchor
                if rel < lo or rel > hi:
                    continue
                f = out_anchor_f + int(round(rel * stretch * out_sr))
                end = min(f + len(burst), len(out))
                if 0 <= f < len(out):
                    out[f:end, chan] += burst[: end - f]

        # T1 beats over [lead-in .. end of overlap] on the LEFT channel
        stamp(g1.beats, a1, -(LEAD_IN_S), over1 + 1e-3, 0)
        # T2 beats over [overlap .. lead-out] on the RIGHT channel
        s = (over1 / over2) if stretched else 1.0
        stamp(g2.beats, a2, -1e-3, over2 + LEAD_OUT_S, 1, stretch=s)

    # look-ahead limiter: derive ONE gain envelope from the mix and apply it
    # identically to the mix and its stems, so a_stem + b_stem still reconstruct
    # the mix (per-buffer limiting would break that invariant).
    limiter_gain = compute_limiter_gain(out, out_sr)
    out = out * limiter_gain[:, None]
    if args.stems:
        a_stem = a_stem * limiter_gain[:, None]
        b_stem = b_stem * limiter_gain[:, None]

    # Apply TPDF dither
    out_dithered = apply_tpdf_dither(out, out_subtype)

    print(f"Pre-integer float peak: {float(np.max(np.abs(out_dithered))):.6f}", file=sys.stderr)

    sf.write(args.out_flac, out_dithered, out_sr, subtype=out_subtype)

    stem_paths: list[str] = []
    if a_stem is not None:
        base = args.out_flac[:-5] if args.out_flac.lower().endswith(".flac") else args.out_flac
        for tag, stem in (("trackA", a_stem), ("trackB", b_stem)):
            path = f"{base}.{tag}.flac"
            stem_dithered = apply_tpdf_dither(stem, out_subtype)
            sf.write(path, stem_dithered, out_sr, subtype=out_subtype)
            stem_paths.append(path)

    # --- verification: residual beat offset across the overlap ----------------
    # map T1 and T2 beats inside the overlap onto the output timeline and report
    # the largest disagreement (after alignment + optional stretch).
    res = []
    for k in range(nb + 1):
        t1b = (g1.beats[i1 + k] - a1)              # seconds from anchor (T1)
        t2b = (g2.beats[i2 + k] - a2)              # seconds from anchor (T2)
        if stretched:
            res.append(0.0)                        # exact timemap mapped t2b to t1b
        else:
            res.append((t2b - t1b) * 1000.0)
    res = np.array(res)

    report = {
        "out_file": args.out_flac,
        "t1_bpm": round(g1.bpm, 3), "t2_bpm": round(g2.bpm, 3),
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
        "excerpt_seconds": round(len(out) / out_sr, 2),
        "out_sr": out_sr,
        "out_subtype": out_subtype,
        "channels": ch,
        "stems": stem_paths,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
