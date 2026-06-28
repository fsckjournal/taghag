# Beatmatched Mixer — Handoff / Where We Left Off

_Last updated: 2026-06-28._

Status doc for the automated beatmatched-mixer line of work. Read this first when
resuming. Pairs with the memory note `beatmatched-mixer-project.md`.

## Goal

Render an already-ordered playlist of local **FLAC** masters into a continuous,
beatmatched mix — one transition at a time. The order is a human/Rekordbox
playlist (`/Volumes/PLAYGROUND/MINIMAL/minimal-rekordbox.m3u8`, 224 tracks); the
job is the beatmatched crossfade between consecutive tracks, eventually chained.

## Data sources & the source-of-truth rules (hard-won — read these)

| Source | File | Use it for | Do NOT use it for |
| --- | --- | --- | --- |
| **Apple analyzer** | `cuecifer_analyzer` on the FLAC | Beat grid, downbeats, sections, key, loudness, pace | Declared BPM header (can be wrong) |
| **MIK** | `/Volumes/PLAYGROUND/MINIMAL/rekordbox_mikcues_001.xml` | Energy cues (structure) | Beat grid / BPM (it has none) |
| **Rekordbox** | `/Volumes/PLAYGROUND/MINIMAL/rbx.xml` | AverageBpm, cues | (phrase intro/outro cues are NOT here — see ANLZ) |
| **Lexicon** | `lexicon_main.db` snapshot | (reference only) | **BPM — was wrong (125 vs true 125 grid... see below)** |

