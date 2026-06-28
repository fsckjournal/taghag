# Beatmatched Mixer — Current State & Handoff (read this first)

_Last updated 2026-06-28. Supersedes the per-phase Gemini docs for "what's true now."_
Pairs with memory `beatmatched-mixer-project.md`. This doc is the durable record after
a conversation clear.

## Goal
Render an ordered crate of local minimal-techno FLACs into ONE continuous, beatmatched,
gapless mix + a CUE sheet, played natively by Roon. Focus playlist (concentration), not
hand-curated for taste.

## The hard-won conclusions (do NOT relitigate)

1. **The wobble was real and it was ours.** The old `render_transition.py` warped the
   incoming track to the Apple analyzer's RAW per-onset beats (±5–20 ms jitter + gaps).
   `pyrubberband.timemap_stretch` chasing those jittery targets made the incoming track's
   playback speed lurch 0.66×–0.99× beat-to-beat (33.6% swing) = the audible "slows down
   and bounces back." The grid was steady (Booka = 125.02 BPM, 5 ms RMS); only our warp
   wobbled.

2. **The fix: warp a RIGID grid at ONE constant ratio.** A constant-tempo track's grid is
   just `phase + i·(60/BPM)`. Warp the incoming overlap at `rate = period_in/period_out`
   (one number). `tools/mixslice/grid_mix.py` does this → measured **0.0% per-beat speed
   swing** (vs 33.6%). The wobble cannot occur with rigid grids.

3. **Don't compute beatgrids — consume the DJ apps'.** Rekordbox/MIK/Beatport already
   solved precise tempo. Tempo precision = many beats fit to a constant period (regression
   / the app's grid), NEVER `60/Δt` per beat (that's a jitter amplifier). Source of truth:
   - **`rbx-re.xml`** (`/Volumes/PLAYGROUND/MINIMAL/`): `AverageBpm` (rigid tempo) +
     `POSITION_MARK` energy cues (first cue = grid phase, = old `TEMPO Inizio`). Covers all
     224 playlist tracks. The `<TEMPO>` node is redundant with `AverageBpm` for constant
     tracks; this export dropped it, doesn't matter.
   - **Every track in the playlist is constant-tempo** — checked the multi-node grids; BPM
     spread ≤0.5 on all of them. Zero true drift. So `AverageBpm` + single-ratio warp works
     for the WHOLE set. (Genuinely-drifting tracks would need a piecewise grid — none here.)

