# Renderer → rigid DJ-app grids (kill the wobble at the source)

The warp wobble (±34% beat-to-beat speed swings) comes from warping to the Apple
analyzer's RAW detected onsets, which carry ~5–20 ms jitter and gaps. Fix: drive
alignment/warp from a RIGID grid model (constant period + phase), never raw onsets.
rbx.xml is the best source where it exists; a regression-fit of our own beats is the
universal fallback.

## Coverage (measured on minimal-rekordbox.m3u8, 224 tracks)
- Stem-matched into rbx.xml: **215/224** (file://...POOL/... vs our MINIMAL paths → match by filename stem, not exact path).
- Of those: **78 single rigid TEMPO** (ideal), **35 piecewise** (2–3 TEMPO), **102 ZERO TEMPO** (in collection, never gridded).
- ⇒ rbx gives a usable grid for ~**113/224**. The rest need the fallback. So: a SOURCE PRIORITY CHAIN, not rbx-only.

## Grid-source priority chain (per track)
1. **rbx.xml rigid TEMPO** (human-corrected, file-relative phase) — 78+35 tracks.
2. **Beatport iWebDJ BPM** via beatport_resolver.py (catalog-accurate tempo) — for tracks resolvable to a Beatport ID. NOTE its phase/offset is unreliable (validation showed ±0.5–1.6 beat lag) → take its BPM only, anchor phase separately.
3. **Regression-fit Apple grid** (universal fallback): fit `beat[i] ≈ phase + i·period` to the Apple beats by least squares → a CONSTANT-period rigid grid. This alone removes the wobble even with no DJ-app grid.

All three yield the same object: `(period, phase, downbeats, optional piecewise segments)`. The renderer consumes that, not raw onsets.

## rbx.xml schema (the wheel)
- `<TRACK Location="file://localhost/..." AverageBpm Tonality>` — match by stem.
- `<TEMPO Inizio Bpm Metro Battito>` — Inizio = first-beat seconds (file-relative), Bpm constant, Battito = beat-in-bar (1..4 → downbeat = Battito==1). 1 node = fully rigid; N nodes = piecewise (each valid until next Inizio).
- `<POSITION_MARK Name Type Start Num>` — cues; Name="Energy 4/7/8" (MIK energy), Start = seconds. These mark phrase/energy boundaries → mix-in/out candidates.

## Concrete changes in tools/mixslice/render_transition.py

### NEW module `tools/mixslice/rekordbox_grid.py`
- Parse rbx.xml once → `{stem: {bpm, inizio, tempo_nodes:[(inizio,bpm)], battito, cues:[(start,name)], duration}}`; cache to JSON (avoid reparsing 1.8 MB each run).
- `build_rigid_beats(track, duration)`:
  - 1 TEMPO → `inizio + arange(N)*(60/bpm)`, N = floor((dur-inizio)*bpm/60)+1.
  - N TEMPO → piecewise: for each node, emit beats at 60/bpm until next node's Inizio.
  - downbeats = beats where running bar-count ≡ Battito==1 (every 4th from Inizio).
- `regression_grid(apple_beats)` fallback: `period,phase = lstsq`; return rigid beats + report max deviation (the “is it actually drifting?” number).

### `load_grid` / `Grid`
- Add `source` param. Build `Grid.beats` from the priority chain (rbx → beatport bpm → regression), NOT from raw `rhythm.beats`.
- `Grid.bpm` = the rigid period’s BPM (constant).
- `Grid.sections` = 32-beat blocks anchored on downbeats (Battito), or keep Apple `structure.sections` for phrasing.
- KEEP reading Apple JSON, but ONLY for `loudness` / `structure` / `instrumentActivity` curves. Apple no longer supplies beats/tempo/cues.

### The warp (THE wobble fix) — replace the per-beat time_map loop
- Both grids are now rigid ⇒ a SINGLE constant ratio: `rate = period_in / period_out` (= bpm_out/bpm_in). One `pyrubberband.time_stretch(t2_over, sr, rate)` call. Beats stay locked across the whole overlap because both grids are perfectly periodic. No timemap, no per-beat targets, no wobble.
- Only for a genuinely piecewise track (multi-TEMPO) use timemap — but to the SPARSE rbx TEMPO nodes, never to per-onset beats.

### Phase anchoring (the one caveat)
- rbx `Inizio` is relative to the file rbx analyzed (a POOL copy). We render the MINIMAL copy. If they’re the same content, Inizio is directly usable. Add a one-time guard: cross-correlate the rbx first-downbeat window against our FLAC with `taghag_import.time_base.pcm_cross_correlation`; if offset > a few ms, shift the grid phase by it. (This is exactly what time_base exists for, and it fixes Beatport’s phase issue too.)

### Cues — replace `plan_auto_cues`
- Mix-out: an energy POSITION_MARK in T1’s last ~30% (prefer high→falling energy = outro).
- Mix-in: an energy POSITION_MARK in T2 after its intro where energy is already up (NOT Start≈0). The energy cues are exactly the phrase markers that fix the naked-beat pick.
- Keep `--mixin-s/--mixout-s` overrides and FIX the AND-bug (each should default independently).

### Fallback / honesty
- Tag each render’s report with `grid_source` per track (rbx | beatport | regression) and the grid max-deviation, so a wobbly result is attributable.

## Net
- Wobble: gone (rigid grid + single ratio) on 100% of tracks (rbx where gridded, regression elsewhere).
- Naked-beat cue: solved via energy cues.
- Apple analyzer: demoted to loudness/structure/vocal curves only.
- time_base PCM-anchor reused for phase (rbx POOL→MINIMAL, and Beatport offset).
