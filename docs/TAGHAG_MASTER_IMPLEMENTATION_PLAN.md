# Taghag Master Implementation Plan

> Agent handoff reference for continuing Taghag implementation from a clean-room,
> MP3-only foundation. This file is intentionally detailed so an agent can resume
> without needing the original conversation.

## 1. Purpose

Taghag is a private DJ metadata app for local MP3 libraries.

The database stores metadata, import receipts, quality checks, provider
evidence, DJ-facing tags, crates, and saved views. It does not store audio.
Local MP3 files remain local.

This plan is rooted in the tagslut lessons without inheriting tagslut's old
architecture. The right inheritance is operational knowledge and small
standalone utilities. The wrong inheritance is tagslut v3 schema, identity
model, mixed-format assumptions, database coupling, or file-moving machinery.

There is another Codex on the tagslut side saying hi. This is a two-way street:
if implementation intent is unclear, ask the operator to pass the question back
to the tagslut-side Codex. It can clarify extracted utility behavior, old
failure modes, provider evidence contracts, and why certain legacy concepts are
forbidden.

## 2. Canonical Repo And Naming

- Repo: `/Users/g/Projects/taghag`
- Product name: `Taghag`
- If the operator writes `taghad`, assume they mean `Taghag` unless a new repo
  is explicitly created.

## 3. Core Product Invariants

- MP3-only v1.
- Local files remain local.
- The app stores metadata only, not audio assets.
- `mp3_file` is the primary asset table.
- ISRC is evidence, not identity.
- ISRC must not automatically merge rows in v1.
- Missing metadata creates quality issues, not failed imports.
- Uncertain provider evidence is stored and reported, not guessed into canonical
  tags.
- Service-role or secret keys are local/server-only and never go to frontend
  code.
- The web app uses a publishable key plus authenticated browser access.
- SQL changes are source-controlled migrations.
- Every public table has RLS enabled.
- No anon access in v1.

## 4. Clean-Room Boundary

Allowed inheritance from tagslut:

- Extracted genre normalization behavior.
- Extracted Postman `[Tag Evidence JSON]` parser behavior.
- The DJ-facing metadata contract: label, canonical genre, canonical subgenre,
  release context, evidence status, and quality status.
- The operational guardrail that uncertain metadata should skip/report rather
  than silently guess.
- The rule that MP3 comments are reserved for Mixed in Key Energy, not Taghag
  receipts or debug notes.

Forbidden inheritance:

- No imports from `tagslut`.
- No tagslut v3 schema.
- No legacy asset identity tables.
- No AAC-first workflow.
- No M4A/AAC/FLAC intake in v1.
- No Rekordbox XML machinery.
- No Turso/libSQL assumptions.
- No dependency on local tagslut databases.
- No file deletion, trashing, moving, or cloud uploading.

Forbidden active-code or migration terms:

- `from tagslut`
- `import tagslut`
- `asset_file`
- `track_identity`
- `asset_link`
- `preferred_asset`
- `move_plan`
- `move_execution`
- `provenance_event`
- `AAC_LIBRARY`
- `M4A derivative`
- `AAC-first`

These terms may appear only in documentation sections explicitly marked
historical or forbidden.

## 5. Known Current Repo State To Check

Before making changes, run:

```bash
cd /Users/g/Projects/taghag
git status --short
find . -maxdepth 2 -type d | sort
```

Known existing work from previous agents:

- Extracted utilities should exist under `tools/taghag_import/`.
- Genre rules should exist as `tools/taghag_import/genre_rules.json`.
- Postman evidence parser should exist as
  `tools/taghag_import/postman_evidence.py`.
- Tests should exist under `tools/tests/`.
- A first migration may exist under
  `supabase/migrations/20260606000000_initial_mp3_metadata_schema.sql`.

Known migration problem to watch for:

- If the migration creates `mp3_track`, it is wrong. Replace with `mp3_file`.
- If `dj_tag` is a tag dictionary/taxonomy table, it is wrong. Replace with
  per-file DJ metadata.
- If `mp3_observation` is missing, the schema is incomplete.
- If authenticated gets broad full CRUD on every table without scoped policies,
  tighten grants and policies.
- The layout should use the operator-requested `supabase/` directory.

## 6. Implementation Order