**Corrections established this session (don't relitigate):**

1. **"MIK" = `rekordbox_mikcues_001.xml`** — a Rekordbox-format XML, 398 FLAC-pathed
   tracks, 5,908 `POSITION_MARK` Energy cues ("Energy 4/6/8…") in absolute seconds,
   **no tempo/BPM**. It is MIK's energy/structure layer on the real FLAC masters.
2. **`Collection11.mikdb` is an ADDED LAYER — ignore it.** It is a genuine Mixed In
   Key Core Data collection, but its bookmark paths point mostly at
   `/Volumes/LOSSY/transcoded_mp3/` + `.Trashes` (transcodes derived from the FLAC
   masters). The "MIK analyzed historical MP3s / encoder-delay" worry was about this
   wrong layer and does not apply to the XML above.
3. **BPM source of truth = the median beat-interval of the analyzer grid**, never any
   declared/tag BPM field — not the analyzer's own `rhythm.beatsPerMinute` header,
   not Lexicon's tag, not Rekordbox's `AverageBpm`. Example: Booka Shade *In White
   Rooms* — analyzer header says 120.089, but its grid spacing = **124.94** (≈ what
   Lexicon tagged, 125). The grid is truth.
4. **Adjacent-BPM gaps along the playlist** (Rekordbox BPM, 113/224 matched): median
   1.0, p75 2.0, max 7.0, **~24% of transitions > 2 BPM**. ⇒ time-stretching is
   required for a general renderer; "crossfade only" trainwrecks on the long tail.

## What's built

All under `tools/mixslice/` (Python, uses the `tools/.venv`).

- **`render_transition.py`** — renders ONE beatmatched crossfade between two FLACs
  from their analyzer JSON. Picks 32-beat section anchors snapped to the nearest
  beat, aligns anchors to the same output sample, micro-stretches the incoming
  overlap with rubberband only if grid drift > 6 ms, equal-power crossfade, writes a
  FLAC excerpt + a JSON report (residual beat offset).
  - `--mixin-s` / `--mixout-s` override the cue points (seconds).
  - `--click` overlays panned beat clicks (T1 = left, T2 = right) to ear-check
    beats-vs-kicks.
  - `--stems` also writes each track isolated on the mix timeline
    (`<out>.trackA.flac` / `.trackB.flac`); the two stems sum exactly to the mix.
- **`visualize.py`** — librosa-free diagnostic PNG: peak-envelope waveform + red clip
  carets (|amp| ≥ 0.99) + analyzer pulse grid (grey bars, numbered 32-beat sections)
  + MIK/Rekordbox cues overlaid (orange). `--start/--end` to zoom, `--mark` for
  candidate cue lines. Supersedes the root-level `spectralwaveform.py` (which
  recomputed a librosa PLP pulse).
- **`syncopation_score.py`** — ML-free "straightness" ranker: bandpasses to the kick
  band, locks beat phase from Rekordbox BPM, measures on-beat vs off-beat energy
  concentration. Ranks the playlist from straight (4/4) to syncopated. Well-calibrated
  (most-syncopated results were Bruno Pronsato, Kollektiv Turmstrasse).

Supporting (kept, but the 2.4 GB DB **snapshots are gitignored**, not committed):
`tools/forensic/` — DB probes + cross-source beat-grid comparison scripts + small
extraction JSONs. The native `tools/cuecifer-analyzer` Swift binary is already built
at `.build/out/Products/Release/cuecifer_analyzer` (takes a FLAC or .m3u path).

## Analyzer JSON format (per FLAC)

Keys: `rhythm` (`beatsPerMinute` + `beats[]` + `bars[]`), `key`, `structure`
(`segments` 16-beat / `phrases` 8-beat / `sections` 32-beat), `pace`, `loudness`
(`integrated`/`momentary`/`shortTerm`/`peak`), `instrumentActivity`,
`structurePredictions`. Times are CMTime `value/timescale` seconds; **timescale = the
file's sample rate (48000 or 44100), not fixed**. `flags` are CMTime validity bits,
NOT downbeats — downbeats are `rhythm.bars` / `structure.sections`.

## What we learned from listening (demos on ~/Desktop)

- **First stretch demo** (`transition_stretch.flac`, Booka → Patrice): beat-synced but
  **musically mis-phrased** — Patrice/Glutes was cued at `section[1]` = 15.2 s, deep in
  its sparse kick-only intro, so Booka's fade exposed a naked beat. **Fix**: re-cue the
  mix-in to the END of the intro. `transition_fixed.flac` uses `--mixin-s 60.6`
  (Glutes' section 4, where the groove fills out) — tail now carries full content as A
  exits. **Lesson: the default mix-in must be end-of-intro, not section[1].**
- **Brickwalling is in the SOURCE masters**, not (mainly) our render. `booka.viz.png`
  shows *In White Rooms* railed at 0 dBFS almost end to end. Can't un-clip a limited
  master; the renderer must only avoid ADDING clipping (overlap headroom / true-peak
  limit) — the current whole-file `/peak` normalize just scales the result down.
- **Clean test pair** (straight + zero stretch): Mihai Popoviciu – Viper (127) → Kalle-M
  & Monoder – Beep Parade (127). Both grid-BPM 126.998. Rendered as
  `viper_beepparade.flac` + `.trackA`/`.trackB` stems (stems verified to sum to the
  mix). Beat alignment essentially perfect: residual 0.023 ms over 32 beats, no stretch.

## Open issues / next steps (in rough priority)

1. **Clip/gain fix in `render_transition.py`** (parked at user request): stop whole-file
   normalizing; leave overlap headroom (sources already at 0 dBFS) + optional true-peak
   limit; preserve **24-bit** (currently writes 16-bit); label the report's BPM from the
   grid median, not the declared header.
2. **Auto mix-in/out cue selection** (replace the section[1] heuristic). Two leads:
   - Loudness-structure recipe from the user's notebook
     (`~/Downloads/python,_but_BPM_&_Beatgrid_Rekordbox_+_Key_Detec_.ipynb`): detect the
     drop (first > 8 dB loudness jump, quantize to a bar), Mix-In = 32 bars before, Mix-Out
     = 64 bars after. We already have the `loudness`/`pace` fields it needs. (Caveat: it
     uses declared BPM — switch to grid.)
   - Rekordbox's own intro/outro **phrase** cues live in the **ANLZ** files
     (`~/Library/Pioneer/rekordbox/share/PIONEER/USBANLZ`, PSSI tag), NOT in the XML
     exports — parse those if we want DJ-grade auto cues.
3. **Stress-test rubberband on a genuinely large gap** (> 4 %, or a half/double-time
   case). So far only ~1.6 % stretch has been exercised; quality at big stretches unknown.
4. **Recompute the full gap distribution from Apple grids** (batch-analyze all 224 — ~hours
   of compute, ~2 GB JSON) for the definitive landscape + to pre-cache grids for the full mix.

## How to run

```bash
cd tools && source .venv/bin/activate
ANALYZER=cuecifer-analyzer/.build/out/Products/Release/cuecifer_analyzer

# 1. analyze each FLAC -> JSON grid
"$ANALYZER" "/path/A.flac" > A.json
"$ANALYZER" "/path/B.flac" > B.json

# 2. render a transition (+ isolated stems)
python mixslice/render_transition.py A.flac B.flac A.json B.json out.flac --stems

# 3. diagnose a track (waveform + pulse grid + MIK/RBX cues)
python mixslice/visualize.py A.flac A.json \
  --cues /Volumes/PLAYGROUND/MINIMAL/rekordbox_mikcues_001.xml \
         /Volumes/PLAYGROUND/MINIMAL/rbx.xml \
  --start 0 --end 70 --out A.viz.png

# 4. rank playlist tracks by straightness (un-syncopated)
python mixslice/syncopation_score.py
```

Toolchain: `rubberband` 4.0.0 (brew); venv has numpy, scipy, soundfile, pyrubberband,
matplotlib, mutagen. The Apple analyzer needs macOS 26/27+ and the built Swift binary.
