# Time-Base Anchor — evaluation

**Status:** evaluated (2026-06-21) · **Source:** live DB, owner `d4c61173-8432-432f-b238-9bd72c7285e3`, applied 2026-06-21 · **Probe:** `tagslut/docs/audit/2026-06-21-cue-coregistration-probe.md`

Empirical results of re-zeroing the mixonset analyzer grid onto the human/master grid across the 11 tracks carrying both clocks.

---

## Methodology — histogram-vote grid cross-correlation

The two grids are not 1:1: human cues are few and hand-placed, mixonset cues are many predicted boundaries. Nearest-neighbour-then-median is polluted by the non-corresponding cues on both sides. `grid_offset` (`tools/taghag_import/time_base.py:83`) instead:

1. De-dupes each grid (the human quadruple-insert).
2. Collects every pairwise diff `mixonset − human` within `window_ms` (60 ms).
3. Finds the diff value with the most neighbours inside `eps_ms` (8 ms) — the histogram peak. Non-corresponding cues scatter and form no peak; corresponding cues pile up at the true lag.
4. Reports the peak contributors' mean as `offset_ms` and their MAD as `residual_ms`; `votes` = peak size; `confidence = agreement × tightness`.

`reconcile_offset` accepts the vote only at `votes ≥ 3` (`min_votes`). Sign convention: `offset = mixonset − human`; **`canonical_ms = measured_ms − offset_ms`**. A failed vote returns `None` — it does **not** fall through to a fabricated identity (offset 0), so un-measurable tracks stay honestly `offset_missing`.

## Results — measured offsets

The mixonset analyzer grid lands a small **positive** offset *after* the human/master grid. **6 of 11** tracks reconciled confidently via `cross_correlation`:

| audio_file | offset (ms) | residual (ms) | confidence |
| --- | --- | --- | --- |
| 0c77e5b8 | +12.25 | 1.25 | 0.865 |
| 9d73c11a | +11.60 | 0.60 | 0.581 |
| 22e24501 | +15.00 | 3.00 | 0.455 |
| 94d7efe4 | +17.00 | 0.00 | 1.000 |
| 3e08a729 | +17.75 | 1.25 | 0.432 |
| 445971f8 | +23.20 | 3.80 | 0.565 |

Measured band: **+12..+23 ms**. `3e08a729` (+17.75 ms, MAD 1.25) is the real-data twin of the probe's ~17 ms finding and is the calibration fixture in `tools/tests/test_time_base.py`.

> The `time_base.py` module docstring quotes a tighter **+12..+18 ms** band; the authoritative live result is **+12..+23 ms** (`445971f8` at +23.20 ms sits above the docstring's upper bound).

**5 of 11** tracks returned `None` — too little structural overlap to vote: `9a35d116`, `b51cdc3b`, `c7038153` (only 1 human cue), `c7fa7f07`, `ec581126`. These correctly stay `offset_missing` rather than being fabricated as identity/zero.

## Post-backfill verification

- **6** `rendition_time_offset` rows written.
- **335** mixonset cues now `time_base='rendition'` — **183** anchored (have an offset), **152** `offset_missing` (the 5 un-votable tracks).
- `track_cue_canonical` total **unchanged at 12,832** — no row fan-out; the 3-column join (incl. `audio_file_id`) holds.
- The canonical view re-zeros `3e08a729` mixonset cues by exactly **−17.75 ms**.

## Why per-(file, rendition, system), not one constant

The offset is **not** a single universal constant — it varies +12..+23 ms per track. It compounds encoder/analyzer framing, 1000 Hz (1 ms) quantization, and beat-snapping. Storing it per `(canonical audio_file, measured_against rendition, source_system)` is therefore necessary, not over-engineering. Consumers read the canonical views, never raw `time_ms`.

## Known limitations

- **Coverage gated by human cues.** A track needs a human grid with enough corresponding structure to vote. 5/11 here had too little; sparse-cue tracks (e.g. 1 human cue) cannot anchor.
- **1 ms quantization floor.** Cue times are integer ms, so residuals below ~1 ms are not meaningful; the histogram `eps_ms`/`window_ms` are tuned to that grain.
- **Confidence is heuristic.** `agreement × tightness` is a relative health signal, not a calibrated probability; some confident-looking offsets (e.g. 0.432 at residual 1.25) are tight but low-agreement because human cues are few.
- **PCM path dormant.** `pcm_cross_correlation` (librosa/numpy) would validate the cheaper grid vote, but the toolchain has neither dependency, so it returns `None`. All results above are grid-vote only, unvalidated against decoded audio.
- **Legacy `unknown` cues un-anchored.** The 12,832 pre-existing cues stay passthrough (`offset_missing=false`); only mixonset rows get re-zeroed.

## Open questions

- Is the per-track offset stable across re-analysis, or does it drift with mixonset version / re-import?
- Can the 5 un-votable tracks be anchored via `downbeat_anchor` (single explicit beat) or the dormant PCM correlation once librosa is available?
- Does the +12..+23 ms spread correlate with codec/sample-rate of the analyzed rendition, suggesting a `declared_priming` prior worth blending in?
- Should `min_votes`/`eps_ms`/`window_ms` be tuned per source_system as other clocks (apple, iwebdj_cloud, anlz, beatport) are onboarded?
- What confidence/residual thresholds should gate fusion downstream — i.e. when is a reconciled offset trustworthy enough to average grids on?
