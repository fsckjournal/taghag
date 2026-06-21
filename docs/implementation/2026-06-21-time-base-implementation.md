# Time-Base Anchor — implementation record

**Status:** implemented (2026-06-21) · **Design:** `docs/design/2026-06-21-time-base-anchor.md` · **Migration:** `supabase/migrations/20260621000000_time_base_anchor.sql`

What was actually built to make every cue/segment re-zeroable onto one canonical clock (master-FLAC PCM sample 0), additively and non-destructively. Direction throughout: **`canonical_ms = measured_ms − offset_ms`**.

---

## 1. Schema — `supabase/migrations/20260621000000_time_base_anchor.sql`

Additive-only, idempotent (`if not exists` / `pg_policies` guards), backward-compatible.

- **Rendition geometry** on `audio_file` (lines 6–9): `sample_rate_hz integer`, `encoder_delay_samples integer` (FLAC=0, AAC≈2112/2624, MP3≈576+).
- **Clock provenance** on `track_cue` and `track_segment` (lines 12–28): `measured_against_file_id uuid` (FK to `audio_file`) and `time_base text not null default 'unknown'` with a CHECK in `('master_flac','rendition','external_grid','unknown')`. Both FK columns are indexed.
- **`rendition_time_offset`** table (lines 33–48): one row per `(audio_file_id, measured_against_file_id, source_system)` — that triple is the `unique` key. Carries `offset_ms`, `offset_method` (CHECK matches the four method constants in `time_base.py`), `residual_ms`, `confidence`, `owner_user_id`, timestamps. RLS enabled with owner-scoped select/insert/update/delete policies mirroring `track_cue`/`track_segment` (lines 63–103).
- **Canonical views** `track_cue_canonical` / `track_segment_canonical` (lines 107–137), `security_invoker = true`. They `left join` the offset table on **all three** key columns (`audio_file_id`, `measured_against_file_id` via `is not distinct from`, `source_system`) — the 3-column join prevents row fan-out. They expose `canonical_time_ms` (or `canonical_ms_start`/`canonical_ms_end`) and a boolean `offset_missing` that is true only for `rendition`/`external_grid` rows lacking an offset. Legacy `unknown` rows fall through to raw `time_ms` with `offset_missing=false` (un-anchored, not wrong).

## 2. Re-zeroing module — `tools/taghag_import/time_base.py`

Pure-Python, dependency-free (except the optional librosa path). Public API:

- **`RenditionTimeOffset`** dataclass (`time_base.py:47`) — a reconciled offset; `.to_row(owner_user_id)` (`:59`) shapes it as a `rendition_time_offset` upsert row.
- **`GridAlignment`** dataclass (`:73`) — result of correlating two grids: `offset_ms`, `residual_ms` (MAD of contributing diffs), `votes`, `agreement`.
- **`grid_offset(canonical_cues_ms, source_cues_ms, *, eps_ms=8.0, window_ms=60.0)`** (`:83`) — the histogram-vote cross-correlation. Collects every pairwise `source − canonical` diff within `window_ms`, finds the diff value with the most neighbours inside `eps_ms` (the histogram peak), returns its mean as the offset and the MAD as the residual. Non-corresponding cues scatter and form no peak; corresponding cues pile up at the true lag. Returns `None` when no pair falls within `window_ms`. De-dupes the human quadruple-insert via `_dedupe` (`:276`).
- **`reconcile_offset(...)`** (`:135`) — picks the strongest method the inputs support. Method constants at `:41–44`.

  Method preference order (the non-obvious design choice): **`cross_correlation` runs *before* `identity`** (`:163` then `:184`). A confident grid vote (votes ≥ `min_votes`, default 3) is the only method that *measures* the real lag, so it wins even when `source_file_id == canonical_file_id` — e.g. mixonset reading the same FLAC but emitting a lagged grid. `identity` (offset 0, confidence 1) fires only when the source IS the canonical file **and no grids were supplied** (`:187` `not (canonical_cues_ms and source_cues_ms)`). Crucially, a *failed* vote does not fall through to a fabricated identity: it returns `None`, leaving cues honestly `offset_missing`. Then `downbeat_anchor` (`:200`, confidence 0.6) and `declared_priming` (`:212`, `encoder_delay_samples / sample_rate_hz * 1000`, confidence 0.4). `None` when no method has its inputs.
- **`pcm_cross_correlation(canonical_path, source_path, ...)`** (`:226`) — decodes both renditions and correlates librosa onset-strength envelopes for the lag. **librosa-gated:** returns `None` immediately if `librosa`/`numpy` are absent (`:240–244`). The current toolchain has neither, so this path is dormant; the grid vote is the workhorse.
- **`_grid_confidence`** (`:270`) maps `agreement × tightness` (tightness from residual/eps) onto [0, 1].

## 3. Importer — `tools/taghag_import/mixonset.py`

- Imports `reconcile_offset` (`:14`).
- **Inline stamping:** mixonset cues and segments are written with `time_base='rendition'` and `measured_against_file_id = audio_file_id` (cues `:315–317`, segments `:336–337`) — they record the rendition they were measured against so the offset re-zeros them.
- **`_reconcile_mixonset_offset(audio_file_id, owner_user_id, mixonset_cue_rows)`** (`:84`) — after insert, fetches the track's `human` cues, votes the mixonset grid against them via `reconcile_offset` (canonical = human grid, source = mixonset grid), and upserts the resulting `rendition_time_offset` row (`:120`). Returns `False` (skips) when there are no human cues or the grids are too sparse to vote — the cues stay `time_base='rendition'` with no offset and are flagged `offset_missing` by the views until an offset lands. Called at `:355`; the new `offsets_reconciled` stat is initialised at `:194` and incremented at `:358`.

## 4. DB client — `tools/taghag_import/db_client.py`

- **`upsert_rendition_time_offsets(offsets)`** (`:159`) — PostgREST upsert into `rendition_time_offset` with `on_conflict="audio_file_id,measured_against_file_id,source_system"` (matches the table's unique key).

## 5. Backfill script — `tools/scripts/backfill_rendition_offsets.py`

Corrects history for existing pairs (new imports are reconciled inline). For every `audio_file` carrying both `human` and `mixonset` cues, votes the grids, upserts the offset, and stamps the mixonset cues/segments. Supports `--dry-run` (compute, don't write). Idempotent — re-running recomputes and upserts. Operational detail in `docs/runbooks/2026-06-21-rendition-offset-backfill.md`.

## 6. Tests — `tools/tests/test_time_base.py`

10 tests. The real-data fixtures (`HUMAN_3E08` / `MIX_3E08` and two more) are cue grids captured verbatim from the live DB (track `3e08a729`), not synthetic, and prove the documented ~17 ms with the right sign. Algorithm guards cover vote-rejects-noise, dedupe, declared-priming, and the key invariant `test_same_file_but_unvotable_grids_returns_none_not_identity` (`:119`): a lagged analyzer on the same FLAC whose grid can't vote returns `None`, never a fabricated identity.
