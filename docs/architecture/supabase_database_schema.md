# Taghag and Cuecifer Supabase Database Creation

This document describes how to create the Supabase database used by Taghag and
the Cuecifer analysis layer.

Taghag natively processes lossless FLAC files and is metadata-only. The database stores local-file metadata,
tagging decisions, import receipts, evidence, quality checks, crates, saved
views, and Cuecifer analysis outputs. It does not store audio bytes, derived
audio snippets, cloud object paths, or local file-moving state.

## Architecture Decision

Taghag and Cuecifer use Supabase/Postgres as the metadata system of record.
SQLite is not an alternative setup path unless a future task explicitly changes
the architecture.

This decision separates the system into two boundaries:

- Local disks hold FLAC files and local analysis artifacts.
- Supabase holds metadata, receipts, tags, evidence, analysis results, crates,
  saved views, and authenticated ownership.

Docker is not required to run Taghag itself. Docker is required only when using
the local Supabase CLI stack because `supabase start` and `supabase db reset`
run the local Supabase services in containers.

Hosted Supabase does not imply a paid plan. Taghag is metadata-only, so a free
hosted Supabase development project should be sufficient initially, subject to
the current Supabase free-tier quotas.

| Setup | Docker | Cost assumption | Migration path | Verification |
| --- | --- | --- | --- | --- |
| Free hosted Supabase dev project | Not required | Free tier initially | Dashboard SQL editor or linked `supabase db push` | Run the SQL checks in this document against the hosted project. |
| Local Supabase CLI stack | Required | Local development | `supabase db reset` | Reset from migrations, then run local checks/tests. |

## Current Schema State

The source-controlled database lives in `supabase/migrations/` and is applied
in timestamp order:

1. `20260606000000_initial_audio_metadata_schema.sql`
2. `20260607203437_add_cuecifer_track_analysis.sql`

The initial migration creates the Taghag core:

| Table | Purpose |
| --- | --- |
| `import_run` | One scanner/importer run and its receipt summary. |
| `audio_file` | Durable metadata row for a local FLAC file. `file_key` is owner-scoped and unique. |
| `audio_observation` | Per-run observation of a local path, checksum, and status. |
| `dj_tag` | Operator-facing per-file metadata, tags, rating, notes, and manual override state. |
| `tag_evidence` | Provider evidence such as ISRC lookups and candidate fields. |
| `quality_check` | Decode, duration, bitrate, missing-tag, and duplicate issue records. |
| `crate` | User-owned DJ crates. |
| `crate_track` | Crate membership and ordering. |
| `saved_view` | Saved UI filters, routes, sort state, and chart state. |

The Cuecifer migration adds:

| Table | Purpose |
| --- | --- |
| `track_analysis` | Metadata-only Essentia/Cuecifer attributes for an existing `audio_file`. |

`track_analysis` currently stores the five Cuecifer attributes:

- `happy`
- `aggressive`
- `relaxed`
- `party`
- `danceability`

It also stores genre candidates, model metadata, the source artifact digest,
the local source path, raw JSON evidence, and `computed_at`.

## Supabase Project Creation

Use either a hosted Supabase project or a local Supabase CLI stack.

Free hosted Supabase is the preferred lightweight development path when
avoiding Docker. The local CLI stack remains the reproducible full-reset path
when Docker is available.

### Hosted Project

1. Create a new Supabase project.
2. Create or invite the first authenticated user who will own the imported
   library.
3. Record that user's `auth.users.id` as `TAGHAG_OWNER_USER_ID`.
4. Apply the migrations in timestamp order.
5. Configure server-side importer environment variables.
6. Configure frontend-safe Vite environment variables.
7. Run the verification SQL in this document.

If applying migrations through the Supabase Dashboard SQL editor, run each SQL
file completely and in order. If using the CLI against a linked hosted project,
run:

```bash
supabase link --project-ref <project-ref>
supabase db push
supabase migration list
```

### Local CLI Stack

The checked-in `supabase/config.toml` defines the local project id, API ports,
the exposed `public` schema, and Postgres major version 15.

Start locally with:

```bash
supabase start
supabase db reset
supabase migration list --local
```

Docker is required for the local stack. If Docker is unavailable, use the hosted
project path and apply the source-controlled SQL there.

## Required Environment

The importer and analysis import use service-role credentials server-side only.
Never put these values in `web/` or any `VITE_` variable.

```bash
TAGHAG_SUPABASE_URL=https://your-project.supabase.co
TAGHAG_SUPABASE_SERVICE_ROLE_KEY=replace-me
TAGHAG_SUPABASE_SECRET_KEY=
TAGHAG_OWNER_USER_ID=<auth.users.id for the library owner>
TAGHAG_DB_SCHEMA=public
TAGHAG_IMPORT_ACTOR_ID=<operator/user id if needed by future tooling>
TAGHAG_FLAC_OUTPUT_ROOT=/Volumes/LOSSY/taghag
```

