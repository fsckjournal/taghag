# Plan — One Identity-Anchored, Harmonically-Ordered Playlist That Plays in Roon

Date: 2026-06-22
Status: plan
Supersedes: `docs/audit-outdated/2026-06-21-smallest-next-product-outcome-plan.md` (file paths and
function names below were re-verified against the live `tag/hag` and `tag/slut` trees; the
source plan referenced `tagslut`/`taghag` as sibling directories, which have since moved to
`tag/slut` and `tag/hag`, and referenced `apple_butterflow.py`, which has been renamed to
`apple_handoff.py`)

## The outcome

Emit **one** `.m3u8` of master FLAC absolute paths, ordered into a harmonically sensible run
from a seed track, where every entry is chosen by **identity** (survives re-tag/move) and the
file resolves on disk so it plays in Roon. This is the understand → interlink → mix → playlist
→ listen chain in miniature. It forces the one decision that currently blocks everything — the
identity join between Taghag's Postgres store and Tagslut's SQLite store — in the smallest,
lowest-risk way: read-only, one playlist, no schema merge, no migration.

## Architecture

The two stores stay separate; they exchange a neutral JSON interchange and neither imports the
other. This respects `tools/audit_cleanroom.py` (which forbids the string `tagslut` in Taghag
code).

```
  Taghag (the brain)                 interchange            Tagslut (the backbone)
  Postgres/pgvector                  ordered JSON           SQLite music_v3.db
  ----------------------------       ------------------     --------------------------
  seed -> sonic neighborhood         [ { isrc,              resolve each item -> identity
  -> harmonic ordering (Camelot      content_sha256,        (ISRC primary; sha256/
  + BPM-delta + apple_handoff)       streaminfo_md5,        streaminfo_md5 fallback)
  -> emit ordered identity keys      artist, title,         -> build PlaylistSource of
                                      transition_cost } ]    selectors -> render(zone=master)
                                                              -> .m3u8 of /Volumes/MUSIC paths
```

- **Taghag owns ordering** because that's where the features live
  (`apple_derived_features`, sonic embeddings, `dj_tag.bpm`/`musical_key`). It must emit only
  neutral identifiers (ISRC / sha256 / streaminfo_md5) — never a Tagslut concept.
- **Tagslut owns identity resolution + rendering** via the existing
  `tagslut.playlist.{resolver,renderer}` (`tag/slut/tagslut/playlist/resolver.py:92`,
  `tag/slut/tagslut/playlist/renderer.py:24`) — `resolve_selector()` already resolves `isrc:`
  selectors through SQLite, and `render(source, conn, zone, output_path)` already writes
  `#EXTM3U` with absolute paths and a `.missing` sidecar for unresolved entries.
- **Roon delivery is manual**: drop the `.m3u8` into a Roon watched folder. No API automation
  in scope.

### Join key precedence

