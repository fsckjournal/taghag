# Gemini — Phase 3 answers + Phase 2 status correction (paste next turn)

## Phase 2 status — corrected (your "invariants hold strictly in both paths" is overstated)

Re-measured. The ceiling=0.84 and the timemap float64 cast both landed and help:
- True-peak is now SAFE: -0.18 dBTP (zero-stretch) / -0.32 dBTP (stretched) — under 0 dBFS,
  no inter-sample clipping. (Still not the -1 dBTP target, but acceptable. If you want
  true -1 dBTP, limit in the oversampled domain; otherwise stop calling it "true-peak".)
- The stems MATH is now exact: pre-dither max|a+b-out| = 3.3e-16 in BOTH paths. Good — the
  float64 cast fixed the real precision bug.

BUT the WRITTEN stretched stems still diverge 1.22e-4 (vs 4.8e-7 zero-stretch). Root cause
(measured, not guessed): the limiter gain is sized for the MIX, so in cancellation regions
the INDIVIDUAL stems exceed 0 dBFS (the masters are brickwalled at 0 dBFS), and
apply_tpdf_dither's np.clip hard-clips those stem samples on the 24-bit write while the
in-range mix doesn't. So the invariant holds in float and breaks only at the PCM-write
boundary for out-of-range stems. Either (a) write the diagnostic stems as floating-point
(soundfile FLOAT subtype, no clip), or (b) document that stems may individually exceed
0 dBFS and clip — they're a diagnostic, the MIX is the deliverable. Don't claim "strict".

## Q1 (section roles): evaluate candidate sections by LOUDNESS SHAPE — do NOT build a role guesser.

The analyzer JSON has no role field (correct). Don't add a separate intro/outro heuristic —
the loudness curve IS the role signal. Score candidate sections directly:
- T1 mix-out candidates: sections in the last ~30%; favor where loudness.shortTerm is at or
  below the track's median and falling (outro dissolve).
- T2 mix-in candidates: sections in the first ~35%; favor where loudness starts low and rises
  (intro build → just before the drop). This directly fixes the "naked beat" bug (mixing into
  a sparse drum-only intro) that motivated Phase 3.
"Role" is emergent from the loudness score; a label-guesser is redundant scope.

## Q2 (beam search): NO — do not port advanced_cue_planner.py's beam search.

That beam search is for PLAYLIST SEQUENCING (ordering N tracks). This renderer slice handles
ONE transition between two FIXED tracks; it only needs to pick the best (mixout, mixin) pair
for those two. apple_handoff cost + vocal-collision penalty + loudness-phrasing over candidate
section pairs is exactly the right scope and sufficient. Sequencing is Phase 4 (full-set
wiring), a separate concern — keep them separate.

## Phase 3 guardrails

- Keep --mixin-s/--mixout-s as manual overrides; auto-cue ONLY when they're absent.
- Before calling score_apple_transition(from_features, to_features), READ the bodies of
  _loudness_handoff / _bpm_disagreement / _key_instability / _phrase_boundary_penalty and use
  the EXACT feature keys they read. Do not guess key names from the field list — verify, and
  paste the keys you found.
- Deterministic scoring only (no random tie-breaks; stable sort).
- Vocal-collision penalty: use instrumentActivity.activity.vocal curves over the ACTUAL
  candidate overlap window (aligned to each candidate's anchors), not a track-level average.
- Re-validate after: stems-sum + true-peak on BOTH a zero-stretch and a stretched pair, AND
  assert the chosen mix-in is NOT in a low-loudness region (the bug this phase fixes). Report
  the chosen (mixout_s, mixin_s) and their loudness context, and listen.
- Diff against the CURRENT render_transition.py.