Frontend values must be publishable/browser-safe only:

```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=replace-me
VITE_TAGHAG_APP_NAME=Taghag
VITE_TAGHAG_ENV=local
```

## Ownership Model

Every app table includes `owner_user_id uuid not null references auth.users(id)
on delete cascade`.

That means imports cannot be uploaded until the target owner exists in
Supabase Auth. The importer adds `owner_user_id` from `TAGHAG_OWNER_USER_ID`
when it uploads receipt events.

The important identity rules are:

- `audio_file.id` is the durable internal database key.
- `file_key` is the importer-owned local file identity and is unique per owner.
- ISRC is evidence, not identity, and is intentionally not unique.
- Cuecifer `track_analysis` attaches to `audio_file` through `(audio_file_id,
  owner_user_id)`.
- Local audio paths are operational metadata; local audio bytes stay on disk.

## Security And API Exposure

The migrations intentionally harden the public schema:

- Revoke public and anon schema/table access.
- Grant `usage` on `public` only to `authenticated` and `service_role`.
- Enable RLS on every app table.
- Add authenticated policies scoped with `owner_user_id = auth.uid()`.
- Give authenticated users read access to metadata/evidence tables.
- Give authenticated users write access only where the browser app needs it:
  `dj_tag`, `crate`, `crate_track`, and `saved_view`.
- Give `service_role` full table access for local importer jobs.

Supabase projects can expose schemas through the Data API. Recent Supabase
behavior means SQL-created tables may require explicit API exposure settings in
addition to SQL grants. If a table exists but the frontend cannot query it,
check both:

1. Supabase Dashboard API/Data API exposed schema and table settings.
2. SQL grants and RLS policies in the migrations.

Do not fix frontend access by disabling RLS.

## Core Relationships

The high-level relationship graph is:

```text
auth.users
  -> import_run
       -> audio_observation
       -> quality_check
  -> audio_file
       -> dj_tag
       -> audio_observation
       -> quality_check
       -> tag_evidence
       -> crate_track
       -> track_analysis
  -> crate
       -> crate_track
  -> saved_view
```

Important constraints:

- `audio_file` is unique on `(owner_user_id, file_key)`.
- `dj_tag` is unique on `(owner_user_id, audio_file_id)`.
- `track_analysis` is unique on `(owner_user_id, audio_file_id, schema_name,
  source_artifact_sha256)`.
- Cross-table foreign keys include `owner_user_id` so records cannot silently
  attach across owners.

## Creation Verification SQL

Run these checks after applying migrations.

### Confirm Tables

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'import_run',
    'audio_file',
    'audio_observation',
    'dj_tag',
    'tag_evidence',
    'quality_check',
    'crate',
    'crate_track',
    'saved_view',
    'track_analysis'
  )
order by table_name;
```

Expected: 10 rows.

### Confirm RLS

```sql
select relname, relrowsecurity
from pg_class
where relnamespace = 'public'::regnamespace
  and relkind = 'r'
  and relname in (
    'import_run',
    'audio_file',
    'audio_observation',
    'dj_tag',
    'tag_evidence',
    'quality_check',
    'crate',
    'crate_track',
    'saved_view',
    'track_analysis'
  )
order by relname;
```

Expected: every row has `relrowsecurity = true`.

### Confirm Policies

```sql
select tablename, policyname, cmd, roles
from pg_policies
where schemaname = 'public'
order by tablename, policyname;
```

Expected: authenticated owner-scoped policies exist for every user-visible
table, including `authenticated_select_track_analysis`.

### Confirm Importer Grants

```sql
select grantee, table_name, privilege_type
from information_schema.role_table_grants
where table_schema = 'public'
  and table_name in (
    'import_run',
    'audio_file',
    'audio_observation',
    'dj_tag',
    'tag_evidence',
    'quality_check',
    'crate',
    'crate_track',
    'saved_view',
    'track_analysis'
  )
  and grantee in ('authenticated', 'service_role')
