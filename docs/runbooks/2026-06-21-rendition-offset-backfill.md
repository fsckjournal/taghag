# Runbook — rendition offset backfill

**Status:** operational (2026-06-21) · **Script:** `tools/scripts/backfill_rendition_offsets.py` · **Module:** `tools/taghag_import/time_base.py`

Backfills `rendition_time_offset` for **existing** human↔mixonset cue pairs so the canonical views re-zero them. New imports are reconciled **inline** by `MixonsetImporter._reconcile_mixonset_offset` (`tools/taghag_import/mixonset.py:84`); this script only corrects history.

---

## What it does

For every `audio_file` that already carries both `human` and `mixonset` cues:

1. Collects the `human` and `mixonset` grids (paged 1000 rows at a time, owner-scoped).
2. Votes the mixonset grid against the human grid via `reconcile_offset` (canonical = human, source = mixonset; `canonical_ms = measured_ms − offset_ms`).
3. If a confident offset is returned, `upsert_rendition_time_offsets([...])` it, then PATCHes the track's mixonset `track_cue` and `track_segment` rows to `time_base='rendition'`, `measured_against_file_id = <audio_file_id>`.
4. If `reconcile_offset` returns `None` (no/too-little structural overlap to vote), it **skips** — the cues correctly stay un-anchored / `offset_missing` rather than being fabricated as identity/zero.

## Idempotency

Safe to re-run. Offsets upsert on the unique key `(audio_file_id, measured_against_file_id, source_system)`; the cue/segment PATCH is a constant assignment. Re-running recomputes from the current grids and overwrites — no duplication, no fan-out.

## How to run

Run from the `tools/` directory (so `scripts.` and `taghag_import.` imports resolve):

```bash
cd tools
python -m scripts.backfill_rendition_offsets --dry-run   # compute + print, write nothing
python -m scripts.backfill_rendition_offsets             # write
```

Required environment (read by `DatabaseConfig`, see `tools/taghag_import/config.py`):

| Var | Purpose |
| --- | --- |
| `TAGHAG_SUPABASE_URL` | PostgREST base URL |
| `TAGHAG_SUPABASE_SERVICE_ROLE_KEY` (or `TAGHAG_SUPABASE_SECRET_KEY`) | service-role key (bypasses RLS for the backfill) |
| `TAGHAG_OWNER_USER_ID` | owner whose cues are reconciled (e.g. `d4c61173-8432-432f-b238-9bd72c7285e3`) |
| `TAGHAG_DB_POSTGRES_URL` / `DATABASE_URL` | optional direct Postgres URL |

> **Caveat:** the script currently calls `DatabaseConfig.from_env()`, but `config.py` exposes the constructor as `read_database_config()`. If `from_env` is not aliased onto `DatabaseConfig` in your tree, the run will `AttributeError` at startup — invoke the equivalent flow through `read_database_config()` or add the alias. This runbook documents intended behaviour; do not change code without a separate task.

Expected console output (one line per track):

```
Found 11 tracks with both human and mixonset cues.
  0c77e5b8...: offset=+12.25ms residual=1.25 conf=0.865 (cross_correlation)
  ...
  SKIP 9a35d116...: too little overlap to vote
Done. reconciled=6 skipped=5
```

## Verify via the canonical views

Confirm offsets landed and the views re-zero without fan-out (all SQL owner-scoped; substitute `:owner`):

```sql
-- offset rows written by the backfill
select audio_file_id, source_system, offset_ms, residual_ms, confidence, offset_method
from rendition_time_offset
where owner_user_id = :owner and source_system = 'mixonset'
order by offset_ms;

-- a re-zeroed track: canonical = measured − offset (e.g. 3e08a729 → −17.75 ms)
select source_system, time_base, time_ms, canonical_time_ms, offset_missing
from track_cue_canonical
where audio_file_id = :file_id and source_system = 'mixonset'
order by time_ms;

-- no row fan-out: canonical view row count must equal base table count
select (select count(*) from track_cue where owner_user_id = :owner)            as base,
       (select count(*) from track_cue_canonical where owner_user_id = :owner)  as canonical;
```

## Roll forward (new tracks)

No action — the importer does it inline. On each mixonset import, cues/segments are stamped `time_base='rendition'` + `measured_against_file_id` and `_reconcile_mixonset_offset` votes against the track's human grid, upserting the offset and bumping the `offsets_reconciled` stat. Run the backfill only after bulk historical loads or after a vote/grid algorithm change.

## Monitoring / evaluation

```sql
-- offset coverage: mixonset cues anchored vs still offset_missing
select offset_missing, count(*)
from track_cue_canonical
where owner_user_id = :owner and source_system = 'mixonset'
group by offset_missing;
-- expected after backfill: 183 anchored (false), 152 offset_missing (true), 335 total

-- time_base distribution (legacy 'unknown' = passthrough, not missing)
select source_system, time_base, count(*)
from track_cue
where owner_user_id = :owner
group by source_system, time_base
order by source_system, time_base;

-- offsets missing an offset row (tracks that couldn't vote)
select distinct c.audio_file_id
from track_cue_canonical c
where c.owner_user_id = :owner and c.source_system = 'mixonset' and c.offset_missing;

-- residual distribution & confidence thresholds (flag wide/low-confidence rows)
select offset_method,
       count(*)                       as rows,
       round(avg(offset_ms)::numeric, 2)   as mean_offset_ms,
       round(avg(residual_ms)::numeric, 2) as mean_residual_ms,
       round(min(confidence)::numeric, 3)  as min_conf
from rendition_time_offset
where owner_user_id = :owner
group by offset_method;

-- low-confidence offsets to eyeball (e.g. residual > 3 ms or confidence < 0.5)
select audio_file_id, offset_ms, residual_ms, confidence
from rendition_time_offset
where owner_user_id = :owner and (residual_ms > 3 or confidence < 0.5)
order by confidence;
```

Healthy state: every `rendition` cue is either anchored (`offset_missing=false`) or a known skip; `unknown` cues stay passthrough; canonical and base row counts match exactly.
