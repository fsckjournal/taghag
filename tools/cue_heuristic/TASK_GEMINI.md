# TASK — Cuecifer mix-point heuristic (`predict_cues`)

**Owner:** Gemini · **Support:** Taghag (hag) session · **Repo:** `hag:tools/cue_heuristic/`
**Read first:** `README.md` (this dir) and `hag:docs/reports/opus_training_dossier.md`.

## Objective
Write a deterministic `predict_cues(payload) -> list[float]` that consumes an Echo Nest
payload and reproduces the Mixonset ground-truth cue timestamps — and **beat the measured
section-boundary floor** (`python3 eval.py --baseline`): F1 **0.07** (Wildfires) / **0.36**
(Smoothin' Groovin'). Then explain the acoustic rule each cue fires on.

This is yours because you decoded the Mixonset energy TFLite net and built the payload
corpus — you know the signal better than we can infer it.

## Steps (in order)

### 1. Grow the eval set (biggest leverage — only you can scrape)
- Run `scrape_targets.json`: fetch the 4 missing cue-bearing payloads into
  `hag:automix_payloads/<spotify_id>.json` (same pipeline/format as the existing 22,808).
- All 4 targets now have resolved Spotify IDs (Steady Drummer → `6HSQVzeB7kjoeEkrTwLCSY`,
  duration-validated). Just scrape them; disambiguate any remaining variants by
  `track.duration > last_cue_s`.
- For each newly-scraped track, extract its cue table from `mixonset_analysis_report.md`
  (you have it — `/Users/g/Documents/taghag/docs/archive/mixonset_analysis_report.md`) and add
  it to `ground_truth.json:verified_pairs` (same shape as the 2 existing entries:
  `{title, spotify_id, payload, cues:[{t,bpm,energy,mix}]}`). Or ping hag to fold them in.
- Skip **Drifting — Proviant Audio**: no Spotify release (flagged `no_spotify_release`). Don't
  title-match it — false-positive risk.

### 2. (Bonus, only you can do) Richer target from the `.dat` cache
The report kept only the **cue rows**. If you can dump the full **per-segment `Local Energy`
and `Local BPM` time-series** from the decrypted Mixonset `.dat` cache, drop them as
`ground_truth_curves/<spotify_id>.json`. That gives the heuristic the actual gradient shape the
net responded to, not just the firing timestamps — a much stronger supervision signal.

### 3. Implement `predict_cues` in `eval.py`
- Use the high-res `segments` array, not `sections` (sections alone scored the floor above).
- Per the dossier thesis: cues correlate with large positive ΔE (energy gradient) at
  drops/breakdowns. Build the loudness envelope from `loudness_start` / `loudness_max` /
  `loudness_max_time`; consider `timbre[0]` (overall loudness) and spectral flux from
  `pitches`/`timbre` for confirmation.
- Iterate against `python3 eval.py` after each pass.

### 4. Explain the rule
Short writeup: what acoustic condition places each cue (gradient threshold, beat-quantization,
min-spacing, section-aware gating — whatever you land on). Append to the dossier or a sibling
`HEURISTIC_NOTES.md`.

## Done when
- `predict_cues` scores **F1 > baseline on every pair** in `ground_truth.json` (ideally with the
  set grown to 5–6 tracks), and
- the new payloads are present, and
- the rule is documented.

## Handoff back
Ping the hag session when `predict_cues` clears the floor. Hag then: folds new payloads into the
eval set, wires the winning `predict_cues` into the taghag pipeline, and builds the
payload↔library join once v4's `spotify_id` seam lands (see
`slut:docs/v4/HANDOFF_FROM_HAG_2026-07-01.md`).
