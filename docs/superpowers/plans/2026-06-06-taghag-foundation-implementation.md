# Taghag Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Taghag into alignment with the clean-room MP3-only implementation prompts, centered on the Supabase `mp3_file` schema and receipt-first import flow.

**Architecture:** Taghag remains independent from Tagslut code. Tagslut is used only as context for extracted behavior: genre normalization, Postman `[Tag Evidence JSON]` shape, provider authority lessons, and legacy failure modes to avoid. The implementation order follows `.github/prompts/taghag-01` through `taghag-10`: schema/layout before importer, importer before web, audit before done.

**Tech Stack:** Supabase/Postgres SQL migrations, Python 3.11+ importer with `mutagen`, `ffprobe`/`ffmpeg` subprocess probing, PostgREST upload via service-role env vars, React/Vite TypeScript web app with `@supabase/supabase-js`.

---

## Current Ground Truth

- `/Users/g/Projects/taghag` is on `main` and was clean before this plan was created.
- `pytest tools/tests -q` passes: `5 passed`.
- `cd web && npm run build` passes.
- `supabase --version` is available: `2.102.0`.
- Current migration is wrong for the canonical plan: it creates `mp3_track`, treats `dj_tag` as a tag dictionary, lacks `mp3_observation`, and grants broad authenticated CRUD.
- Current importer is wrong for the canonical plan: it has `scan`/`load`, emits `mp3_track` receipt records, uses `library_fingerprint`, and uploads only `import_run` plus `mp3_track`.
- Current web shell is placeholder data only and does not use generated Supabase types or a typed client.
- `/Users/g/Projects/tagslut` is dirty on `dev`; do not edit it for this plan.

## Task 1: Normalize Repository Layout