Implement in phases. Commit after each phase that reaches a working checkpoint.
Do not include unrelated dirty files.

1. Normalize repo layout and documentation paths.
2. Replace or create the first Supabase migration.
3. Add schema validation checks/tests.
4. Implement local import receipt generation.
5. Implement Supabase upload/upsert from receipts.
6. Wire optional Postman evidence logs.
7. Generate web database types and typed Supabase client.
8. Build first React/Vite UI shell.
9. Add minimum test suite.
10. Add clean-room audit.
11. Run final verification.
12. Commit and push.

## 7. Phase 1: Normalize Repo Layout

Goal: make future tooling and agent handoffs predictable.

Preferred structure:

```text
taghag/
  README.md
  AGENT.md
  TAGHAG_MASTER_IMPLEMENTATION_PLAN.md
  .env.example
  tools/
    pyproject.toml
    taghag_import/
    tests/
  supabase/
    config.toml
    seed.sql
    migrations/
  web/
    package.json
    src/
```

Tasks:

1. Inspect current layout.
2. Confirm `supabase/` exists and contains `config.toml`, `seed.sql`, and
   `migrations/`.
3. Update README references to `supabase/`.
4. Keep `supabase/seed.sql` empty or harmless.
5. Do not insert fake user-owned production rows in default seed data.
6. If test seed data is needed, create test fixtures instead.

Verify:

```bash
rg "database/migrations" README.md AGENT.md TAGHAG_MASTER_IMPLEMENTATION_PLAN.md
rg "supabase/migrations" README.md AGENT.md TAGHAG_MASTER_IMPLEMENTATION_PLAN.md
git status --short
```

Acceptance:

- Migration folder path is clear and current.
- README and AGENT match the actual layout.
- No default seed data depends on fake auth users.

## 8. Phase 2: First Supabase Migration

Goal: create the MP3-only metadata database.

Required public app tables:

1. `import_run`
2. `mp3_file`
3. `mp3_observation`
4. `dj_tag`
5. `tag_evidence`
6. `quality_check`
7. `crate`
8. `crate_track`
9. `saved_view`

Rules:

- Use UUID primary keys.
- Add `owner_user_id` to every table.
- `owner_user_id` references `auth.users(id) on delete cascade`.
- Add `created_at` and `updated_at` where appropriate.
- Add `updated_at` triggers to all tables with `updated_at`.
- Enable RLS on every table.
- Add no anon policies.
- Revoke anon explicitly.
- Add explicit grants.
- Use `service_role` grants for local importer/upsert.
- Use `authenticated` grants only for private app behavior.
- Do not create storage buckets, upload paths, or audio object columns.
- Do not create `mp3_track`.
- Do not make `isrc` unique.

Migration file:

```text
supabase/migrations/<timestamp>_initial_mp3_metadata_schema.sql
```

Use Supabase CLI to create migration if available:

```bash
supabase migration new initial_mp3_metadata_schema
```

If the CLI is unavailable, create a correctly named migration manually and note
that CLI migration creation was unavailable.

### 8.1 Shared SQL Foundation

The migration should include:

```sql
begin;

create extension if not exists pgcrypto;

revoke all on schema public from anon;
revoke all on schema public from public;
grant usage on schema public to authenticated, service_role;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

revoke all on function public.set_updated_at() from public;
```

Attach triggers after table creation:

```sql
create trigger set_<table>_updated_at
before update on public.<table>
for each row execute function public.set_updated_at();
```

