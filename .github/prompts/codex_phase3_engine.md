# Codex task — Phase 3: Engine Migration (Magikbox Rehoming)

## Objective
Port the `tagslut/tagslut/metadata/sonic_discovery.py` intelligence engine (and its related CLI tools) into the clean-room `taghag` environment under `taghag/tools/magikbox/`. 
The legacy system relied on a local `index.sqlite` and in-memory caches. The new architecture is fully integrated into the `taghag` Supabase Postgres schema.

## Files to create
Create the following files inside `taghag/tools/magikbox/`. Make sure `__init__.py` exists so it acts as a package.

### 1. `sonic_discovery.py` (The Engine)
Port `SonicDiscoveryIndex`. 
- **Read**: Fetch source data by joining `public.track_analysis` (for `happy`, `aggressive`, `relaxed`, `party`, `danceability`, and `raw_json` containing segments) and `public.dj_tag` (for `bpm` and `energy`).
- **Compute**: Keep the exact same `producer_vibes_for` logic and `sonic_vector_for` normalization (7-D vector: `[energy_norm, bpm_norm, danceability, party, happy, aggressive, relaxed]`). Note: `dj_tag.energy` is text, so cast/parse it safely to float.
- **Write**: Introduce a `recompute_all()` method that UPSERTs the results directly into `public.track_embedding`.
  - Conflict target: `(owner_user_id, audio_file_id, vector_schema)`
  - Provide `vector_schema = 'sonic7_v1'`.
  - Calculate `dynamic_evolution` and `evolution_delta` from the segments inside `track_analysis.raw_json` (if present) just like the old script did.

### 2. `crates.py`
Port the old `generate_neighborhood_crate.py`.
- **Query**: Use Postgres to find nearest neighbors! Instead of pulling all vectors into memory to calculate distance, execute a cosine similarity query directly against `public.track_embedding` leveraging the `hnsw` index (`ORDER BY embedding <=> %s LIMIT %s`).
- **Output**: Generate M3U8 playlists (just like before) by joining back to `public.audio_file` to get the physical `path`.

### 3. `map.py`
Port the old `generate_library_map.py` (if it existed, or skip if purely theoretical—at minimum, stub the CLI).
- If computing t-SNE or PCA, read the vectors directly from `public.track_embedding` via Postgres.

### 4. `human_correction.py`
Port the old `apply_human_correction.py` and `audit_qualitative_conflicts.py`.
- **Write**: Instead of mutating the in-memory index or `index.sqlite`, this must now UPSERT into `public.track_curation`.
- Conflict target: `(owner_user_id, audio_file_id)`
- Fields: `pinned = true`, `human_vibes_json`.

### 5. `sync_vibes.py`
Port the old `sync_vibes_to_id3.py` (or similar ID3 tag writer).
- **Read**: Fetch the final resolved vibes from Postgres. Give precedence to `track_curation.human_vibes_json` (if `pinned` is true) over `track_embedding.producer_vibes_json`.
- **Write**: Use Mutagen to write the resolved vibes to the physical MP3 files at `audio_file.path`.

## Hard requirements
1. **The Owner Injection**: Just like Phase 2, pull `owner_user_id` from `DatabaseConfig` and inject it unconditionally on all reads and writes.
2. **Database Config**: Use `tools/taghag_import/config.py` and `psycopg2` for all database interactions.
3. **Delete Legacy Files**: Once you have fully ported the logic, safely `git rm` the old files from the `tagslut/` repository (as specified in `implementation_plan.md` "The Extraction"). We do not want orphaned logic remaining in the archive.

## What NOT to do
- Do not bring over SQLite references (`index.sqlite`).
- Do not compute cosine similarity in Python for crates—offload that to Postgres `pgvector`.
- Do not alter the underlying `audio_file` or `dj_tag` schemas.
- Do not commit the code. Georges applies and verifies.

## Post-run checklist
- `sonic_discovery.py` reads `track_analysis` and writes to `track_embedding`
- Cosine distance for crates is executed via Postgres (`<=>`)
- `owner_user_id` is supplied to all DB queries
- Legacy Magikbox files deleted from `tagslut`