**Files:**
- Move: `database/` -> `supabase/`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/TAGHAG_HANDOVER.md`
- Modify: `docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md`
- Modify: `.env.example`

- [ ] **Step 1: Confirm clean Taghag worktree**

Run:

```bash
cd /Users/g/Projects/taghag
git status --short
```

Expected: no unrelated dirty files. If files are dirty, inspect them and do not overwrite user work.

- [ ] **Step 2: Move the Supabase layout**

Run:

```bash
cd /Users/g/Projects/taghag
mv database supabase
```

Expected: `supabase/config.toml`, `supabase/seed.sql`, and `supabase/migrations/0001_initial_schema.sql` exist.

- [ ] **Step 3: Update docs and command references**

Replace active `database/` references with `supabase/` in repository guidance and setup docs. Keep historical/forbidden references only where explicitly marked as historical context.

Run:

```bash
cd /Users/g/Projects/taghag
rg "database/|database/migrations|mp3_track" README.md AGENTS.md docs .github/prompts tools web .env.example
```

Expected after edits:
- README source-controlled migrations point to `supabase/migrations`.
- `AGENTS.md` says SQL changes belong in source-controlled Supabase migrations.
- Prompt docs may still mention `mp3_track` only as "wrong/forbidden" context.

- [ ] **Step 4: Verify and commit layout checkpoint**

Run:

```bash
cd /Users/g/Projects/taghag
git status --short
git add README.md AGENTS.md docs .env.example supabase
git add -u database
git commit -m "chore: normalize Supabase project layout"
```

Expected: one focused commit containing only layout/doc reference changes.

## Task 2: Replace First Migration With Canonical MP3 Metadata Schema

**Files:**
- Replace or rename: `supabase/migrations/0001_initial_schema.sql`
- Create final migration path: `supabase/migrations/20260606000000_initial_mp3_metadata_schema.sql`

- [ ] **Step 1: Create the migration file**

Run:

```bash
cd /Users/g/Projects/taghag
mv supabase/migrations/0001_initial_schema.sql supabase/migrations/20260606000000_initial_mp3_metadata_schema.sql
```

Expected: the old `0001_initial_schema.sql` path is gone and the timestamped canonical migration path exists.

- [ ] **Step 2: Implement the 9-table schema exactly**

The migration must create only these public app tables:

```text
import_run
mp3_file
mp3_observation
dj_tag
tag_evidence
quality_check
crate
crate_track
saved_view
```

Hard requirements:
- `mp3_file` is the primary asset table.
- No `mp3_track`, `asset_file`, `track_identity`, `asset_link`, `preferred_asset`, storage bucket, upload path, or audio object columns.
- UUID primary keys with `gen_random_uuid()`.
- `owner_user_id uuid not null references auth.users(id) on delete cascade` on every table.
- Composite ownership foreign keys wherever child rows reference parent rows, for example `(mp3_file_id, owner_user_id)` -> `mp3_file(id, owner_user_id)`.
- `isrc` may exist on `dj_tag` and be indexed, but is never unique and never a row identity.
- `created_at` and `updated_at` on all 9 tables.
- `public.set_updated_at()` trigger attached to all 9 tables.
- Explicit `revoke` from `anon` and `public`.
- Explicit grants: authenticated can read import/file/observation/evidence/quality tables; authenticated can write `dj_tag`, `crate`, `crate_track`, `saved_view`; `service_role` can CRUD all 9 app tables.
- RLS enabled on all 9 app tables.
- No policies to `anon`.
- Authenticated policies use `(select auth.uid())`.

- [ ] **Step 3: Validate migration**

For the local Supabase CLI stack, Docker is expected. Run:

```bash
cd /Users/g/Projects/taghag
supabase db reset
```

To avoid Docker during early development, use a free hosted Supabase dev project instead and apply the files in `supabase/migrations/` there. Hosted Supabase is not assumed to be paid; Taghag is metadata-only, so the free tier should be enough initially.

Then run the verification SQL from `.github/prompts/taghag-02-first-migration.prompt.md` against the local or hosted database to confirm table names, RLS, policies, and grants.

Run grep checks:

```bash
cd /Users/g/Projects/taghag
! rg "mp3_track|asset_file|track_identity|asset_link|preferred_asset" supabase/migrations
! rg "storage|bucket|upload_path|storage_path|object_path|object_id|bucket_id" supabase/migrations
! rg "to anon" supabase/migrations
! rg "unique.*isrc|isrc.*unique" supabase/migrations
```

Expected: all negative checks pass.

- [ ] **Step 4: Commit schema checkpoint**

Run:

```bash
cd /Users/g/Projects/taghag
git add supabase/migrations supabase/config.toml supabase/seed.sql
git commit -m "feat: add canonical MP3 metadata schema"
```

Expected: one focused schema commit.

## Task 3: Add Schema Guard Tests

**Files:**
- Create: `tools/tests/test_schema_contract.py`
- Create: `tools/taghag_import/schema_contract.py`

- [ ] **Step 1: Write tests that parse the migration text**

Test cases:
- Exactly the 9 canonical `create table public.<name>` app tables are present.
- `mp3_file` exists and `mp3_track` does not.
- Forbidden Tagslut schema terms are absent from migrations.
- No storage/upload path terms are present.
- No `to anon` policy exists.
- No unique ISRC constraint exists.
- Every app table has an `alter table public.<table> enable row level security`.
- Every app table has a `set_<table>_updated_at` trigger.

- [ ] **Step 2: Run the schema tests**

Run:

```bash
cd /Users/g/Projects/taghag
pytest tools/tests/test_schema_contract.py -q
```

Expected: pass.

- [ ] **Step 3: Commit schema tests**

Run:

```bash
cd /Users/g/Projects/taghag
git add tools/tests/test_schema_contract.py tools/taghag_import/schema_contract.py
git commit -m "test: guard Taghag schema contract"
```

Expected: one focused test commit.

## Task 4: Implement Receipt-First Import Batch Command

**Files:**
- Modify: `tools/taghag_import/cli.py`
- Modify: `tools/taghag_import/config.py`
- Modify: `tools/taghag_import/discover.py`
- Modify: `tools/taghag_import/tags.py`
- Modify: `tools/taghag_import/audio_probe.py`
- Modify: `tools/taghag_import/genre.py`
- Modify: `tools/taghag_import/receipt.py`
- Create or modify: `tools/tests/test_import_cli.py`
- Create or modify: `tools/tests/test_discover.py`
- Create or modify: `tools/tests/test_receipt.py`

- [ ] **Step 1: Add failing CLI contract tests**

Test `python -m taghag_import.cli import-batch` behavior through `cli.main()` or parser invocation:
- Requires `--root`.
- Accepts `--run-name`, `--dry-run`, `--no-upload`, `--receipt-dir`, `--postman-evidence`, `--unsafe-title-artist-evidence-match`, and `--verbose`.
- Always writes `artifacts/import_runs/<run_id>/receipt.jsonl` before upload.
- `--dry-run` and `--no-upload` never call the database client.
- Receipt contains `import_run_start`, `mp3_observed`, `quality_check`, `import_run_summary`, and `upload_result` when upload is attempted.

- [ ] **Step 2: Add discovery tests**

Test:
- `.mp3` and `.MP3` are discovered.
- `.m4a`, `.aac`, `.flac`, `.wav`, `.aiff`, `.aif`, `.alac`, `.ogg`, `.opus`, `.wma` are recorded as `out_of_scope_audio`.
- `.DS_Store`, `._*`, `__MACOSX`, `.Trashes`, `.Spotlight-V100`, and `.fseventsd` are ignored.
- Discovery never deletes or moves files.

- [ ] **Step 3: Add receipt tests**

Test:
- Receipt JSONL has stable sorted keys and one JSON object per line.
- Receipt has no secret-looking values from `TAGHAG_SUPABASE_SERVICE_ROLE_KEY`.
- Receipt includes enough upload data for `import_run`, `mp3_file`, `mp3_observation`, `dj_tag`, and `quality_check`.
- Full checksum file keys are shaped as `sha256:<hex>`.
- Stat fallback keys are shaped as `stat:<size>:<mtime_ns>:<path_hash>`.

- [ ] **Step 4: Implement discovery, tag extraction, probing, and issue generation**

Required behavior:
- `discover_audio_files()` returns MP3 observations plus out-of-scope audio events.
- `extract_mp3_tags()` extracts artist, title, album, label, catalog number, release date/year, BPM, musical key, genre/subgenre, ISRC, compilation, rating, energy, and raw ID3.
- MP3 comments are never used for Taghag notes; they may only inform energy if the logic is explicit.
- `probe_mp3()` handles missing `ffprobe` or `ffmpeg` with issue codes instead of crashing.
- Missing metadata creates quality issue codes from `.github/prompts/taghag-03-import-cli.prompt.md`, not failed imports.
- Full SHA-256 checksum is preferred for `file_key`; stat fallback is explicit and lower confidence.

- [ ] **Step 5: Implement `import-batch` receipt-first flow**

Required event types:

```text
import_run_start
mp3_observed
out_of_scope_audio
quality_check
tag_evidence
import_run_summary
upload_result
```

Required row intent:
- `import_run`: one row per command run.
- `mp3_file`: idempotent by `(owner_user_id, file_key)`.
- `mp3_observation`: one row per file occurrence per run.
- `dj_tag`: one row per MP3 file, idempotent by `(owner_user_id, mp3_file_id)` after upload resolves the file id.
- `quality_check`: one row per run/file check.

- [ ] **Step 6: Run importer tests and commit**

Run:

```bash
cd /Users/g/Projects/taghag
pytest tools/tests/test_import_cli.py tools/tests/test_discover.py tools/tests/test_receipt.py tools/tests/test_genre.py -q
```

Expected: pass.

Commit:

```bash
git add tools/taghag_import tools/tests
git commit -m "feat: add receipt-first MP3 import batch"
```

## Task 5: Implement Supabase Upload Against Canonical Tables

**Files:**
- Modify: `tools/taghag_import/db_client.py`
- Modify: `tools/taghag_import/config.py`
- Modify: `tools/taghag_import/receipt.py`
- Create or modify: `tools/tests/test_db_client.py`

- [ ] **Step 1: Update importer env contract**

Use these env vars:

```text
TAGHAG_SUPABASE_URL
TAGHAG_SUPABASE_SERVICE_ROLE_KEY
TAGHAG_SUPABASE_SECRET_KEY
TAGHAG_OWNER_USER_ID
```

Rules:
- Accept either `TAGHAG_SUPABASE_SERVICE_ROLE_KEY` or `TAGHAG_SUPABASE_SECRET_KEY`.
- Require `TAGHAG_OWNER_USER_ID` for upload.
- Do not read `VITE_` vars in Python tools.
- Never write service-role values to receipts.

- [ ] **Step 2: Add upload tests with mocked PostgREST**

Test:
- `import_run` upsert uses conflict `id`.
- `mp3_file` upsert uses conflict `owner_user_id,file_key`.
- `mp3_observation` inserts every occurrence.
- `dj_tag` upsert waits until `mp3_file.id` is known and uses `owner_user_id,mp3_file_id`.
- `quality_check` and `tag_evidence` insert as event rows.
- Upload failure preserves existing receipt and records/prints a clear failure.

- [ ] **Step 3: Implement upload**

Implementation requirements:
- Use service role only in local tooling.
- Use PostgREST headers already established in `TaghagDbClient`.
- Request returned rows where needed to map `file_key` to `mp3_file.id`.
- Do not dedupe `mp3_observation` across runs.
- Do not merge files by ISRC.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
cd /Users/g/Projects/taghag
pytest tools/tests/test_db_client.py tools/tests/test_import_cli.py tools/tests/test_receipt.py -q
```

