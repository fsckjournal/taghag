# Gemini 3.1 Pro — Mixer Optimization Prompt

Paste the fenced block below into Gemini 3.1 Pro. It will have the repo via your
AI Studio environment snapshot. The brief is deliberately heavy on ground-truth +
anti-hallucination guardrails because every prior AI pass on this failed by
inventing files/fields (e.g. `loudness.intervals.decibels`, which does not exist).

Tailoring choices baked in: (1) reality-check pass first; (2) Phase 1 = cheap
runnable wins with real diffs; (3) full DSP roadmap kept (multi-band, drift warp,
loudness cueing, vocal avoidance); (4) an explicit phase to wire the existing but
currently-disconnected scorer (`apple_handoff.py` + `advanced_cue_planner.py`)
into the renderer; (5) Roon/real-time explicitly deferred.

---

```
You are a senior audio-DSP + Python engineer optimizing a REAL, working codebase
(taghag). Goal: dramatically improve the quality of the automated beatmatched FLAC
mixer. Be concrete, runnable, and correct — not aspirational.

## NON-NEGOTIABLE RULES (prior AI attempts failed on exactly these)

1. VERIFY EVERYTHING AGAINST THE ACTUAL FILES. Do not trust any prose summary
   (including this one) over the source. Before proposing a change to a file,
   quote the relevant current lines. If you can't find a file/field, say so —
   never invent it.

2. DO NOT HALLUCINATE Apple's MusicUnderstanding API or the analyzer JSON schema.
   Ground every field name in the committed sample files:
     tools/mixslice/samples/A__mike_shannon__search_party.analyzer.json
     tools/mixslice/samples/B__mella_dee__realisation.analyzer.json
   (Prior attempts invented `loudness.intervals[].decibels`. It does NOT exist.
   The real keys are `loudness.momentary` / `loudness.shortTerm` (LUFS TimedValues)
   and `loudness.peak`. Confirm the actual shape from the sample JSON before using it.)

3. SCOPE DISCIPLINE. Optimize the MIX QUALITY of the offline renderer first.
   Roon integration, real-time streaming, and Squeezebox loopback are OUT OF SCOPE
   except as a final "future phase" note. No Kalman/PLL real-time DSP — offline,
   deterministic processing only.

## GROUND TRUTH (verify, then build on)

- The mixer is `tools/mixslice/render_transition.py` (~291 lines), STANDALONE.
  It does NOT import apple_handoff.py or advanced_cue_planner.py. Read it fully.
  Current behavior:
    * CLI: A.flac B.flac A.json B.json out.flac [--mixin-s --mixout-s
      --overlap-beats --click --stems]
    * From each analyzer JSON it uses ONLY: rhythm.beats[] (CMTime value/timescale
      = seconds), structure.sections[].start, and rhythm.beatsPerMinute (printed in
      the report only — NOT trusted for math).
    * Picks mix-out (default ~78% of A) and mix-in (default = B's section[1]),
      snaps each to nearest 32-beat section then nearest beat, aligns those two
      beats to the same output sample.
    * 32-beat equal-power (cos/sin) crossfade. Resamples both to 44100. Writes
      16-bit FLAC. If |grid drift| over the overlap > 6 ms, applies ONE global
      rubberband stretch ratio (over2/over1) to B's overlap; else no stretch.
    * Clip guard = whole-file scale by 0.999/peak.
    * Its `residual_beat_offset_ms` report metric is CIRCULAR (compares the two
      grids to each other; ~0 by construction when BPMs match) — it does NOT
      validate that beats land on real kicks. Treat it as an arithmetic check only.

- Analyzer JSON (per FLAC, from tools/cuecifer-analyzer/.build/.../cuecifer_analyzer):
  top-level keys rhythm (beatsPerMinute, beats[], bars[]), key, structure
  (sections=32-beat, phrases=8-beat, segments=16-beat), pace, loudness
  (integrated/momentary/shortTerm/peak), instrumentActivity (activity + ranges),
  structurePredictions. Times are CMTime value/timescale seconds; timescale = the
  file's sample rate (44100 or 48000), NOT fixed. `flags` are CMTime validity bits,
  NOT downbeats — downbeats are rhythm.bars / structure.sections.

- There is a SEPARATE, already-written scoring/cue pipeline that the renderer does
  NOT currently use: tools/taghag_import/apple_handoff.py (~127 lines, transition
  risk scoring), advanced_cue_planner.py (~510 lines), apple_derived_features.py
  (~326), mixonset.py (~369). Read these — they are the intended "brain" for
  auto-cue and auto-sequencing but are disconnected from render_transition.py.

- ESTABLISHED RULES (do not relitigate):
    * BPM = median beat interval of rhythm.beats[], NEVER any declared/tag field
      (analyzer header, Lexicon, or Rekordbox AverageBpm). If a header says 120 but
      the grid spacing is 125, the grid wins.
    * FLAC-native: analyze the FLAC master directly. "MIK" in this repo =
      rekordbox_mikcues_001.xml (energy cues only, no BPM/grid).
    * Many source masters are brickwalled at 0 dBFS — you CANNOT un-clip them; the
      renderer must only avoid ADDING clipping.

## KNOWN DEFECTS TO FIX (real, verified — prioritize by impact/effort)

1. Output is 16-bit @ 44.1k. Preserve native bit depth (24-bit) and the higher of
   the two sample rates; 64-bit float internally; triangular dither + noise shaping
   on requantize.
2. Whole-file 0.999/peak normalize quietens the solo sections. Replace with
   overlap-local gain handling / a look-ahead true-peak limiter that only acts where
   summed audio exceeds 0 dBFS.
3. Default mix-in = section[1] lands in sparse drum-only intros (audible "naked
   beat"). Replace with loudness/structure-driven cue selection (mix-in at
   end-of-intro / before the drop; mix-out at the outro dissolve), from
   loudness.shortTerm + structure — verify those fields' real shape first.
4. Single global rubberband ratio ignores intra-overlap tempo drift. Propose a
   piecewise-linear / DTW warp anchored on rhythm.beats[] across the overlap
   (NOT real-time Kalman).
5. Single full-spectrum equal-power fade muddies bass. Propose a 3-band
   Linkwitz-Riley split with a hard bass-swap on a downbeat + equal-power blends on
   mid/high. Justify filter order, crossover freqs, and phase summing.
6. No vocal-collision avoidance. Use the analyzer's real instrumentActivity vocal
   curve to detect/avoid two vocals overlapping in the blend; shift the anchor by
   whole bars if needed. Confirm the actual activity field shape from the sample JSON.
7. Report BPM uses the declared header — switch to grid median.

## WHAT TO PRODUCE

A. REALITY-CHECK PASS (do this first, cheap): list what you actually found in the
   files vs this brief. Explicitly flag anything I got wrong, any field that does
   NOT exist in the sample JSON, and any of the 7 defects that are already handled.
   Paste a real excerpt from a sample JSON for every analyzer field you intend to use.
B. A phased plan ordered by impact/effort, each item rated impact (H/M/L) +
   effort (S/M/L). Phase 1 = cheapest high-impact wins (likely #1, #2, #7).
C. For Phase 1 ONLY: actual unified diffs against render_transition.py that apply
   cleanly and keep the existing CLI + --stems/--click behavior working.
D. For EACH change, a concrete VALIDATION I can run — NOT the circular residual
   metric (e.g. "render the committed sample pair tools/mixslice/samples/A…/B…,
   confirm 24-bit via soundfile.info, confirm no inter-sample peak > -1 dBTP", or a
   specific listen-test).
E. Roadmap (no code yet) for Phases 2+: multi-band bass-swap (#5), drift warp (#4),
   loudness/structure auto-cue (#3), vocal avoidance (#6), THEN wiring the existing
   apple_handoff.py + advanced_cue_planner.py scorer into the renderer so mix-point
   and sequencing become automatic, and finally an offline CUE-sheet + single-FLAC
   pre-render (the only Roon path worth considering). Same impact/effort/validation
   framing for each.

Constraints: pure Python on numpy/scipy/soundfile/pyrubberband (already in the
venv); deterministic & offline; no new heavy deps (no Demucs/ONNX) unless you prove
the analyzer's existing curves can't do the job. If a proposal depends on a JSON
field, paste the real excerpt from the sample file that proves it exists.
```