ISRC is the primary join key (also the selector the renderer natively resolves), with
`content_sha256` then `streaminfo_md5` as fallbacks for ISRC-less identities. On the Taghag
side, `audio_file.file_key` already encodes whichever hash exists (`sha256:…` or
`checksum:streaminfo:…`; see `tools/taghag_import/extract_dj_slice.py:228-235`). The precedence
matters because sha256 alone covers a minority of master-zone identities in Tagslut's store —
**re-verify the exact counts against the live Tagslut DB before relying on this**, since the
original census numbers are not reproducible from this repo alone (they require live access to
`tag/slut`'s `music_v3.db` and to Supabase).

## What's already built (reuse, don't rebuild)

| Need | Already exists | Location |
|------|----------------|----------|
| Sonic neighborhood from a seed | `SonicDiscoveryIndex.similar_tracks()` | `tools/cuecifer/sonic_discovery.py` |
| Neighborhood crate generation + CLI command | `cuecifer crate --seed-id --out-dir --limit` | `tools/taghag_import/generate_neighborhood_crate.py`, wired in `cli.py` |
| Blended harmonic edge cost (Camelot + BPM-delta + handoff score) | `cue plan --seed --depth` pathfinder | `tools/taghag_import/advanced_cue_planner.py` |
| Transition/handoff scorer | `score_apple_transition()` | `tools/taghag_import/apple_handoff.py:23` |
| Camelot distance / mapping | `camelot_distance()` (Taghag), `to_camelot()` (Tagslut) | `generate_neighborhood_crate.py:18`, both repos |
| ISRC -> path resolution | `resolve_selector()` | `tag/slut/tagslut/playlist/resolver.py:92` |
| Identity-anchored M3U render with `.missing` sidecar | `render(source, conn, zone, out)` | `tag/slut/tagslut/playlist/renderer.py:24` |
| Playlist CLI surface (`--zone master/mp3/aac`) | `tagslut playlist …` | `tag/slut/tagslut/cli/commands/playlist.py` |

**The actual remaining gap** is the glue between the two existing command surfaces: nothing
today takes a Taghag `cuecifer crate` / `cue plan` JSON output and feeds it into a Tagslut
`playlist` command as an ordered, identity-keyed `PlaylistSource`. That bridge — not new
analysis or rendering engines — is the only new code this outcome needs.

## Milestones

### M0 — Roon smoke test (do this first, before any code)
Hand-write a 3-line `.m3u8` containing one known master FLAC absolute path under
`/Volumes/MUSIC/MASTER_LIBRARY/...`, drop it in Roon's watched folder, confirm it imports **and
plays**. This validates the path/mount assumption before any glue code is written. If Roon
won't import a watched-folder M3U, the output format or delivery mechanism is wrong — discover
that on day one, not after the bridge is built.

### M1 — Join census (the one unresolved number)
Run a read-only check of how many Taghag-analyzed master FLACs (rows in
`apple_derived_features` joined to `audio_file` where `codec = 'flac'`) intersect with
Tagslut's master-zone resolvable identities (by ISRC, then sha256, then streaminfo_md5). If the
intersection is near zero, there is nothing for the brain to order yet — run the Apple analyzer
over the master FLACs before proceeding to M2.

### M2 — Taghag: ordered-neighborhood emitter
Extend the existing `cuecifer crate` / `cue plan` surface (rather than adding a third
parallel command) to emit ordered JSON in the interchange shape below, restricted to whatever
identity intersection set M1 establishes. The handoff scorer should be additive, not a gate:
order on Camelot + BPM-delta when `apple_derived_features` rows are absent for a candidate, and
layer in `score_apple_transition()` where they exist — this is already how
`advanced_cue_planner.py` degrades (handoff cost falls back to 0 when Apple features are
missing).

### M3 — Tagslut: resolve + render bridge
Add a `tagslut playlist from-neighborhood <json> --zone master -o out.m3u8` command that:
1. Resolves each ordered item to a `Selector` — `isrc:` primary, else a sha256/streaminfo_md5
   lookup.
2. Builds a `PlaylistSource` with one entry per item **in order** and calls
   `render(..., zone="master")`.
3. Relies on the existing `.missing` sidecar behavior for any item that doesn't resolve, rather
   than silently dropping it — a silent drop in the middle of an ordered run (A→B→C becoming
   A→C) would ship an untested transition without anyone knowing.

## Interchange contract (the seam)

```json
[
  { "isrc": "GBxxx1234567", "content_sha256": "...", "streaminfo_md5": "...",
    "artist": "...", "title": "...", "bpm": 124.0, "camelot": "8A",
    "transition_cost": 0.0, "position": 0 }
]
```

Stable, neutral, store-agnostic. Either side can be tested against a fixture of this shape with
the other store absent.

## Risks / open items

- **Join census (M1)** is the only true unknown and must be re-run against live data; the
  numbers in the superseded plan are not reproducible from this repo and should not be cited as
  current fact.
- **Key notation variance**: `musical_key` values may be Camelot (`8A`), spelled (`A minor`),
  or come from different providers. `camelot_distance()` in
  `generate_neighborhood_crate.py:18-41` returns a 999.0 sentinel for unparseable keys — ensure
  the planner falls back to BPM-delta ordering rather than letting an unparseable key poison a
  transition cost.
- **Roon on another machine**: paths only resolve if `/Volumes/MUSIC` is mounted on whichever
  machine runs Roon. Out of scope for this slice, but the watched-folder approach assumes the
  same mount path everywhere Roon imports the file.
- **Apple coverage is gated**: `apple_derived_features` only exists for tracks passing
  eligibility gates (duration, BPM consistency, sections, drum activity). The handoff score is
  an enhancement over a Camelot+BPM baseline, never a prerequisite for M2/M3.

## Definition of done

One harmonically-ordered, ISRC-anchored `.m3u8` of master FLACs renders from a seed via the new
`from-neighborhood` bridge, drops into Roon, and plays through start to finish — read-only,
reversible, zero schema change.
