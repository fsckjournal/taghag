# Live automix engine (sketch)

Concrete shape for the **live** automix model (operator decision 2026-06-29: "a
continuous FLAC is not viable… it needs to be 'live' and uses the actual files, just
like offtrack in local mode"). Pairs with [slut_hag_split.md](slut_hag_split.md) and
[GLOSSARY.md](../GLOSSARY.md). This exists so the **own-engine vs drive-an-open-player**
decision has something concrete under it.

## The key realization

A media server (Jellyfin/Roon/Plex) streams **one file at a time**. Automix needs **two
decoded streams overlapping with a live crossfade**. No REST media server exposes that.
**So the live mix has to happen in *our* engine** — the "player" is at most a library
browser + remote control + audio sink. This strongly favors **hag owns the live engine**
(offtrack is itself a standalone app, not a plugin). Jellyfin then matters only as an
optional UI/library layer, not as the mixer.

## The one hard problem, and the trick that dissolves it

`mixslice/render_transition.py` already does the whole transition (align → micro-stretch →
equal-power blend → 3-band bass swap → limiter → dither). But it's **offline**:
full-array, `pyrubberband.timemap_stretch` has no real-time mode.

We **don't need streaming time-stretch.** The next track and its grid are known in advance
(the render plan is ordered). So when the current track enters its lead-out, a worker
thread **pre-bakes just the ~30–60 s overlap segment** (reusing `render_transition`'s exact
DSP) into a buffer. Steady-state playback is then **straight FLAC decode, zero DSP**; the
real-time callback only ever does a cheap buffer swap + (optional) per-block blend. The
expensive math runs ahead of the playhead on a finite segment, never in the hot path.

## Components

| Component | Role | Reuses |
| --- | --- | --- |
| **Library resolver** | identity (`track id`/`content_sha256`) → local FLAC path, at play time | slut `track_file` (0001_library_foundation) |
| **Sequencer** | emits/loads `render_plan.json` = live instruction set: ordered identity list + per-track in/out segment cues + per-transition params | `similarity/` + planner + `build_render_plan.py`, unified |
| **Scheduler** | watches the playhead; when current track nears mix-out, triggers the Baker for the next pair | new (thin) |
| **Transition Baker** | (A-tail, B-head, grids, params) → pre-rendered aligned/stretched/crossfaded overlap buffer, on a worker thread | **`render_transition.py` as-is** |
| **Real-time mixer / audio I/O** | CoreAudio callback: straight-decode steady state → swap to baked overlap during the window → continue into next track; lock-free buffer handoff | new (small) |
| **Control API** | play/pause/next/seek/regenerate-mix — the player-agnostic seam (CLI now; REST/UI later; what Jellyfin or a custom client would drive) | new |

## Tech (macOS, FLAC, python-first)

- **Decode:** `soundfile`/libsndfile (already used), chunked.
- **Output:** `sounddevice` (PortAudio → CoreAudio). A 2-stream blend at 1024–4096-frame
  blocks is feasible in Python **because the heavy stretch is pre-baked** — the callback
  does only array slicing + add.
- **Stretch:** keep `pyrubberband` *offline*, applied by the Baker to the overlap only. No
  real-time rubberband bindings needed for v1.
- Net: the engine stays in Python and reuses **all** existing mixslice DSP unchanged.

## Risks / unknowns

- **Python + real-time audio:** the callback must never block. Mitigation: Baker runs on a
  worker thread and hands finished numpy buffers across; the callback does only cheap ops.
  Feasible, but **must be validated with a latency/underrun test** before committing.
- **Gapless steady-state decode** + seeking to segment in/out points.
- **Fully dynamic (unknown next track)** would need real-time stretch — explicitly **out of
  scope for v1**; the look-ahead bake assumes an ordered plan.

## Vertical slice (smallest proof)

1. **Two-track live transition.** Load a 2-track identity-keyed plan → decode A → at the
   scheduled mix-out, blend into the **pre-baked overlap** → continue into B → out to
   speakers via `sounddevice`. This is literally `render_transition.py`'s current output,
   **played live instead of written to `out.flac`** — the minimal thing that proves the
   look-ahead-bake architecture.
2. **N-track chaining** (the `chain_mix` logic, live + scheduled).
3. **Control API** (skip / regenerate-from-here), which is the seam an external player drives.

If step 1's latency/underrun test passes, the model is proven and the rest is assembly.