order by table_name, grantee, privilege_type;
```

Expected: authenticated receives the browser-safe privileges from the
migrations; `service_role` receives importer privileges.

### Confirm The Owner User Exists

```sql
select id, email, created_at
from auth.users
where id = '<TAGHAG_OWNER_USER_ID>'::uuid;
```

Expected: one row.

## Data Loading Sequence

Use this order when creating a fresh Taghag/Cuecifer database:

1. Apply both migrations.
2. Create or identify the owner user in Supabase Auth.
3. Configure server-side env vars with the service-role key and owner id.
4. Import FLAC metadata:

   ```bash
   cd tools
   taghag-import import-batch \
     --root /Volumes/LOSSY/taghag/identified/flac \
     --run-name identified
   ```

5. Import provider evidence during or after MP3 import when available:

   ```bash
   taghag-import import-batch \
     --root /Volumes/LOSSY/taghag/identified/flac \
     --run-name identified-with-evidence \
     --postman-evidence /path/to/evidence.log
   ```

6. Run Apple Music Understanding analysis only after the corresponding FLAC
   files already exist in `audio_file`:

   ```bash
   taghag-import analyze \
     --target /path/to/flac-or-directory
   ```

The Apple analysis command resolves each FLAC by Taghag `file_key`, then stores
raw analyzer provenance in `apple_analysis_runs`, normalized curves in
`apple_track_analysis`, derived scalars in `apple_derived_features`, and Apple
segments/cues in `track_segment` and `track_cue`. Unmatched files are counted
and skipped rather than creating orphan records. Successful Apple runs also
write a `track_embedding` row with `vector_schema = 'apple_hybrid_v1'`.

`apple_hybrid_v1` keeps the existing seven-dimensional pgvector shape and uses
these interpreted dimensions:

1. `apple_bpm_norm` - Apple BPM divided by 200 and clipped to 0..1.
2. `pace_mean` - mean Apple pace scalar.
3. `pace_volatility` - Apple pace standard deviation.
4. `vocal_intensity_mean` - mean Apple vocal activity.
5. `drum_intensity_mean` - mean Apple drum activity.
6. `bass_intensity_mean` - mean Apple bass activity.
7. `loudness_range_norm` - Apple loudness range divided by 30 dB and clipped.

Run `taghag-import apple-audit --out <csv>` after analysis to write a
metadata-only disagreement report. The report flags Apple-vs-`dj_tag` BPM
deltas above the configured threshold, low Apple/MIK BPM agreement scores, and
unstable Apple keys.

## Cuecifer Expansion Notes

The current committed Cuecifer database layer is `track_analysis`. The broader
Cuecifer product plan still expects future migrations for:

- operator tier policy versions,
- reviewed external track matches,
- read-only Rekordbox observations,
- recommendation sessions,
- recommendation candidates,
- optional tier fields on `dj_tag`.

Those future tables should follow the same pattern:

- `owner_user_id` on every table,
- foreign keys that include `owner_user_id`,
- no anon grants,
- RLS enabled,
- authenticated policies scoped to `auth.uid()`,
- service-role grants for local importers,
- no stored audio bytes,
- no static set-relative intensity direction column.

## Cuecifer Engine Commands

The engine and local sync helpers live under `tools/cuecifer/` and use the
same owner-scoped environment variables as the importer.

Typical operator flow:

```bash
cd tools
python cuecifer/sonic_discovery.py recompute-all
python cuecifer/crates.py --seed /absolute/path/to/track.flac --limit 30 --out-dir ../artifacts/crates
python cuecifer/map.py --out-dir ../artifacts/cuecifer_map
python cuecifer/human_correction.py apply --music-dir /Volumes/LOSSY/taghag/flacs --execute
python cuecifer/human_correction.py audit --out ../artifacts/manual_review_needed.csv
python cuecifer/sync_vibes.py --execute
```

`sonic_discovery.py` reads `track_analysis` and `dj_tag`, computes the
normalized `sonic7_v1` vector, and upserts `track_embedding`. Apple analysis
upserts `apple_hybrid_v1` vectors during `taghag-import analyze`. Butter Flow
uses the legacy cue/vector model as a fallback and adds Apple-derived
phrase-boundary, pace, vocal-overlap, loudness-handoff, BPM-disagreement, and
key-stability cost terms when `apple_derived_features` rows exist.
`human_correction.py` writes pinned corrections into `track_curation`, and
`sync_vibes.py` writes the resolved vibe list back into local FLAC comments.

## Operational Notes

- `supabase/seed.sql` is intentionally empty. Do not seed fake production-owned
  rows.
- Run `python tools/audit_cleanroom.py` after database or importer edits.
- Run `pytest tools/tests -q` after importer or schema-contract edits.
- Run `cd web && npm run build` after updating generated database types or UI
  code.
- Regenerate `web/src/lib/database.types.ts` after schema changes that affect
  the frontend.
- Keep service-role and secret keys out of frontend env vars. Only `VITE_`
  publishable values belong in `web/`.

## External Reference Check

Checked on 2026-06-08:

- [Supabase CLI docs](https://supabase.com/docs/guides/local-development/cli/getting-started):
  local projects use `supabase init` and `supabase start`;
  migration files live under `supabase/migrations`; the CLI can create, list,
  and apply migrations.
- [Supabase CLI reference](https://supabase.com/docs/reference/cli/introduction):
  `supabase db push` pushes new migrations, and `supabase migration list`
  compares local and remote migration history.
- [Supabase changelog](https://supabase.com/changelog?tags=database): recent
  Data API behavior makes explicit table exposure, grants, and RLS verification
  important for SQL-created tables.
- [Supabase API security guidance](https://supabase.com/docs/guides/api/securing-your-api):
  grants control role access to Data API objects, while RLS controls row
  visibility and mutation permissions.
- [Supabase RLS guidance](https://supabase.com/docs/guides/database/postgres/row-level-security):
  exposed user data should be protected with row-level security rather than
  client-side filtering.
