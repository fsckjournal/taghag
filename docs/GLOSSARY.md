# Taghag Glossary — canonical vocabulary

The single source of truth for what every term, tool, and concept means. If a name
here disagrees with an older doc, **this file wins** — older docs (`docs/archive/`,
`docs/reports/`, `docs/management/`) are historical snapshots and may use legacy
names (notably `cuecifer`, `magikbox`, `butterflow`).

Naming principle: **components are named by function, not by brand.** The only proper
nouns are the two products/repos (`Taghag`, `Tagslut`). Everything inside is plain and
descriptive.

## The two layers

| Term | Meaning |
| --- | --- |
| **Tagslut** | The *Backbone*. Identity, provenance, acquisition, safety. System of record. Taghag is read-only on it. Join keys: `content_sha256`, ISRC. |
| **Taghag** | The *Brain*. Audio understanding + mixing. Everything below. |

## The pipeline — seven stages

Every tool belongs to exactly one stage. If something doesn't fit a stage, it's
misnamed or redundant.

```
AUDIO (FLAC master, owned by Tagslut)
  ① ANALYZE   raw MIR from the waveform          → apple-analyzer
  ② DESCRIBE  MIR → interpretable scalars/vectors → apple_*.py
  ③ RELATE    vectors → "which tracks sound alike" → similarity/
  ④ SEQUENCE  a track set → an ordered crate       → similarity/ + build_render_plan.py
  ⑤ PLAN      per-transition: cues, key, grid      → advanced_cue_planner.py
  ⑥ RENDER    crate + plan → continuous audio      → mixslice/
  ⑦ DELIVER   audio → Roon plays it                → FLAC + CUE in a watched folder
```

## Terms, tools & concepts

| Term | Canonical meaning | Stage | Legacy name |
| --- | --- | --- | --- |
| **apple-analyzer** | Swift binary wrapping Apple MusicUnderstanding. Deterministic MIR JSON (BPM, key, beats, segments, loudness, instrument activity). FLAC-native. Dir `tools/apple-analyzer/`, binary `apple_analyzer`, sidecar cache `<flac>.analyzer.json`. | ① | `cuecifer-analyzer` / `cuecifer_analyzer` |
| **Apple Music Understanding** | Apple's closed framework the analyzer wraps. The *vendor*, not our tool. macOS 26/27+. | ① | — |
| **`apple_*.py`** | Feature engineering: `apple_derived_features` (MIR→scalars), `apple_hybrid_vector` (→`apple_hybrid_v1`), `apple_music_adapter` (runs the analyzer, writes DB), `apple_handoff` (transition-score handoff), `apple_disagreement_report`. | ② | `apple_butterflow` → `apple_handoff` |
| **`apple_hybrid_v1` / `sonic7_v1`** | The two pgvector embeddings. `sonic7_v1` = 7-dim sonic identity; `apple_hybrid_v1` = interpretable Apple-derived. | ② | — |
| **similarity** | Python engine: pgvector similarity search, producer vibes, neighborhood crates, PCA `map`. Package `tools/similarity/`, import `from similarity.X`, CLI group `taghag-import similarity …`. | ③④ | `cuecifer/`, `magikbox/` |
| **producer vibes** | Human-curated `[TS: …]` annotations (in ID3 COMM frames) describing a track's sonic character; fed back into similarity. | ③ | — |
| **advanced_cue_planner** | Per-transition planning: Camelot/key distance, Rekordbox ANLZ cue import, transition scoring (`TransitionPlanner`). | ⑤ | `ButterFlowPlanner` → `TransitionPlanner` |
| **rigid grid** | Constant-tempo beatgrid `phase + i·(60/BPM)`, *consumed* from a DJ app — never computed by us. Source: `rbx-re.xml` `AverageBpm` + first `POSITION_MARK` cue = phase. | ⑤ | — |
| **render_plan.json** | The handoff artifact: an ordered, filtered, gridded track list. Built by `build_render_plan.py`; consumed by the renderer. | ④→⑥ | — |
| **mixslice** | The renderer. `grid_mix.py` = one wobble-free transition (rigid grid, single-ratio warp); `chain_mix.py` = stitch all → one FLAC + CUE. `render_transition.py` = OLD (has the wobble); donor for DSP only. | ⑥ | — |
| **Roon** | Player + control plane only — no DSP/stream injection. Our FLAC+CUE goes in a watched folder; Roon plays it gapless. Our offline render IS the product. | ⑦ | — |
| **time_base** | Re-zeroing cues onto the canonical master-FLAC clock. Cross-cutting. | — | — |
| **MIK-cues** | `rekordbox_mikcues_001.xml` — Mixed-In-Key energy cues in absolute seconds. **Use this** for mix-in/out zones. | ⑤ | "MIK" (ambiguous) |
| **MIK-db** | `Collection11.mikdb` — MIK's Core Data collection pointing mostly at transcodes. **Ignore.** | — | "MIK" (ambiguous) |

## The one architectural truth: SEQUENCE is implemented twice

Stage ④ exists in two places that were never reconciled:

- **similarity** sequences by *sonic similarity* — seed → pgvector neighborhood → ordered crate.
- **`build_render_plan.py`** sequences by *importing Spotify's mix-mode order* (`Minimal Focus.txt` column `#`).

These are the same conceptual stage. The intended model:

> **similarity produces the ordered crate; mixslice renders it.** They're adjacent, not rivals — `render_plan.json` is the handoff.

So Spotify-import is **one sequencing strategy among several** that belongs *inside* the
similarity engine, all emitting the same `render_plan.json` shape:
- `strategy=spotify` — import a pre-solved order (cheap, validated)
- `strategy=sonic` — pgvector neighborhood walk
- `strategy=harmonic` — Camelot-constrained path (`advanced_cue_planner`)

## Dead names — do not reintroduce

- **cuecifer** → split into `apple-analyzer` (①) and `similarity` (③④).
- **magikbox** → `similarity`.
- **butterflow** → `TransitionPlanner` (class) / `apple_handoff` (module).

## What was intentionally NOT renamed

- **Migration files** (`supabase/migrations/*cuecifer*.sql`) — immutable history; the live
  table is `public.track_analysis`, not named `cuecifer`.
- **`docs/archive/`, `docs/reports/`, `docs/management/`** — historical snapshots.