Expected: pass.

Commit:

```bash
git add tools/taghag_import tools/tests
git commit -m "feat: upload imports to canonical Supabase tables"
```

## Task 6: Wire Postman Evidence Without Tagslut Coupling

**Files:**
- Modify: `tools/taghag_import/postman_evidence.py`
- Modify: `tools/taghag_import/cli.py`
- Modify: `tools/taghag_import/receipt.py`
- Create or modify: `tools/tests/test_postman_evidence.py`
- Create or modify: `tools/tests/test_import_cli.py`

- [ ] **Step 1: Add evidence parser tests**

Test:
- Matched evidence is parsed from `[Tag Evidence JSON]`.
- `no_match`, `ambiguous`, `error`, and malformed JSON produce receipt events and never crash import.
- Duplicate evidence lines are preserved or explicitly marked `duplicate`.
- Raw evidence payload is preserved.
- Evidence import never blocks MP3 import.

- [ ] **Step 2: Add evidence matching tests**

Test:
- Match evidence to MP3 by ISRC first.
- If MP3 has no ISRC and unsafe flag is absent, do not match by title/artist.
- If `--unsafe-title-artist-evidence-match` is present, emit `lookup_type = "unsafe_title_artist"` and do not merge fields automatically.
- Ambiguous/no-match/error evidence does not update `dj_tag`.
- Beatport can supply label and genre/subgenre only when confidence is clear.

