# Gemini — Phase 2 Feedback (paste into the next turn)

Phase 2 was reviewed by running it on the committed zero-stretch sample pair AND
on a freshly-analyzed drift pair (Booka Shade 124.94 → Patrice Bäumel 127.0, 242 ms
grid drift). Most of it is correct and a genuine improvement — but two claims do
not hold up under measurement, and the warp path has a regression the sample pair
can't catch.

## VERIFIED GOOD (keep)
- 24-bit / dynamic-SR output (48000 / PCM_24). ✓
- Crossover reconstruction is exact: max|low+mid+high - x| = 1.1e-16. ✓
  (Note: it's a *subtraction-complementary* crossover, NOT Linkwitz-Riley. Perfect
  reconstruction holds — which is what matters — so just stop calling it "LR4 /
  Linkwitz-Riley"; the band magnitude shapes aren't LR.)
- Banded-stems reconstruction in the zero-stretch path: max|a+b-mix| = 5e-7. ✓
- Bass-swap + per-band stem weighting is correct by construction. ✓
- The "Pre-integer float peak" diagnostic you added is exactly right — keep it.

## ISSUE 1 (claim is false): the "true-peak limiter" does NOT limit true peak.
Measured on the written output (4x oversample, then max-abs): TRUE peak = 1.00488
= +0.042 dBTP — OVER 0 dBFS, and ~1 dB over the -1 dBTP spec. The sample peak is
0.969 (fine), but inter-sample peaks exceed it.

Root cause: you oversample to DETECT the peak, but apply the gain at the NATIVE
rate. A per-native-sample gain does not constrain the inter-sample peak, because
the reconstructed peak between samples i and i+1 depends on both (differently-
gained) samples. Detection ≠ correction.

Fix (choose one):
  (a) Apply the limiter in the oversampled domain: compute req on the 4x signal,
      smooth + re-clamp there, multiply the 4x signal, then DECIMATE back (or
      derive a 4x gain curve and decimate the GAIN, then apply at native rate).
      Then re-measure 4x true-peak of the result to confirm <= ceiling.
  (b) If staying native-rate, treat it honestly as a SAMPLE-peak limiter and lower
      LIMIT_CEILING enough that measured true-peak <= -1 dBTP (empirically ~0.84
      on these masters). Don't label it "true-peak".
Validation rule: never claim a true-peak ceiling without measuring
`max(abs(resample_poly(written_mix, 4, 1)))` on the FILE you wrote.

## ISSUE 2 (regression, stretched path only): stems invariant degrades 200x.
Zero-stretch path: max|a+b-mix| = 5e-7. Stretched path: 1.2e-4, with 78% of frames
> 1e-5. Inaudible (~-78 dBFS) but it's a real, broad divergence introduced by the
warp branch, and it breaks the documented "stems sum to the mix at ~1 LSB" guarantee.
Likely pyrubberband.timemap_stretch returns float32 (its temp-file round-trip), and
the band-split arithmetic then accumulates inconsistently. Investigate: cast the
timemap_stretch output to float64 immediately, confirm t2_over is the SAME array
used for both `mixed` and `b_stem`, and re-measure. Do not consider Phase 2 done
until the stretched path also hits ~1e-6.

## VALIDATION RULES you must add (the sample pair hid both issues)
1. ALWAYS test a STRETCHED pair too — the committed sample pair is zero-drift, so
   it never exercises timemap_stretch. Use a >6 ms-drift pair every time.
2. Assert max|trackA+trackB-mix| <= 1e-6 in BOTH the stretched and unstretched paths.
3. For any peak/ceiling claim, measure 4x true-peak of the WRITTEN file, not the
   pre-write sample peak.
4. Report measured numbers, not "validated".

## STILL DESIGN CHOICES (the founder will pick, not bugs)
- Bass crossover at 250 Hz and bass-swap on beat 16 — fine defaults; expose as args.

## PHASE 3 — proceed only after Issues 1 & 2 are fixed and re-measured
Auto-cue from loudness.shortTerm + structure (end-of-intro / drop / outro-dissolve),
vocal-collision avoidance from instrumentActivity.activity.vocal, then wiring
apple_handoff.py + advanced_cue_planner.py into the renderer. Same invariants:
64-bit float internally, re-clamp every gain stage, stems-sum asserted in all paths,
deterministic, validate on a stretched pair. Diff against the CURRENT file.
