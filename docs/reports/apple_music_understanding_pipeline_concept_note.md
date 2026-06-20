# Apple Music Understanding Pipeline — Technical Concept Note

**Date:** 2026-06-20
**Status:** Component-verified (106 tests green; analyzer→derived-features→vector reproduced on a real track). The three defects below are fixed and a new MIK energy cross-check is wired in. End-to-end DB ingestion still not exercised this session (no live Supabase creds).
**Purpose:** Explain the deterministic Apple Music Understanding workflow now in the Taghag codebase, report on its success with reproducible evidence, and serve as the basis for (a) reviewing stale documentation and (b) deciding the fate of legacy vector scripts. This note **recommends**; it does not perform the doc edits or script moves.

---

## TL;DR

- The pipeline takes a local **FLAC** → Apple's on-device Music Understanding (via a compiled Swift CLI) → raw JSON → Python adapter → normalized Postgres tables + **deterministic derived scalars** → an interpretable `apple_hybrid_v1` pgvector + Butter Flow transition scoring + an Apple-vs-legacy disagreement audit.
- The previous build **deleted the `fm-reviewer` LLM path and `apple_fm_pipeline.py`**, replacing them with deterministic feature engineering. This aligns the code with the architecture doc's explicit rule: *"Don't Put LLMs in Hot Path — Use Music Understanding's deterministic outputs instead"* ([apple_music_understanding_integration.md:350](../architecture/apple_music_understanding_integration.md)).
- **It works on real audio.** Running the compiled analyzer on a real techno track produced 770 beats, 24 sections, 95 phrases, and a 7D hybrid vector — see [Success Report](#success-report).
- Real-data validation surfaced **three concrete defects** the synthetic unit tests hid (`apple_key` parsing, pace-vector saturation, an unwired `bpm_agreement_score`) — all three are now fixed, see [Gaps Found and Fixed](#gaps-found-and-fixed-by-real-data-validation).
- Rekordbox is now wired in as the **BPM owner**, and Mixed In Key's manually-curated energy cues are cross-checked against Apple's automatic pace curve via a new `energy_agreement_score` — see [Rekordbox/MIK Cross-Checks](#rekordbox-as-bpm-owner-and-the-mik-energy-cross-check).

---

## The Workflow

```text
local FLAC file
  → Swift Music Understanding extractor      (cuecifer-analyzer, compiled binary)
  → raw SessionResult JSON                    (key/rhythm/structure/pace/instrument/loudness)
  → Python ingestion adapter                  (apple_music_adapter.py)
  → normalized Postgres tables                (apple_analysis_runs, apple_track_analysis, segments, cues, loudness curves)
  → deterministic derived scalars             (apple_derived_features.py → apple_derived_features table)
  → interpretable Apple-hybrid pgvector       (apple_hybrid_vector.py → track_embedding, schema apple_hybrid_v1)
  → Butter Flow transition scoring            (apple_butterflow.py)
  → Apple-vs-legacy disagreement audit        (apple_disagreement_report.py / `apple-audit`)
```

Mapped to the architecture doc's 8-phase roadmap:

| Phase | Roadmap item | Module(s) | Status |
|-------|--------------|-----------|--------|
| 0–1 | Swift extractor → JSON | `cuecifer-analyzer` (binary present) | ✅ |
| 2 | Raw JSON provenance | `apple_analysis_runs` table (migration `20260619000000`) | ✅ |
| 3 | Normalization (sections, segments, phrases, beats, bars, loudness series) | `apple_music_adapter.py` | ✅ |
| 4 | Derived scalars (pace stats, key stability, intro/outro, vocal/drum/bass, loudness range, MIK energy agreement) | `apple_derived_features.py` | ✅ |
| 5 | Apple-hybrid vector | `apple_hybrid_vector.py` (`apple_hybrid_v1`, 7D) | ✅ |
| 6 | Butter Flow planner scoring | `apple_butterflow.py` | ✅ |
| 7 | Disagreement audit | `apple_disagreement_report.py`, `apple-audit` CLI | ✅ |
| 8 | Export integrations (Roon/Rekordbox tag write-back gated on agreement) | — | ⏳ not built |

---

## Why This Workflow Is Useful

1. **Deterministic, not generative.** Every downstream feature is pure arithmetic over Apple's MIR outputs (`statistics.mean`, `stdev`, range subtraction). The same FLAC yields the same scalars every run — auditable and diff-able, with no model-drift in the hot path.
2. **On-device, offline, free.** Apple's framework runs locally; no API cost, no network, no rate limits, and no audio leaves the machine.
3. **Raw output is preserved.** `apple_analysis_runs.raw_result_json` (jsonb, keyed by `source_artifact_sha256`) keeps the full SessionResult so any derived feature can be recomputed or explained after the fact — satisfying the doc's *"Don't Discard Raw JSON"* directive.
4. **Legacy data is not overwritten.** Apple scalars land in their own tables; `apple_hybrid_v1` is a *new* vector schema alongside the legacy embedding. The `apple-audit` report flags Apple-vs-legacy disagreement instead of silently trusting one source.
5. **Structure the legacy stack never had.** 24 sections / 48 segments / 95 phrases per track (real numbers below) give the planner phrase-boundary cut points that the old BPM/energy-only vector could not express.

---

## Success Report

All evidence below is reproducible from the current working tree.

### Test suite — real
```
$ cd tools && source .venv/bin/activate && python -m pytest -q
106 passed in 0.20s
```

### Real-track run — real (not synthetic), post-fix

Track: **Layton Giordani – New Generation (Space 92 Remix) [Extended]** (FLAC on `/Volumes/PLAYGROUND`).
Command run: the compiled Swift analyzer → 8.5 MB JSON (all six feature keys present) → `compute_derived_features` (with an illustrative `reference_bpm=134.0`, since this track is not in either Rekordbox XML) → `build_apple_hybrid_vector`.

```jsonc
// REAL apple_derived_features output, after the apple_key and bpm_agreement_score fixes
{
  "apple_bpm": 135.0,
  "beat_count": 770,           "bar_count": 193,
  "key_stable": true,          "key_change_count": 0,
  "apple_key": "E Minor",      // fixed -- was null, see Gaps Found and Fixed
  "loudness_integrated": -5.67, "loudness_peak": -0.0, "loudness_range_db": 5.67,
  "loudness_mean": -5.88,      "loudness_std": 1.76,
  "pace_mean": 21.8,           "pace_median": 16.88, "pace_volatility": 9.14,
  "pace_max": 33.75,           "pace_min": 8.44,
  "energy_agreement_score": null,  // null here -- no MIK cues exist for this untagged track
  "section_count": 24,         "segment_count": 48,  "phrase_count": 95,
  "intro_length_ms": 14222,    "outro_length_ms": 14222,
  "has_vocal_activity": false, "vocal_intensity_mean": 0.009,
  "has_drum_activity": true,   "drum_intensity_mean": 0.79, "bass_intensity_mean": 0.35,
  "bpm_agreement_score": 0.926  // now non-null once reference_bpm is supplied
}
```

```text
// REAL apple_hybrid_v1 vector, after the pace-calibration fix
dims: [apple_bpm_norm, pace_mean, pace_volatility, vocal_intensity_mean, drum_intensity_mean, bass_intensity_mean, loudness_range_norm]
vec : [0.675, 0.545, 0.2285, 0.009, 0.79, 0.35, 0.189]
```

Before the fix, `pace_mean`/`pace_volatility` both saturated to `1.0` (see git history); they now sit at 0.545/0.2285, distinguishing this track from lower-pace material on those two axes.

The numbers are musically sane for a 135-BPM peak-time techno tool: instrumental (vocal 0.009, `has_vocal_activity: false`), drum-led (0.79), loud and compressed (5.67 dB range), with a dense 95-phrase structure.

### MIK legacy adapter — real, now path-matched against both XML exports

```
$ python -c "from taghag_import.mik_xml_adapter import get_mik_energy_shifts, get_mik_bpm; ..."
MIK Gossip shifts count: 8   BPM: 123.0
First 3 shifts: [{'time_s': 1.35, 'energy': 4}, {'time_s': 48.18, 'energy': 6}, {'time_s': 79.4, 'energy': 6}]
```

`get_mik_bpm`/`get_mik_energy_shifts` now match tracks by decoding Rekordbox's `Location` URL and comparing basenames, not just by parsing `Artist - Title` from the filename. This is the only way to use `rekordbox_mikcues_001.xml` at all, since that export carries no `Artist`/`Name` attributes — only `Location`. Rekordbox's `AverageBpm` (from `downloaded.xml`) is the BPM authority; MIK's per-cue `Energy N` markers (from `rekordbox_mikcues_001.xml`) are the energy authority, both now threaded into ingestion automatically via `apple_music_adapter.py`.

### What is NOT yet proven this session

- The **full FLAC → DB-rows → audit-CSV** path was not run end-to-end (it requires live Supabase credentials). What is verified is component-level: analyzer output, derived-feature computation, vector construction, the MIK/Rekordbox adapter against real XML exports, and the 106-test suite. Do not read the success above as a corpus-wide ingestion run.
- `energy_agreement_score` has not been observed non-null on a real track in this session, because no single track in the working tree has both a real Apple analyzer run *and* real MIK energy cues. The score's correctness is verified by unit tests built directly from the real pace-curve shape (`_REAL_PACE_CURVE` in [test_apple_derived_features.py](../../tools/tests/test_apple_derived_features.py)), not by an end-to-end run on one track.

---

## Replicability

The Swift binary is already compiled at
`tools/cuecifer-analyzer/.build/release/cuecifer_analyzer`.

**1. Analyzer only (no DB), for inspecting raw JSON:**
```bash
./tools/cuecifer-analyzer/.build/release/cuecifer_analyzer "/path/to/track.flac" > track.cuecifer.json
```

**2. Full ingestion (analyzer + normalize + derive + vector → Supabase):**
```bash
cd tools && source .venv/bin/activate
taghag-import analyze --target "/path/to/flac-file-or-directory"
taghag-import analyze --target "/path/to/track.flac" --dry-run   # analyzer only, no DB writes
```

**3. Apple-vs-legacy disagreement audit:**
```bash
taghag-import apple-audit --out apple_disagreement.csv \
  --bpm-threshold-pct 2.0 --agreement-threshold 0.8
```

**4. Derived features + hybrid vector from a JSON file (what produced the real numbers above):**
```python
from taghag_import.apple_derived_features import compute_features_from_file
from taghag_import.apple_hybrid_vector import build_apple_hybrid_vector

features = compute_features_from_file("track.cuecifer.json", filename="track.flac")
vector   = build_apple_hybrid_vector(features)   # 7D, fits the existing pgvector column
```

The derived-feature math is small and self-contained — e.g. loudness range and pace volatility:
```python
features["loudness_range_db"] = round(peak_val - integrated_val, 2)
features["pace_volatility"]   = round(statistics.stdev(pace_values), 2)
```

---

## Gaps Found and Fixed by Real-Data Validation

Running on a real track (not the synthetic fixtures) exposed three defects, all now fixed:

1. **`apple_key` was null on every real track.** Apple's JSON encodes key as **strings** — `{"tonic": "e", "mode": "minor"}` — but the old code called `int(tonic)` / `int(mode)`, which raised and was swallowed to `None`. The unit test passed integer indices (`tonic: 7`) and masked the bug. **Fixed:** [apple_derived_features.py](../../tools/taghag_import/apple_derived_features.py) now has a `_format_key(tonic, mode)` helper that maps the real string encoding (with sharp/flat suffix handling), covered by real-string-encoded fixtures in [test_apple_derived_features.py](../../tools/tests/test_apple_derived_features.py).
2. **Pace dimensions saturated in the hybrid vector.** Real `pace_mean` is ~21.8 and `pace_volatility` ~9.14 (an unbounded, real-valued scale), but `build_apple_hybrid_vector` clipped both to `1.0`, so every energetic track looked identical on those two axes. The synthetic test used pace ≈ 3, hiding this. **Fixed:** both [apple_hybrid_vector.py](../../tools/taghag_import/apple_hybrid_vector.py) and [apple_butterflow.py](../../tools/taghag_import/apple_butterflow.py) now divide by `PACE_NORM_DIVISOR = 40.0` before clipping — single-track-calibrated and explicitly marked provisional in code; a larger corpus should re-derive this constant.
3. **`bpm_agreement_score` was effectively dead** without a robust way to find a track's Rekordbox/MIK row. The old `mik_xml_adapter.py` only matched by parsing `Artist - Title` out of the filename, which can't work at all against `rekordbox_mikcues_001.xml` (no `Artist`/`Name` attributes, only `Location`). **Fixed:** the adapter now decodes each `Location` URL and matches by basename first, falling back to the Artist/Title regex — verified against real tracks from both `downloaded.xml` and `rekordbox_mikcues_001.xml`.

A fourth item was added rather than fixed: **`energy_agreement_score`**, a new derived feature comparing the direction of MIK's manual energy-cue changes against Apple's automatic pace curve at the same timestamps — see [Rekordbox as BPM Owner and the MIK Energy Cross-Check](#rekordbox-as-bpm-owner-and-the-mik-energy-cross-check) below.

---

## Rekordbox as BPM Owner and the MIK Energy Cross-Check

Two real Rekordbox XML exports ground this section: `downloaded.xml` (full collection, rich `Artist`/`Name`/`AverageBpm`/`Tonality`, cue-sparse) and `rekordbox_mikcues_001.xml` (MIK's cue-dense export, only `TrackID`/`Location`/`TotalTime`).

- **Rekordbox is the BPM owner.** `mik_xml_adapter.get_mik_bpm(filename)` reads `AverageBpm` from `downloaded.xml` and is passed as `reference_bpm` into `compute_derived_features` during ingestion ([apple_music_adapter.py:294](../../tools/taghag_import/apple_music_adapter.py#L294)). Apple's own detected BPM is never overwritten — `apple_bpm` and the Rekordbox reference are compared, not merged, via `bpm_agreement_score`.
- **MIK's energy cues are the energy ground truth.** `mik_xml_adapter.get_mik_energy_shifts(filename)` parses `POSITION_MARK` cues named `Energy N` out of `rekordbox_mikcues_001.xml` (falling back to `downloaded.xml`) into a `[{"time_s", "energy"}, ...]` list, passed as `mik_energy_shifts` into the same call ([apple_music_adapter.py:295](../../tools/taghag_import/apple_music_adapter.py#L295)).
- **`energy_agreement_score`** ([apple_derived_features.py](../../tools/taghag_import/apple_derived_features.py)) walks consecutive MIK energy shifts, looks up Apple's pace value at each shift's timestamp via the piecewise-constant pace curve, and checks whether the *direction* of the energy change (up/down) matches the *direction* of the pace change. It returns `agreements / comparisons` rounded to 3 decimals, or `None` if there are fewer than two MIK shifts or no pace data — mirroring `bpm_agreement_score`'s null-when-uncomparable convention.
- Both scores are now surfaced together in `apple_disagreement_report.py`: a `low_bpm_agreement_score` or `low_energy_agreement_score` issue code is appended when either score drops below `--agreement-threshold`, giving two independent Apple-vs-manual-curation cross-checks in the same audit row.

---

## Basis for Documentation Review

Ingestion is **FLAC-only** (`stage.py` rejects any non-`.flac` source). MP3 survives legitimately only in **export/audit** tooling. So a flat "remove all MP3 mentions" sweep is wrong — the references split into two buckets:

**Bucket A — legitimate, describe live MP3 tooling (do NOT "fix"):** the CLI ships `audit-mp3`, `dump-tags`, and `write-tags` commands. Docs describing those are current.
- `docs/management/mp3_tools_provider_export_plan.md`
- `docs/architecture/dsp_metadata_integration.md`

**Bucket B — review for stale FLAC-vs-MP3 ingestion assumptions** (these describe the library/ingestion model, which is now FLAC-only):
- `docs/README.md`, `docs/management/project_brief.md`
- `docs/management/taghag_stage_pipeline_plan.md`, `docs/architecture/taghag_stage_pipeline_design.md`, `docs/architecture/manifest_stage_design.md`
- `docs/architecture/canonical_metadata_schemas.md`, `docs/architecture/supabase_database_schema.md`, `docs/architecture/dsp_metadata_integration.md`
- `docs/architecture/roon_extension_architecture.md`, `docs/architecture/roon_metadata_policy.md`
- `docs/architecture/autonomous_intelligence_engine_design.md`, `docs/guides/migration_reference.md`, `docs/guides/xcode_gemini_walkthrough.md`
- `docs/architecture/apple_music_understanding_integration.md`, `docs/reports/cuecifer_a_z_technical_report.md`

> Bucketed by filename + the live-command fact; the reviewer should confirm each before editing. Archived docs under `docs/archive/` are intentionally frozen and out of scope.

---

## Basis for Legacy-Script Disposition

The Essentia-era `sonic_vector` path was **not** fully migrated to `apple_hybrid_v1`. Two files reference the legacy vector — but they are **not interchangeable archival candidates**:

| File | Wiring | Recommendation |
|------|--------|----------------|
| [generate_neighborhood_crate.py](../../tools/taghag_import/generate_neighborhood_crate.py) | **Live** — backs the `cuecifer crate` CLI command ([cli.py:871](../../tools/taghag_import/cli.py#L871), [cli.py:1081](../../tools/taghag_import/cli.py#L1081)); queries `FROM public.sonic_analysis a` / `a.sonic_vector` | **Rewire to `apple_hybrid_v1`**, not archive. The `sonic_analysis.sonic_vector` column still exists (migration `20260611000000`), so the command is *not rewired*, not necessarily broken — but it ignores the new Apple vectors. |
| [tools/cuecifer/sonic_discovery.py](../../tools/cuecifer/sonic_discovery.py) | **Live dependency** — imported by `cuecifer/crates.py`, `map.py`, `human_correction.py`, `sync_vibes.py`, `__init__.py` | **Keep.** Despite the legacy name, it is load-bearing for the cuecifer package. Not archivable. |

Genuinely deleted already (no action needed, listed for the record): `fm-reviewer/` Swift package and `apple_fm_pipeline.py` — the LLM path the architecture doc warned against.

**Net archival recommendation:** there is no obsolete *script* to archive right now. The real work is the **`generate_neighborhood_crate.py` rewire** to consume `apple_hybrid_v1` embeddings, after which the legacy `sonic_analysis`/`sonic_vector` column can be deprecated in a dedicated migration.

---

## Recommended Next Steps (in order)

1. Run one full `analyze --target <dir>` against a small corpus with live Supabase creds to verify the end-to-end DB path (including the new `energy_agreement_score` column), then run `apple-audit` to produce the first disagreement CSV.
2. Re-derive `PACE_NORM_DIVISOR` (currently `40.0`, calibrated on a single track) once pace values from a larger corpus are available.
3. Rewire `generate_neighborhood_crate.py` / `cuecifer crate` onto `apple_hybrid_v1`.
4. Action the Bucket-B doc review; leave Bucket-A and `docs/archive/` untouched.