- [ ] **Step 3: Implement evidence receipt and upload mapping**

Map evidence to `tag_evidence` columns:
- `provider`
- `lookup_type`
- `lookup_key`
- `provider_track_id`
- `status`
- `confidence`
- `winning_fields_json`
- `candidates_json`
- `raw_marker_json`
- `fetched_at`

- [ ] **Step 4: Run tests and commit**

Run:

```bash
cd /Users/g/Projects/taghag
pytest tools/tests/test_postman_evidence.py tools/tests/test_import_cli.py tools/tests/test_db_client.py -q
```

Expected: pass.

Commit:

```bash
git add tools/taghag_import tools/tests
git commit -m "feat: store Postman tag evidence"
```

## Task 7: Generate Web Types And Typed Supabase Client

**Files:**
- Create: `web/src/lib/database.types.ts`
- Create: `web/src/lib/supabase.ts`
- Modify: `web/package.json`
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Add dependencies and scripts**

Run:

```bash
cd /Users/g/Projects/taghag/web
npm install @supabase/supabase-js
```

Add script:

```json
"db:types": "supabase gen types typescript --local > src/lib/database.types.ts"
```

- [ ] **Step 2: Generate database types**

Run:

```bash
cd /Users/g/Projects/taghag
cd web && npm run db:types
```

