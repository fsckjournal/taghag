# Time-Base Anchor — design

**Status:** design (2026-06-21) · **Follows:** `tagslut/docs/audit/2026-06-21-cue-coregistration-probe.md`
**Problem:** `track_cue.time_ms` / `track_segment.ms_start` store positions from four clocks (`human`, `mixonset`, `iwebdj_cloud`, `anlz`, soon `apple`) in one column with no provenance. The probe measured a fixed **~17 ms** offset between `human` and `mixonset` grids on the same track — structural agreement, clock disagreement. Fusing them today averages un-zeroed clocks.

## Goal
Make every cue/segment expressible on **one canonical clock = master-FLAC PCM sample 0, at the FLAC sample rate**, without rewriting existing `time_ms`. Additive, non-destructive, backward-compatible.

## Canonical clock
For an identity, the **canonical rendition** is the master FLAC (`audio_file` row that is its own master: `master_file_id IS NULL` AND `codec='flac'` AND a master path, or the row another points to via `master_file_id`). Canonical time is **milliseconds from PCM sample 0 of that FLAC**. FLAC has no encoder priming, so the FLAC's own grid is canonical by definition (offset 0).

A measurement made against any *other* rendition R (an MP3, an AAC Apple analyzed, Beatport's stream) carries an unknown constant offset to canonical, caused by encoder delay/padding and trim. We **record which rendition each measurement used** and **store one reconciled offset per (rendition, source)** so re-zeroing is a subtraction — no per-consumer priming math.

## Schema additions (all additive; `IF NOT EXISTS`)

### 1. Rendition geometry — `audio_file`
```sql
ALTER TABLE public.audio_file ADD COLUMN IF NOT EXISTS sample_rate_hz integer;
ALTER TABLE public.audio_file ADD COLUMN IF NOT EXISTS encoder_delay_samples integer; -- priming; FLAC=0, AAC≈2112/2624, MP3≈576+
```
`duration_s`, `codec`, `master_file_id`, `checksum_sha256` already exist and are reused.

### 2. Clock provenance — `track_cue` and `track_segment`
```sql
ALTER TABLE public.track_cue     ADD COLUMN IF NOT EXISTS measured_against_file_id uuid REFERENCES public.audio_file(id);
ALTER TABLE public.track_cue     ADD COLUMN IF NOT EXISTS time_base text NOT NULL DEFAULT 'unknown'
    CHECK (time_base IN ('master_flac','rendition','external_grid','unknown'));
-- identical two columns on track_segment
```
- `measured_against_file_id` — the exact rendition the source analyzed. NULL ⇒ unknown/legacy.
- `time_base` — `master_flac`: `time_ms` is already canonical (offset 0). `rendition`: measured against `measured_against_file_id`, needs an offset. `external_grid`: a reconstructed grid (Beatport) with no decoded rendition — needs offset by anchor/correlation. `unknown`: legacy rows.

### 3. Reconciled offsets — new table `rendition_time_offset`
One row per (canonical rendition, source rendition, source_system). `canonical_ms = measured_ms − offset_ms`.
```sql
CREATE TABLE IF NOT EXISTS public.rendition_time_offset (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id            uuid NOT NULL,
  audio_file_id            uuid NOT NULL REFERENCES public.audio_file(id),  -- canonical (master FLAC)
  measured_against_file_id uuid REFERENCES public.audio_file(id),           -- source rendition; NULL for external grids
  source_system            text NOT NULL,
  offset_ms                numeric NOT NULL,        -- add to canonical to get measured; subtract to canonicalize
  offset_method            text NOT NULL CHECK (offset_method IN
                             ('identity','declared_priming','downbeat_anchor','cross_correlation')),
  residual_ms              numeric,                 -- calibration tightness (lower = better)
  confidence               real NOT NULL DEFAULT 0.0,
  computed_at              timestamptz NOT NULL DEFAULT now(),
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now(),
  UNIQUE (audio_file_id, measured_against_file_id, source_system)
);
```
**RLS:** every existing table carries `owner_user_id` and is RLS-governed on Supabase. `rendition_time_offset` must enable RLS and **mirror the exact owner-scoped policy of `track_cue`/`track_segment`** (a new table left without policy is either inaccessible or over-exposed). Run `get_advisors` after applying and clear anything it flags.

### 4. Canonical views (consumers read these, never raw `time_ms`)
```sql
CREATE OR REPLACE VIEW public.track_cue_canonical AS
SELECT c.*,
  CASE
    WHEN c.time_base = 'master_flac' THEN c.time_ms::numeric
    ELSE c.time_ms - COALESCE(o.offset_ms, 0)
  END AS canonical_time_ms,
  (c.time_base IN ('rendition','external_grid') AND o.offset_ms IS NULL) AS offset_missing
FROM public.track_cue c
LEFT JOIN public.rendition_time_offset o
  ON  o.audio_file_id = c.audio_file_id
  AND o.measured_against_file_id IS NOT DISTINCT FROM c.measured_against_file_id
  AND o.source_system = c.source_system;
-- analogous track_segment_canonical with canonical_ms_start / canonical_ms_end
```
**Join must mirror the offset table's UNIQUE key** `(audio_file_id, measured_against_file_id, source_system)` — all three columns, or a NULL `measured_against_file_id` (Beatport external grids) fans the cue out across every Beatport offset row and multiplies/­corrupts the view. The `o.audio_file_id = c.audio_file_id` term is mandatory, not optional.

`offset_missing = true` flags rows that *cannot yet* be trusted on the canonical clock — only `rendition`/`external_grid` rows that lack an offset. **Legacy `unknown` rows are passthrough, NOT missing**: they keep raw `time_ms` and `offset_missing=false` (we can't claim they're wrong, only un-anchored), so the planner does not drop the 12,832 existing human/mixonset cues. A consumer that wants *only* canonically-anchored cues filters `time_base IN ('master_flac') OR (NOT offset_missing AND time_base IN ('rendition','external_grid'))`; the default view keeps everything visible.

## Re-zeroing routine (`time_base.py`, new module)
`reconcile_offset(canonical_file, source_file, source_system, cues) -> RenditionTimeOffset` picks the strongest available method:

1. **identity** — `source_file is canonical` (FLAC vs itself): `offset_ms=0, residual_ms=0, confidence=1`.
2. **declared_priming** — known codec priming: `offset_ms = encoder_delay_samples / sample_rate_hz * 1000`. Cheap first guess.
3. **downbeat_anchor** — align the source's first strong beat to the FLAC's detected first downbeat: `offset_ms = beat_source_ms − beat_canonical_ms`. Works from existing beatgrids, no full decode.
4. **cross_correlation** — decode both to PCM mono, correlate onset-strength envelopes, take the lag (librosa). Most robust; **also validates** the cheaper methods — `residual_ms` = disagreement between methods.

Direction: `canonical = measured − offset_ms`. The probe's human↔Mixonset case must yield `offset_ms ≈ +17, residual ≈ 0` — that pair is the **calibration test fixture** for the routine.

## Apple phrase-timestamp fix (`apple_derived_features.py`)
Today `compute_derived_features` reduces `structure.{sections,segments,phrases}` to counts and intro/outro *durations* — the absolute boundary positions are discarded. Add:

```python
def extract_structure_boundaries(raw_json) -> list[dict]:
    """Absolute section/phrase boundaries in Apple CMTime ms, role-tagged."""
    # for each section/phrase: start_ms = _cmtime_seconds(range.start)*1000
    #                          end_ms   = start_ms + _range_duration_ms(...)
    # role from section kind (intro/outro/peak/breakdown/phrase)
```
These ms are in **Apple's CMTime base = the artifact Apple analyzed** (identified by the existing `apple_derived_features.source_artifact_sha256`). The importer persists them to `track_segment` with `source_system='apple'`, `time_base='rendition'`, and `measured_against_file_id` = the `audio_file` whose `checksum_sha256` matches `source_artifact_sha256` (the offset row then re-zeros them onto the FLAC). Scalars stay unchanged; this is purely additive.

## Backward compatibility
Existing 12,832 cues / 846 segments get `time_base='unknown'`, `measured_against_file_id=NULL`, no offset row → the views fall through to raw `time_ms` and `offset_missing=false` (we can't claim they're wrong, only that they're un-anchored). Nothing is rewritten or dropped. The 17 ms `human`/`mixonset` evidence is corrected only once a reconciled offset row is inserted.

## Out of scope (later)
Backfilling `measured_against_file_id` for legacy rows; the `human` cue quadruple-insert dedup; negative `mixonset.confidence` handling; ingesting Beatport/Apple at scale. This change makes a correct cue *representable* and re-zeroable — it does not re-ingest history.
