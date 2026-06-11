# Codex task — Phase 2: DJ Slice Backfill Extractor

## Objective
Write the `extract_dj_slice.py` script. This script acts as a one-way bridge to extract the core musical metadata ("DJ slice") from the legacy `tagslut` SQLite database (`music_v3.db`) and inject it into the clean-room `taghag` Supabase database. 

## File to create
`taghag/tools/taghag_import/extract_dj_slice.py`
Use `psycopg2` for Supabase connectivity (using `tools/taghag_import/config.py` for credentials) and the built-in `sqlite3` for reading `music_v3.db` in read-only mode (`file:...?mode=ro`).

## Hard requirements

### 1. The Owner Injection
The new schema requires an `owner_user_id` across all rows.
Read this from `DatabaseConfig` (already defined in `tools/taghag_import/config.py`) and pass it unconditionally to every `INSERT` or `UPSERT`. Do not attempt to read identity or ownership from the legacy database.

### 2. Deduplication Strategy (CRITICAL)
- **Primary dedup key:** `ISRC` and/or `chromaprint` (where available).
- **NEVER use `title` or `artist` + `title`** to merge tracks. The old system aggregated too aggressively, combining distinct remixes into single identities. We are breaking that assumption.
- Use `file_key` (derived from canonical path or checksum) as the deterministic conflict target when upserting `audio_file`.

### 3. Target Schema mappings
Execute a clean, transactional Postgres migration of two tables only.

**Table 1: `public.audio_file`**
- Conflict target: `(owner_user_id, file_key)`
- Map legacy `track_identity` / file stat data into: `file_key`, `path`, `filename`, `size_bytes`, `duration_s`, `bitrate_kbps`, `codec` (hardcoded to `'mp3'`).

**Table 2: `public.dj_tag`**
- Conflict target: `(owner_user_id, audio_file_id)`
- Map legacy metadata into: `artist`, `title`, `album`, `label`, `catalog_number`, `release_date`, `year`, `bpm`, `musical_key`, `isrc`.
- Map legacy genres into `canonical_genre` and `canonical_subgenre`.
- Preserve curation metadata: `rating`, `energy`, `role`, `notes`, `manual_override`.

### 4. Execution Flow
1. Open the Supabase connection (`psycopg2`) and the SQLite connection (`sqlite3` read-only).
2. Fetch the target slice from `music_v3.db`.
3. Group and deduplicate the source records strictly by ISRC/chromaprint.
4. Begin a Postgres transaction.
5. Batch `UPSERT` into `audio_file` and return the new `id`s.
6. Batch `UPSERT` the corresponding metadata into `dj_tag` using those returned `id`s.
7. Commit, and log the counts (read vs. inserted vs. skipped).

## What NOT to do
- Do not extract or write `tag_evidence` (provider lookups). That is deferred.
- Do not extract or write `crate` and `crate_track` data (playlists/cues). That is Phase 4.
- Do not move or rename any physical MP3 files.
- Do not modify `music_v3.db`.

## Post-run checklist (print after writing)
- script filename + location
- confirm `sqlite3` connects in `mode=ro`
- confirm `owner_user_id` injection is present on all writes
- confirm deduplication uses ISRC/chromaprint and ignores titles
- confirm `tag_evidence` is strictly omitted