Expected: `web/src/lib/database.types.ts` reflects the canonical 9-table schema.

- [ ] **Step 3: Add typed client**

`web/src/lib/supabase.ts` must:
- Import `createClient` from `@supabase/supabase-js`.
- Import `Database` from `./database.types`.
- Read only `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`.
- Throw a clear error if either is missing.
- Never reference service-role or secret keys.

- [ ] **Step 4: Update env/docs and commit**

`.env.example` must include:

```text
VITE_SUPABASE_URL=
VITE_SUPABASE_PUBLISHABLE_KEY=
TAGHAG_SUPABASE_URL=
TAGHAG_SUPABASE_SERVICE_ROLE_KEY=
TAGHAG_OWNER_USER_ID=
```

Run:

```bash
cd /Users/g/Projects/taghag/web
npm run build
```

Commit:

```bash
cd /Users/g/Projects/taghag
git add .env.example README.md web/package.json web/package-lock.json web/src/lib
git commit -m "feat: add typed Supabase web client"
```

## Task 8: Build Data-First React/Vite Shell

**Files:**
- Modify: `web/src/App.tsx`
- Create: `web/src/lib/queries.ts`
- Create: `web/src/components/AppShell.tsx`
- Create: `web/src/components/LibraryTable.tsx`
- Create: `web/src/components/DashboardCards.tsx`
- Create: `web/src/routes/ImportRuns.tsx`
- Create: `web/src/routes/Library.tsx`
- Create: `web/src/routes/TrackDetail.tsx`
- Create: `web/src/routes/Crates.tsx`
- Create: `web/src/routes/Dashboard.tsx`

- [ ] **Step 1: Add query module**

Typed query functions:
- `listImportRuns()`
- `listLibraryTracks(filters)`
- `getTrackDetail(id)`
- `listCrates()`
- `getDashboardCounts()`

Rules:
- Query canonical tables only.
- Use generated `Database` types.
- No service-role references.
- Empty states are truthful; no fake track data.

- [ ] **Step 2: Replace placeholder UI with app shell**

Routes:
- `/` redirects or renders dashboard.
- `/dashboard`
- `/imports`
- `/library`
- `/tracks/:id`
- `/crates`

Library columns:
- `filename` from `mp3_file`.
- `artist`, `title`, `label`, `bpm`, `musical_key`, `canonical_genre`, `canonical_subgenre` from `dj_tag`.
- Latest quality status from `quality_check`.
- Evidence status aggregate from `tag_evidence`.

- [ ] **Step 3: Add URL-backed filters**

Implement filters for:
- `import_run`
- genre
- BPM range
- key
- quality status
- provider status

Use `URLSearchParams`; do not add global state for v1.

- [ ] **Step 4: Run build and commit**

Run:

```bash
cd /Users/g/Projects/taghag/web
npm run build
```

Expected: TypeScript and Vite build pass.

Commit:

```bash
cd /Users/g/Projects/taghag
git add web/src web/package.json web/package-lock.json
git commit -m "feat: build private Taghag app shell"
```

## Task 9: Add Clean-Room Audit

