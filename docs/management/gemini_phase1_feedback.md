# Gemini — Phase 1 Feedback (paste into the next turn)

Paste the fenced block below into Gemini 3.1 Pro before asking for Phase 2.

---

```
Phase 1 was applied and reviewed against the real repo by running it on the
committed sample pair (tools/mixslice/samples/A__…/B__…). Three things were
genuinely correct: 24-bit / dynamic-SR output (verified 48000 Hz PCM_24),
grid-median BPM reporting (127.001 / 126.998), and removing the global 0.999/peak
ducking. But two defects were found — one serious — and have been FIXED. Read these
carefully, because the same mistakes would recur in Phase 2.

## BUG 1 (serious): the look-ahead limiter did not limit; the DITHER was hard-clipping.

`compute_limiter_gain` built the per-sample gain reduction, then ran:
    gain = minimum_filter1d(gain, window)
    gain = gaussian_filter1d(gain, sigma=window)
The gaussian AVERAGES each gain dip against the surrounding unity gain. At a sharp
transient the smoothed gain rises back toward 1.0, so the peak passes through
un-attenuated. Measured: the mix reached 1.177 at a transient. What actually
stopped the overs was `np.clip(...)` inside apply_tpdf_dither — i.e. plain HARD
CLIPPING, the exact artifact the limiter was meant to avoid. The validation claim
"peak capped at 1.0" was reporting the SYMPTOM of the bug (clipped to full scale),
not success.

Root cause + rule: any smoothing of a limiter gain curve MUST be re-clamped to the
per-sample requirement, or the ceiling is not guaranteed. A minimum-filter whose
window includes the center sample mathematically guarantees peak*gain <= ceiling;
a symmetric gaussian destroys that guarantee.

FIX APPLIED (now caps at 0.97 with real headroom, no hard clipping):
    req = np.minimum(1.0, threshold / np.maximum(peak_env, 1e-12))
    gain = minimum_filter1d(req, size=window)      # look-ahead attack
    gain = gaussian_filter1d(gain, sigma=window)   # soften zipper
    gain = np.minimum(gain, req)                   # RE-CLAMP -> guarantee ceiling
    return np.clip(gain, 0.0, 1.0)

## BUG 2: the stems-sum-to-mix invariant was broken.

The limiter was applied INDEPENDENTLY to out, trackA, trackB (three different gain
curves), so a_stem + b_stem no longer reconstructed the mix: max|a+b - mix| went
from ~3e-5 (1 LSB) to 0.366. This invariant is intentional and was previously
verified.

FIX APPLIED: derive ONE gain envelope from the mix and apply it identically to the
mix and both stems:
    g = compute_limiter_gain(out, out_sr)
    out *= g[:,None];  a_stem *= g[:,None];  b_stem *= g[:,None]
Now max|a+b - mix| = 5e-7 (dither floor).

## STILL-OPEN (don't reintroduce, address properly in Phase 2)

- The limiter is SAMPLE-peak, not true-peak. Labeling it "true-peak" is wrong.
  Real dBTP requires ~4x oversampling to find inter-sample peaks. Currently it
  leaves ~0.26 dB headroom (ceiling 0.97) as a proxy. Implement real dBTP in Phase 2.
- TPDF dither at 24-bit is inaudible (noise ~-144 dBFS); it's harmless but verify the
  dither amplitude is scaled to the OUTPUT bit depth's LSB, never the 16-bit LSB.

## VALIDATION RULES for every future change (the circular metric is banned)

1. Run on tools/mixslice/samples/A__…/B__… with --stems.
2. ALWAYS assert the invariant: max|trackA + trackB - mix| <= ~1e-6. If a DSP stage
   breaks it, that stage is wrong unless it's explicitly a mix-only effect.
3. For any clipping/limiting claim: assert the float peak BEFORE the integer write
   is <= ceiling. Do NOT infer "no clipping" from the written file's peak — hard
   clipping also produces peak == 1.0.
4. State the measured numbers, not "validated".

## PHASE 2 — proceed, carrying these invariants

#5 Three-band Linkwitz-Riley + bass-swap and #4 piecewise-linear drift warp.
Hard constraints:
- LR4 bands must sum flat: assert |(low+mid+high) - original| is ~0 before any
  crossfade logic. Prove it on a sample before building the swap.
- The bass swap is a mix-only operation; if you keep --stems meaningful, define
  explicitly how stems reconstruct the banded mix (or document that --stems is
  bypassed when multi-band is active — don't silently break invariant #2).
- The drift warp must remain anchored on rhythm.beats[] and stay deterministic;
  no real-time/Kalman. Show the warp path and a before/after beat-alignment number.
- Keep 64-bit float internally; keep the re-clamp discipline for ANY new gain stage.
Deliver unified diffs against the CURRENT render_transition.py (which already has
the Phase 1 fixes above), plus the per-change validation numbers from rule set above.
```