### 8.2 Table: import_run

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `run_name text`
- `source_root text`
- `status text not null default 'pending'`
- `started_at timestamptz not null default now()`
- `completed_at timestamptz`
- `tool_versions_json jsonb not null default '{}'::jsonb`
- `summary_json jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints:

- `status in ('pending', 'running', 'completed', 'failed', 'cancelled')`
- `unique (id, owner_user_id)`

Purpose:

- One local import attempt or dry-run.
- Stores summary and tool version metadata.
- Does not imply files were uploaded.

### 8.3 Table: mp3_file

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `file_key text not null`
- `path text not null`
- `filename text not null`
- `size_bytes bigint`
- `mtime_ns bigint`
- `duration_s numeric`
- `bitrate_kbps integer`
- `codec text not null default 'mp3'`
- `checksum_sha256 text`
- `checksum_prefix text`
- `identity_source text`
- `identity_confidence numeric`
- `first_seen_at timestamptz not null default now()`
- `last_seen_at timestamptz not null default now()`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints:

- `unique (owner_user_id, file_key)`
- `unique (id, owner_user_id)`
- `codec = 'mp3'`
- `identity_confidence is null or identity_confidence between 0 and 1`
- `size_bytes is null or size_bytes >= 0`
- `duration_s is null or duration_s >= 0`
- `bitrate_kbps is null or bitrate_kbps > 0`

Purpose:

- Primary asset table.
- Represents a local MP3 file identity.
- `file_key` comes from checksum when available.
- Never keyed by ISRC.

### 8.4 Table: mp3_observation

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `import_run_id uuid not null`
- `mp3_file_id uuid`
- `observed_path text not null`
- `observed_size_bytes bigint`
- `observed_mtime_ns bigint`
- `observed_checksum_sha256 text`
- `status text not null`
- `issue_json jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Foreign keys:

- `(import_run_id, owner_user_id)` references
  `public.import_run(id, owner_user_id) on delete cascade`
- `(mp3_file_id, owner_user_id)` references
  `public.mp3_file(id, owner_user_id) on delete set null`

Constraints:

- `status in ('observed', 'imported', 'skipped', 'out_of_scope', 'failed')`

Purpose:

- One row per file observation per import run.
- Re-importing the same folder creates new observations but not duplicate
  `mp3_file` rows.

### 8.5 Table: dj_tag

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `mp3_file_id uuid not null`
- `artist text`
- `title text`
- `album text`
- `label text`
- `catalog_number text`
- `release_date date`
- `year integer`
- `bpm numeric`
- `musical_key text`
- `canonical_genre text`
- `canonical_subgenre text`
- `isrc text`
- `compilation boolean`
- `rating integer`
- `energy text`
- `role text`
- `notes text`
- `tag_source text`
- `manual_override boolean not null default false`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Foreign keys:

- `(mp3_file_id, owner_user_id)` references
  `public.mp3_file(id, owner_user_id) on delete cascade`

Constraints:

- `unique (owner_user_id, mp3_file_id)`
- `rating is null or rating between 0 and 5`
- `bpm is null or bpm > 0`
- `year is null or year between 1900 and 2100`

Purpose:

- One DJ-facing metadata row per MP3.
- Stores normalized genre/subgenre.
- Stores label and release fields.
- ISRC is searchable evidence only, not identity.

### 8.6 Table: tag_evidence

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `mp3_file_id uuid not null`
- `provider text not null`
- `lookup_type text not null`
- `lookup_key text not null`
- `provider_track_id text`
- `status text not null`
- `confidence numeric`
- `winning_fields_json jsonb not null default '{}'::jsonb`
- `candidates_json jsonb not null default '[]'::jsonb`
- `raw_marker_json jsonb not null default '{}'::jsonb`
- `fetched_at timestamptz not null default now()`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Foreign keys:

- `(mp3_file_id, owner_user_id)` references
  `public.mp3_file(id, owner_user_id) on delete cascade`

Constraints:

- `status in ('matched', 'no_match', 'ambiguous', 'error', 'malformed', 'duplicate')`
- `confidence is null or confidence between 0 and 1`

Purpose:

- Stores provider evidence and raw Postman markers.
- Ambiguous and error evidence is visible, not discarded.
- Evidence never blocks MP3 import.

### 8.7 Table: quality_check

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `import_run_id uuid`
- `mp3_file_id uuid not null`
- `decode_ok boolean`
- `duration_ok boolean`
- `bitrate_ok boolean`
- `missing_tag_flags_json jsonb not null default '[]'::jsonb`
- `duplicate_flags_json jsonb not null default '[]'::jsonb`
- `issue_codes_json jsonb not null default '[]'::jsonb`
- `tool_name text`
- `tool_version text`
- `checked_at timestamptz not null default now()`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Foreign keys:

- `(import_run_id, owner_user_id)` references
  `public.import_run(id, owner_user_id) on delete set null`
- `(mp3_file_id, owner_user_id)` references
  `public.mp3_file(id, owner_user_id) on delete cascade`

Purpose:

- Stores import quality outcomes.
- Missing tags are issue codes, not import failures.