**Files:**
- Create: `tools/audit_cleanroom.py`
- Create: `tools/tests/test_cleanroom_audit.py`
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Add audit tests**

Test:
- Clean active code passes.
- `from tagslut` in Python fails.
- `import tagslut` in Python fails.
- Forbidden schema names in SQL fail.
- Docs may contain forbidden terms only inside `cleanroom-audit: allow-start` and `cleanroom-audit: allow-end`.
- Migrations and active code never get allow-block exceptions.

- [ ] **Step 2: Implement audit script**

Forbidden active-code terms:

```text
from tagslut
import tagslut
asset_file
track_identity
asset_link
preferred_asset
move_plan
move_execution
provenance_event
AAC_LIBRARY
M4A derivative
AAC-first
```

Scan active code, SQL, config, and tests. Ignore generated directories such as `web/dist`, `node_modules`, `tools/.pytest_cache`, and `__pycache__`.

- [ ] **Step 3: Run audit and tests**

Run:

```bash
cd /Users/g/Projects/taghag
python tools/audit_cleanroom.py
pytest tools/tests/test_cleanroom_audit.py -q
```

Expected: pass.

- [ ] **Step 4: Commit audit checkpoint**

Run:

```bash
cd /Users/g/Projects/taghag
git add tools/audit_cleanroom.py tools/tests/test_cleanroom_audit.py README.md AGENTS.md
git commit -m "test: add clean-room audit"
```

## Task 10: Final Verification And Push

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/TAGHAG_HANDOVER.md`

- [ ] **Step 1: Run full verification**

Run:

```bash
cd /Users/g/Projects/taghag
git status --short
python tools/audit_cleanroom.py
pytest tools/tests -q
supabase db reset
cd web && npm run build
```

Expected:
- Clean-room audit passes.
- Python tests pass.
- Supabase reset applies the canonical migration when using local CLI with Docker, or the same migration applies to a free hosted Supabase dev project when avoiding Docker.
- Web build passes.

- [ ] **Step 2: Run final grep checks**

Run:

```bash
cd /Users/g/Projects/taghag
! rg "from tagslut|import tagslut" tools web supabase
! rg "mp3_track|asset_file|track_identity|asset_link|preferred_asset|move_plan|move_execution|provenance_event|AAC_LIBRARY|M4A derivative|AAC-first" tools web supabase
! rg "service_role|secret" web/src
! rg "unique.*isrc|isrc.*unique" supabase/migrations
```

Expected: all negative checks pass.

- [ ] **Step 3: Commit final doc sync**

Update the active docs with the implemented commands, migration path, env names, and verification results, then run:

```bash
cd /Users/g/Projects/taghag
git add README.md AGENTS.md docs .env.example
git commit -m "docs: sync Taghag implementation guide"
```

- [ ] **Step 4: Push all implementation commits**

Run:

```bash
cd /Users/g/Projects/taghag
git status --short
git push origin main
```

Expected: no uncommitted files remain and `main` is pushed.

## Acceptance Criteria

- Local verification with `supabase db reset` applies cleanly, or hosted dev verification applies the same migrations to a free Supabase project when avoiding Docker.
- Public app schema contains exactly the 9 canonical tables.
- `mp3_file` exists and `mp3_track` does not.
- RLS is enabled on every public app table.
- No anon policies exist.
- Grants are explicit and service-role usage is local/server-only.
- ISRC is indexed evidence, not unique identity.
- No storage/upload/audio object schema concepts exist.
- `import-batch` writes a local receipt before upload.
- Repeated import is idempotent for `mp3_file` and `dj_tag`.
- Every run creates fresh `mp3_observation` rows.
- Missing metadata creates quality issues, not failed imports.
- Postman evidence stores matched/no-match/ambiguous/error/malformed states and never blocks MP3 import.
- Web uses generated `Database` types and a publishable-key Supabase client only.
- Clean-room audit passes.
- Python tests and web build pass.
- Changes are committed and pushed.