4. **No BPM tag is trustworthy; tool-agreement proves nothing.** File tags are garbage
   (Mella Dee tagged 95, it's provably 127). rbx + MIK agree but BOTH double-time downtempo
   tracks (People On Sunday: both say 144, it's ~72). Half/double is a perceptual ambiguity
   even top tools miss — DON'T try to auto-fix it. Flag + defer to the user's ears.
   **Crucially: the grid is octave-INDEPENDENT** (beat positions are identical at 74 or
   147), so the renderer/wobble-fix don't care; octave only matters for transition
   compatibility, where the user's ear-verdict is the input.

5. **Sequencing is already solved — don't build beam-search.** `Minimal Focus.txt` (UTF-16
   TSV) column `#` is **Spotify mix-mode's smooth-transition reordering**. Use that order.
   No Phase-4 sequencer needed.

6. **Drop everything >135 BPM** — accidental non-minimal tracks (not curated). This also
   removes the octave-error suspects.

7. **Roon = control plane only.** Confirmed: the Roon Extension Kit exposes playback/volume/
   zones, NOT the audio stream — no in-Roon DSP/VST. So the architecture is **pre-render**:
   produce one continuous FLAC + CUE sheet, drop in Roon's watched folder, Roon plays it
   gapless with per-track seeking. Our offline render IS the product; Roon is just the
   player. (Live "Squeezebox loopback" streaming is the fragile alternative — not pursued.)

## The pipeline (built)
```
Minimal Focus.txt (# = Spotify mix order)         <- sequence
   -> resolve title -> local FLAC (minimal-rekordbox.m3u8)   <- 213/235 match, 22 Beatport-only
   -> drop BPM>135                                            <- 13 dropped
   -> attach rigid grid (rbx-re AverageBpm + phase + cues)
   = render_plan.json   (200 tracks, ordered)                <- tools/mixslice/build_render_plan.py
   -> grid_mix.py per consecutive pair: single-ratio warp + cue-aligned equal-power xfade
   -> [NEXT] chain_mix.py: stitch all 200 -> one FLAC + .cue for Roon
```

## Scalability of the mechanism (the answer)
**O(N) in tracks, constant per-transition cost, streamable, parallelizable.**
- Per track the grid is 2 numbers (BPM, phase) — precomputed by Rekordbox, NO audio analysis
  at render time.
- Each transition only processes the ~30 s overlap region (one rubberband pass over ~15 s +
  a vector crossfade). The body of every track is copied verbatim. So cost ≈ N × (one short
  rubberband + a copy), independent of total mix length.
- Memory is streamable: render pairwise, append to the output file — never hold the 6-hour
  mix in RAM. A 200-track mix costs the same per transition as a 3-track one.
- Transitions are independent → trivially parallelizable, then stitch.
The leverage: consume precomputed rigid grids (don't analyze audio at render time) and touch
only the overlaps (don't reprocess whole tracks).

## Files
- `tools/mixslice/grid_mix.py` — grid-based transition renderer (THE wobble fix). Run:
  `grid_mix.py render_plan.json SEQ OUT.flac`.
- `tools/mixslice/build_render_plan.py` — builds `render_plan.json` (mix order + filter + grid).
- `tools/mixslice/render_transition.py` — OLD Apple-beats renderer (Phases 1–3, has the wobble;
  kept for its DSP: 3-band LR crossover/bass-swap, true-peak limiter, dither). Migrate its DSP
  into `grid_mix.py`; do NOT use its warp.
- `tools/mixslice/build_manifest.py` — QC/provenance manifest (tempo cross-check, octave/fast
  flags). Needs a read-only MIK snapshot (`Collection11.mikdb`).
- Evidence (read-only, `/Volumes/PLAYGROUND/MINIMAL/`): `rbx-re.xml`, `rbx.xml`,
  `rekordbox_mikcues_001.xml`, `Minimal Focus.txt`, `minimal-rekordbox.m3u8`. Identity CSVs
  (ISRC + Spotify/Beatport IDs): `~/Downloads/fm.csv`, `Focus Minimal.csv`, `Focus Minimal-2.csv`.
- Demos on `~/Desktop/`: `grid_transition.flac` (wobble-fixed Danny B→Genius Of Time).

## Next steps (priority)
1. **Listen** to `grid_transition.flac` — confirm the wobble is gone by ear. (Gate.)
2. **`chain_mix.py`** — stitch all 200 into one FLAC + CUE sheet (the Roon deliverable).
3. Migrate the good DSP from `render_transition.py` (LR bass-swap, look-ahead true-peak
   limiter, 24-bit dither) into `grid_mix.py`.
4. Refine cue selection (mix-out = outro energy drop, mix-in = end-of-intro) using rbx energy
   cues + Apple loudness; avoid the naked-beat pick.
5. Octave ear-pass on the ~6 half/double suspects (only matters for compatibility, not render).
6. Identity: 22 unmatched / Beatport-only — reconcile via the ISRC CSVs if you want them in.

## Gemini retrospective (why we stopped using it)
Good at well-specified DSP (24-bit, limiter, LR crossover); unreliable at judgment and
**reported false "validated" results 3 phases running** (broken limiter that hard-clipped via
the dither; stems-sum regression; an auto-cue that picked the naked intro). Every "done" needed
independent measurement to puncture. Keep validation in-house.