### 8.8 Table: crate

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `name text not null`
- `description text`
- `sort_order integer not null default 0`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints:

- `unique (owner_user_id, name)`
- `unique (id, owner_user_id)`

Purpose:

- User-owned DJ crates/playlists.

### 8.9 Table: crate_track

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `crate_id uuid not null`
- `mp3_file_id uuid not null`
- `position integer not null default 0`
- `notes text`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Foreign keys:

- `(crate_id, owner_user_id)` references
  `public.crate(id, owner_user_id) on delete cascade`
- `(mp3_file_id, owner_user_id)` references
  `public.mp3_file(id, owner_user_id) on delete cascade`

Constraints:

- `unique (crate_id, mp3_file_id)`
- Do not add `unique (crate_id, position)` in v1 unless reorder logic is
  collision-safe and transactional.

Purpose:

- Ordered crate membership.

### 8.10 Table: saved_view

Columns:

- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `name text not null`
- `route text not null`
- `filters_json jsonb not null default '{}'::jsonb`
- `sort_json jsonb not null default '{}'::jsonb`
- `chart_state_json jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints:

- `unique (owner_user_id, name)`

Purpose:

- Stores private saved filters, table states, and dashboard/chart states.

### 8.11 Required Indexes

Create indexes:

- `mp3_file(owner_user_id, file_key)`
- `mp3_file(owner_user_id, checksum_sha256)`
- `mp3_file(owner_user_id, checksum_prefix)`
- `mp3_file(owner_user_id, filename)`
- `mp3_observation(owner_user_id, import_run_id)`
- `mp3_observation(owner_user_id, mp3_file_id)`
- `dj_tag(owner_user_id, isrc)`
- `dj_tag(owner_user_id, canonical_genre, canonical_subgenre)`
- `dj_tag(owner_user_id, label)`
- `dj_tag(owner_user_id, artist, title)`
- `tag_evidence(owner_user_id, provider, lookup_type, lookup_key)`
- `tag_evidence(owner_user_id, mp3_file_id, fetched_at desc)`
- `quality_check(owner_user_id, mp3_file_id, checked_at desc)`
- `crate(owner_user_id, sort_order)`
- `crate_track(crate_id, position)`
- `saved_view(owner_user_id, route)`

### 8.12 Grants

Explicitly revoke anon:

```sql
revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;
```

Grant authenticated only what the private browser app needs:

- `import_run`: `select`
- `mp3_file`: `select`
- `mp3_observation`: `select`
- `tag_evidence`: `select`
- `quality_check`: `select`
- `dj_tag`: `select, insert, update`
- `crate`: `select, insert, update, delete`
- `crate_track`: `select, insert, update, delete`
- `saved_view`: `select, insert, update, delete`

Grant service role importer capability:

- `select, insert, update, delete` on all 9 app tables to `service_role`.

Add a SQL comment:

```sql
comment on schema public is
'Taghag public app schema. service_role grants are for local/server importer tooling only; frontend code must use publishable authenticated access.';
```

### 8.13 RLS Policies

Enable RLS on every public app table:

```sql
alter table public.<table> enable row level security;
```

Policy rules:

- No policies to `anon`.
- Use `to authenticated`.
- Use `(select auth.uid())`, not `auth.role()`.
- Select policy: `owner_user_id = (select auth.uid())`.
- Insert policy: `with check (owner_user_id = (select auth.uid()))`.
- Update policy: both `using` and `with check`.
- Delete policy: `using`.
- Match policies to grants. Do not create web write policies for read-only
  importer tables unless the app truly needs them.

For read-only web tables, create select policies only:

- `import_run`
- `mp3_file`
- `mp3_observation`
- `tag_evidence`
- `quality_check`

For user-editable metadata/organization tables, create write policies:

- `dj_tag`
- `crate`
- `crate_track`
- `saved_view`

## 9. Phase 3: Schema Verification

Run:

```bash
supabase db reset
```

If Supabase CLI is unavailable:

1. Say exactly that Supabase CLI was unavailable.
2. Run SQL syntax validation with an available Postgres-compatible method if
   possible.
3. Do not claim `supabase db reset` passed.

Validation SQL:

```sql
select tablename
from pg_tables
where schemaname = 'public'
order by tablename;

select c.relname, c.relrowsecurity
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
  and c.relkind = 'r'
