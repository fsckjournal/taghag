# Gemini — Phase 3 IMPLEMENTATION review (paste next turn). NOT green-lit for Phase 4.

Phase 3 runs and the DSP invariants still hold, but the auto-cue cost function is
unsound and your "validated / robust / complete" claim does not match the code.
Do not start Phase 4 until the cue logic is fixed and validated BY EAR.

## First: your reported validation is fabricated/stale again.
You reported mixout 325.24s / mixin 0.148s with "a -7.2 dB drop". The CURRENT code,
run on the same Booka->Patrice pair, actually selects mixout 283.75s / mixin 0.098s.
Re-run the current file and paste real output. Stop reporting numbers that the code
does not produce.

## BUG 1: base_cost is computed ONCE, outside the candidate loop (line ~178).
score_apple_transition is called a single time before the loop, so apple_handoff
contributes an IDENTICAL constant to every candidate — zero discrimination. The
whole point of wiring it in was per-candidate scoring. Either score per candidate
with real per-segment inputs, or admit it isn't influencing the choice.

## BUG 2: the cost terms are wildly uncalibrated, so one term silently dominates.
  - base_cost (apple): terms are _clip'd to [0,1], total ~O(1)
  - vocal_cost: (sum(v1*v2)/steps) * 100  -> O(0..100)
  - loud_cost: raw LUFS deltas          -> O(+-45)
  - naked_beat_penalty: max(0,-15-avg)*5 -> O(0..tens)
These are not comparable. Normalize EACH term to ~[0,1] (or dB-normalize) before
applying weights, otherwise "scoring" just means "whichever raw term is biggest wins."

## BUG 3: `loud_cost = t1_loud_drop - t2_loud_rise` rewards mixing into SILENCE.
t2_loud_rise = loudness(end) - loudness(start). A candidate at the track's quiet
start maximizes that rise, so `-t2_loud_rise` becomes a huge reward pulling the
mix-in to the quietest possible point — the exact naked-beat failure this phase
targets. Reward an intro that is ALREADY energetic and stable, not one with the
biggest rise from silence. Cap/normalize the rise.

## BUG 4: naked_beat threshold (-15 LUFS absolute) is mis-scaled.
Minimal/techno short-term loudness usually sits around -11 to -13 LUFS, so almost
nothing falls below -15 and the penalty rarely fires (near-uniform). Make it RELATIVE
to the track's own median short-term loudness (e.g. penalize if the mix-in's mean is
> 3 dB below the track median), not an absolute LUFS constant.

## BUG 5 (the real one): loudness != musical density.
Patrice/Glutes' intro measures -12.3 LUFS (essentially track-median) yet is musically
a kick-only "naked beat" — which is exactly why an earlier listen forced --mixin-s 60.6.
A loud lone kick is loud in LUFS. To actually detect a naked intro you must use
instrumentActivity density, not level: e.g. require that bass AND at least one of
{other/melodic, vocal} are active over the mix-in overlap, or score on the count of
simultaneously-active non-drum instruments. Loudness alone cannot fix the bug this
phase exists to fix.

## VALIDATION you must do (DSP-invariant checks do NOT validate cue quality)
1. Run current code; paste the ACTUAL chosen (mixout_s, mixin_s).
2. On Booka->Patrice, assert the planner does NOT pick a mix-in whose overlap is
   drum-only (check instrumentActivity), and ideally lands near Glutes' fill-out
   (~section 4 / ~60 s) that we already know sounds right.
3. LISTEN to the auto-cued render vs the known-good --mixin-s 60.6 render. If the
   auto choice sounds worse, the planner is not done.
4. Report measured terms per candidate for the winner and runner-up so the trade-off
   is auditable.

Keep the DSP invariants (they're fine): stems-sum exact in float, true-peak safe.
Phase 4 (playlist sequencing) stays blocked until 1-4 pass.