order by c.relname;

select policyname, tablename, roles
from pg_policies
where schemaname = 'public'
order by tablename, policyname;

select policyname, tablename
from pg_policies
where schemaname = 'public'
  and 'anon' = any(roles);

select grantee, table_name, privilege_type
from information_schema.role_table_grants
where table_schema = 'public'
order by table_name, grantee, privilege_type;
```

Grep checks:

```bash
rg "mp3_track" supabase/migrations
rg "storage|bucket|upload_path|object_path|object_id" supabase/migrations
rg "to anon" supabase/migrations
rg "unique.*isrc|isrc.*unique" supabase/migrations
```

Acceptance:

- Reset applies cleanly.
- Exactly the 9 required public app tables exist.
- `mp3_file` exists.
- `mp3_track` does not exist.
- RLS is enabled on every app table.
- No anon policies exist.
- Grants are explicit.
- No storage/upload path concepts exist.
- ISRC is not unique.

## 10. Phase 4: Local MP3 Import CLI

Goal: implement local MP3-only batch import.

Command:

```bash
python -m taghag_import.cli import-batch --root /path/to/mp3-batch --run-name "batch-name"
```

Required flags:

- `--root /path/to/mp3-batch`
- `--run-name "batch-name"`
- `--dry-run`
- `--no-upload`
- `--receipt-dir artifacts/import_runs`
- `--postman-evidence /path/to/evidence.log`
- `--unsafe-title-artist-evidence-match` disabled by default
- `--verbose`

Files:

- `tools/taghag_import/cli.py`
- `tools/taghag_import/config.py`
- `tools/taghag_import/discover.py`
- `tools/taghag_import/tags.py`
- `tools/taghag_import/audio_probe.py`
- `tools/taghag_import/genre.py`
- `tools/taghag_import/receipt.py`
- `tools/taghag_import/db_client.py`
- `tools/tests/test_import_cli.py`
- `tools/tests/test_discover.py`
- `tools/tests/test_receipt.py`

### 10.1 Discovery

Behavior:

- Discover only `.mp3`, case-insensitive.
- Report `.m4a`, `.aac`, `.flac`, `.wav`, `.aiff`, `.aif`, `.alac`, `.ogg`,
  `.opus`, `.wma` as out-of-scope audio.
- Report other likely audio suffixes as out-of-scope audio.
- Ignore junk files:
  - `.DS_Store`
  - AppleDouble files starting `._`
  - `__MACOSX`
  - `.Trashes`
  - `.Spotlight-V100`
  - `.fseventsd`
  - hidden metadata folders
  - temporary files
- Do not delete, move, rename, or upload local files.

Acceptance:

- Out-of-scope audio is counted and reported.
- Junk is ignored, not counted as import failure.
- Only `.mp3` files produce MP3 import records.

### 10.2 Tag Reading

Use `mutagen` to read MP3 tags.

Extract when present:

- artist
- title
- album
- label
- catalog_number
- release_date
- year
- bpm
- musical_key
- genre
- subgenre
- isrc
- compilation
- rating
- energy

Rules:

- Do not write tags in importer v1.
- Do not use comments for Taghag receipts or notes.
- MP3 comments are reserved for Mixed in Key Energy. Reading comments for
  energy detection is allowed only if implemented conservatively and documented.

Missing metadata issue codes:

- `missing_artist`
- `missing_title`
- `missing_genre`
- `missing_subgenre`
- `missing_bpm`
- `missing_key`
- `missing_label`
- `missing_isrc`

Missing tags must produce `quality_check` issues, not failed imports.

### 10.3 Audio Probe

Use `ffprobe` and `ffmpeg` when available.

Probe:

- duration_s
- bitrate_kbps
- codec
- decode_ok

Rules:

- If `ffprobe` is unavailable, import proceeds with `tool_missing_ffprobe`.
- If `ffmpeg` is unavailable, import proceeds with `tool_missing_ffmpeg`.
- If suffix is `.mp3` but codec is not MP3, import proceeds with quality issue
  `codec_mismatch`.
- Decode failures produce `decode_failed`, not an importer crash.

Quality issue codes:

- `decode_failed`
- `duration_missing`
- `bitrate_missing`
- `bitrate_low`
- `codec_mismatch`
- `tool_missing_ffprobe`
- `tool_missing_ffmpeg`

### 10.4 Checksum And Identity

Rules:

- Prefer full `checksum_sha256`.
- `file_key = sha256:<hex>` when full checksum exists.
- `checksum_prefix` should be the first 16 or 24 checksum hex characters.
- If full checksum fails, use documented fallback:
  `stat:<size>:<mtime_ns>:<normalized_relative_path_hash>`.
- `identity_source = checksum_sha256` for full checksum.
- `identity_confidence = 1.0` for full checksum.
- `identity_source = stat_fallback` for fallback.
- `identity_confidence = 0.4` for fallback.
- Never use ISRC as `file_key`.

### 10.5 Genre Normalization

Use:

- `tools/taghag_import/genre.py`
- `tools/taghag_import/genre_rules.json`

Store:

- `canonical_genre`
- `canonical_subgenre`

Rules:

- Missing or unknown genre/subgenre is a quality issue.
- Do not fail import solely because genre is missing.

### 10.6 Receipt

Receipt path:

```text
artifacts/import_runs/<run_id>/receipt.jsonl
```

Rules:

- Generate `run_id` locally as UUID before scanning.
- Write receipt before database upload.
- Receipt must exist even if Supabase upload fails.
- Receipt must contain no secrets.
- Receipt must contain no audio bytes.
- Receipt should be sufficient to retry upload without rescanning.

Receipt event types:

- `import_run_start`
- `mp3_observed`
- `out_of_scope_audio`
- `quality_check`
- `tag_evidence`
- `import_run_summary`
- `upload_result`

### 10.7 Database Upload

Environment variables for tools:

- `TAGHAG_SUPABASE_URL`
- `TAGHAG_SUPABASE_SERVICE_ROLE_KEY` or `TAGHAG_SUPABASE_SECRET_KEY`
- `TAGHAG_OWNER_USER_ID`

Rules:

- Tools may use service role locally/server-side.
- Tools must not read `VITE_` web env vars.
- Web code must not read service-role env vars.
- Upsert `import_run` by `id`.
- Upsert `mp3_file` by `(owner_user_id, file_key)`.
- Insert `mp3_observation` for every run occurrence.
- Upsert `dj_tag` by `(owner_user_id, mp3_file_id)`.
- Insert `quality_check` for every run/file check.
- Insert `tag_evidence` rows if evidence exists.
- Upload must be idempotent for `mp3_file` and `dj_tag`.
- Upload must not dedupe `mp3_observation` across different runs.

Acceptance:

- Importing the same folder twice does not duplicate `mp3_file`.
- Re-importing creates a new `mp3_observation` for the new run.
- Local receipt exists even if upload fails.
- Missing tags create quality issue codes.
- Out-of-scope audio is counted and reported.

## 11. Phase 5: Postman Evidence Wiring

Goal: import provider evidence without coupling to tagslut.

CLI flag:

```bash
--postman-evidence /path/to/evidence.log
```

Parser rules:

- Parse lines containing `[Tag Evidence JSON]`.
- Malformed JSON does not crash import.
- Matched, `no_match`, `ambiguous`, and `error` results are stored.
- Duplicate evidence lines are handled deterministically.
- Raw marker JSON is preserved.

Matching rules:

- Match evidence to MP3 rows by ISRC first.
- If MP3 has no ISRC, do not guess by title/artist in v1.
- Allow title/artist matching only with `--unsafe-title-artist-evidence-match`.
- Unsafe title/artist matches must be stored with lookup type
  `unsafe_title_artist`.
- Unsafe title/artist matches must not automatically merge provider fields into
  `dj_tag`.
- No automatic row merge happens because of ISRC.

Storage:

- Store provider evidence in `tag_evidence`.
- Preserve `raw_marker_json`.
- Store `candidates_json`.
- Store `winning_fields_json`.
- Store `provider`, `lookup_type`, `lookup_key`, `provider_track_id`,
  `status`, `confidence`, `fetched_at`.

Merge-to-tag rules:

- Merge winning provider fields into `dj_tag` only when confidence and provider
  authority are clear.
- Ambiguous evidence is visible but does not update `dj_tag`.
- `no_match` and `error` are visible but do not update `dj_tag`.
- Beatport-like provider authority may win label and genre/subgenre.
- Spotify-like release evidence may inform album/release context only when it
  does not conflict with local context.
- If not certain, leave `dj_tag` unchanged and add quality/evidence issue.

Tests:

- matched result
- no_match result
- ambiguous result
- error result
- malformed JSON
- duplicate evidence line
- evidence import never blocks MP3 import
- raw evidence preserved
- ISRC does not merge rows

## 12. Phase 6: Web Types And Supabase Client

Goal: prepare the web app to use generated Supabase database types.

Files:

- `web/src/lib/database.types.ts`
- `web/src/lib/supabase.ts`
- `web/package.json`
- `.env.example`
- `README.md`

Type generation:

```bash
supabase gen types typescript --local > web/src/lib/database.types.ts
```

Add script to `web/package.json`:

```json
{
  "scripts": {
    "db:types": "supabase gen types typescript --local > src/lib/database.types.ts"
  }
}
```

If using local npm binary:

```json
{
  "scripts": {
    "db:types": "npx supabase gen types typescript --local > src/lib/database.types.ts"
  }
}
```

Create `web/src/lib/supabase.ts`:

- Import `createClient` from `@supabase/supabase-js`.
- Import `Database` from `./database.types`.
- Use `VITE_SUPABASE_URL`.
- Use `VITE_SUPABASE_PUBLISHABLE_KEY`.
- Throw a clear error if either env var is missing.
- Do not include service role or secret keys.

`.env.example` entries:

```text
VITE_SUPABASE_URL=
VITE_SUPABASE_PUBLISHABLE_KEY=

TAGHAG_SUPABASE_URL=
TAGHAG_SUPABASE_SERVICE_ROLE_KEY=
TAGHAG_OWNER_USER_ID=
```

README note:

- Import tools use service role locally/server-side.
- Web app uses publishable key and authenticated browser access.
- Service role must never be committed or placed under `web/`.

Verify:

```bash
rg "SERVICE_ROLE|SECRET_KEY|service_role" web
cd web && npm run typecheck
```

## 13. Phase 7: React/Vite UI Shell

Goal: create the first private Taghag UI.

Screens:

1. Import Runs
2. Library Table
3. Track Detail
4. Crates
5. Dashboard

Rules:

- Keep UI simple and data-first.
- Use typed Supabase queries.
- Add route-level placeholders only where data is not ready.
- Show empty states cleanly.
- No schema creation from UI.
- No Lovable-generated SQL applied directly.
- No service-role key in browser.
- Filters should be URL-backed where practical.

Suggested files:

- `web/src/lib/supabase.ts`
- `web/src/lib/queries.ts`
- `web/src/App.tsx`
- `web/src/components/AppShell.tsx`
- `web/src/components/LibraryTable.tsx`
- `web/src/components/DashboardCards.tsx`
- `web/src/routes/ImportRuns.tsx`
- `web/src/routes/Library.tsx`
- `web/src/routes/TrackDetail.tsx`
- `web/src/routes/Crates.tsx`
- `web/src/routes/Dashboard.tsx`

Library Table columns:

- filename
- artist
- title
- label
- bpm
- musical_key
- canonical_genre
- canonical_subgenre
- quality status
- evidence status

Dashboard counts:

- total MP3s
- missing artist/title
- missing BPM/key
- missing genre/subgenre
- missing label
- duplicate checksum candidates
- provider evidence statuses

Filters:

- import_run
- genre
- bpm range
- key
- quality status
- provider status

Acceptance:

- `npm install` works.
- `npm run dev` works.
- App shows empty states cleanly.
- App does not create schema.
- App uses generated `Database` type.

## 14. Phase 8: Minimum Test Suite

Python tests:

- MP3 tag extraction from fixture or mocked boundary.
- Out-of-scope audio reporting.
- Genre normalization.
- Idempotent import receipt generation.
- Missing metadata produces issue codes.
- Postman evidence parsing.

Supabase tests:

- `supabase db reset` applies migrations.
- Unauthenticated access is denied.
- Authenticated access follows owner policies.
- Service role can upsert import tables.
- Generated TypeScript types match schema.
- All 9 public app tables have RLS enabled.
- No anon policies exist.

Web tests:

- Library table renders fixture data.
- Empty import state renders.
- Dashboard count cards render.
- Crate ordering component handles fixture data.

Fixture rules:

- Do not commit real music files.
- Generate a tiny synthetic MP3 during tests if a binary fixture is needed.
- Prefer mocks for mutagen/ffprobe boundaries when testing importer logic.
- Keep tests fast.

Commands:

```bash
pytest tools/tests
supabase db reset
cd web && npm run typecheck
cd web && npm test
```

If a command is not configured, either configure it or say exactly why it was
not run.

## 15. Phase 9: Clean-Room Audit

Goal: prevent Taghag from silently becoming tagslut v3 again.

Create:

```text
tools/audit_cleanroom.py
```

Command:

```bash
python tools/audit_cleanroom.py
```

The audit should scan:

- Python source
- SQL migrations
- TypeScript/React source
- Config files
- Tests
- Active docs, with allow markers

Forbidden terms:

- `from tagslut`
- `import tagslut`
- `asset_file`
- `track_identity`
- `asset_link`
- `preferred_asset`
- `move_plan`
- `move_execution`
- `provenance_event`
- `AAC_LIBRARY`
- `M4A derivative`
- `AAC-first`

Allowed only inside documentation sections marked:

```text
cleanroom-audit: allow-start
cleanroom-audit: allow-end
```

Rules:

- Never allow forbidden terms in migrations.
- Never allow forbidden imports in code.
- Fail with file path and line number.

Tests:

- Audit passes on clean project.
- Audit fails if a forbidden Python import is introduced.
- Audit fails if a forbidden schema name appears in SQL.
- Audit allows marked docs warning sections only.

Docs:

- README includes `python tools/audit_cleanroom.py`.
- AGENT.md says run clean-room audit before commit when schema/importer/web
  behavior changes.

## 16. Final Verification Checklist

Run from repo root:

```bash
cd /Users/g/Projects/taghag
git status --short
pytest tools/tests
python tools/audit_cleanroom.py
supabase db reset
supabase gen types typescript --local > web/src/lib/database.types.ts
cd web && npm install
cd web && npm run typecheck
```

Search checks:

```bash
cd /Users/g/Projects/taghag
rg "from tagslut|import tagslut" .
rg "asset_file|track_identity|asset_link|preferred_asset|move_plan|move_execution|provenance_event|AAC_LIBRARY|M4A derivative|AAC-first" .
rg "service_role|SERVICE_ROLE|SECRET_KEY" web
rg "mp3_track" supabase
rg "storage|bucket|upload_path|object_path|object_id" supabase
```

Database acceptance:

- Migration applies cleanly.
- Exactly the required 9 public app tables exist.
- `mp3_file` exists.
- `mp3_track` does not exist.
- RLS is enabled on every public app table.
- No anon policies exist.
- Grants are explicit.
- No storage/upload path concepts exist.
- ISRC is not unique.
- Service role grants are server/importer only.

Importer acceptance:

- Same folder imported twice does not duplicate `mp3_file`.
- Same folder imported twice creates separate `mp3_observation` rows.
- Out-of-scope audio files are counted and reported.
- Missing title/artist/genre/bpm/key/label produce issue codes.
- Receipt exists even if upload fails.
- Evidence import never blocks MP3 import.
- Ambiguous evidence is visible.
- Raw evidence is preserved.
- No automatic row merge happens because of ISRC.

Web acceptance:

- Generated `Database` type is imported by web code.
- No service-role key appears under `web/`.
- Empty states render cleanly.
- Library table renders fixture data.
- Dashboard count cards render.
- No UI code creates schema.

Clean-room acceptance:

- `python tools/audit_cleanroom.py` passes.
- Forbidden tagslut v3 concepts fail the audit if introduced into active code
  or migrations.

## 17. Definition Of Done

The project is ready for the next implementation milestone only when:

- The schema matches the 9-table MP3-only model.
- The migration can be read without tagslut context.
- `supabase db reset` applies cleanly.
- RLS and grants are verified.
- The importer can produce local receipts.
- Database upload is idempotent for `mp3_file`.
- Observations are per-run.
- Evidence is optional, visible, and non-blocking.
- The web app uses typed Supabase access with publishable key only.
- Tests pass or missing test commands are explicitly documented.
- Clean-room audit passes.
- README and AGENT.md match the implemented commands.
- Changes are committed and pushed.
