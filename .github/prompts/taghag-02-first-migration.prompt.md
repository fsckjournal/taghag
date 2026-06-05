Goal:
Create the first MP3-only metadata schema with exactly these public app tables:

1. `import_run`
2. `mp3_file`
3. `mp3_observation`
4. `dj_tag`
5. `tag_evidence`
6. `quality_check`
7. `crate`
8. `crate_track`
9. `saved_view`

Hard rules:
- `mp3_file` is the primary asset table.
- Do not create `mp3_track`.
- MP3 files remain local.
- Do not create Supabase Storage buckets/tables/policies.
- Do not add `upload_path`, `storage_path`, `bucket_id`, `object_id`, or `object_path` columns.
- Do not make ISRC unique.
- Do not use ISRC as a row identity.
- ISRC can be indexed for evidence lookup and duplicate detection.
- Use UUID primary keys.
- Every table has `owner_user_id`.
- `owner_user_id` references `auth.users(id)` on delete cascade.
- Every table with `updated_at` gets an `updated_at` trigger.
- Use JSONB only where flexible evidence/check payloads are intended.
- Add explicit grants.
- Enable RLS on every public app table.
- No anon policies.
- Revoke anon explicitly.

Ownership safety:
- Add `unique(id, owner_user_id)` on parent tables that are referenced by child tables.
- Use composite foreign keys from child tables to parent tables where practical.
- Example: `dj_tag(mp3_file_id, owner_user_id)` references `mp3_file(id, owner_user_id)`.
- This prevents a user-owned child row from referencing another user’s parent row.

Required extension:
- `create extension if not exists pgcrypto;`

Updated-at trigger:
- Create `public.set_updated_at()`.
- Use language `plpgsql`.
- It should set `new.updated_at = now()`.
- Revoke execute from public if needed.
- Attach to `import_run`, `mp3_file`, `mp3_observation`, `dj_tag`, `tag_evidence`, `quality_check`, `crate`, `crate_track`, `saved_view`.

Table contract:

`import_run`:
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
- check status in `pending`, `running`, `completed`, `failed`, `cancelled`
- `unique(id, owner_user_id)`

`mp3_file`:
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
- `unique(owner_user_id, file_key)`
- `unique(id, owner_user_id)`
- check `codec = 'mp3'`
- check `identity_confidence is null or between 0 and 1`
- check `size_bytes is null or size_bytes >= 0`
- check `duration_s is null or duration_s >= 0`
- check `bitrate_kbps is null or bitrate_kbps > 0`

`mp3_observation`:
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
- `foreign key(import_run_id, owner_user_id) references import_run(id, owner_user_id) on delete cascade`
- `foreign key(mp3_file_id, owner_user_id) references mp3_file(id, owner_user_id) on delete set null`
- check status in `observed`, `imported`, `skipped`, `out_of_scope`, `failed`

`dj_tag`:
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
- `foreign key(mp3_file_id, owner_user_id) references mp3_file(id, owner_user_id) on delete cascade`
- `unique(owner_user_id, mp3_file_id)`
- check `rating is null or rating between 0 and 5`
- check `bpm is null or bpm > 0`
- check `year is null or year between 1900 and 2100`
- Do not make `isrc` unique.

`tag_evidence`:
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
- `foreign key(mp3_file_id, owner_user_id) references mp3_file(id, owner_user_id) on delete cascade`
- check status in `matched`, `no_match`, `ambiguous`, `error`, `malformed`, `duplicate`
- check `confidence is null or confidence between 0 and 1`

`quality_check`:
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
- `foreign key(import_run_id, owner_user_id) references import_run(id, owner_user_id) on delete set null`
- `foreign key(mp3_file_id, owner_user_id) references mp3_file(id, owner_user_id) on delete cascade`

`crate`:
- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `name text not null`
- `description text`
- `sort_order integer not null default 0`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`
- `unique(owner_user_id, name)`
- `unique(id, owner_user_id)`

`crate_track`:
- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `crate_id uuid not null`
- `mp3_file_id uuid not null`
- `position integer not null default 0`
- `notes text`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`
- `foreign key(crate_id, owner_user_id) references crate(id, owner_user_id) on delete cascade`
- `foreign key(mp3_file_id, owner_user_id) references mp3_file(id, owner_user_id) on delete cascade`
- `unique(crate_id, mp3_file_id)`
- Do not add `unique(crate_id, position)` in v1 unless reorder logic is already transactional and collision-safe.

`saved_view`:
- `id uuid primary key default gen_random_uuid()`
- `owner_user_id uuid not null references auth.users(id) on delete cascade`
- `name text not null`
- `route text not null`
- `filters_json jsonb not null default '{}'::jsonb`
- `sort_json jsonb not null default '{}'::jsonb`
- `chart_state_json jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`
- `unique(owner_user_id, name)`

Indexes:
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

Grants:
- `revoke all on schema public from anon;`
- `revoke all on all tables in schema public from anon;`
- `revoke all on all sequences in schema public from anon;`
- `grant usage on schema public to authenticated, service_role;`
- `grant select on read tables to authenticated.`
- `grant select, insert, update on dj_tag to authenticated.`
- `grant select, insert, update, delete on crate, crate_track, saved_view to authenticated.`
- `grant select, insert, update, delete on all 9 app tables to service_role.`
- Do not grant anon anything in v1.

Suggested authenticated grants:
- `import_run`: `select`
- `mp3_file`: `select`
- `mp3_observation`: `select`
- `tag_evidence`: `select`
- `quality_check`: `select`
- `dj_tag`: `select`, `insert`, `update`
- `crate`: `select`, `insert`, `update`, `delete`
- `crate_track`: `select`, `insert`, `update`, `delete`
- `saved_view`: `select`, `insert`, `update`, `delete`

RLS:
- `alter table public.<table> enable row level security` for all 9 tables.
- No `CREATE POLICY` to `anon`.
- Use `TO authenticated`, not `auth.role()`.
- `SELECT` policy uses `owner_user_id = (select auth.uid())`.
- `INSERT` policy uses `owner_user_id = (select auth.uid())`.
- `UPDATE` policy uses `USING` and `WITH CHECK` with `owner_user_id = (select auth.uid())`.
- `DELETE` policy uses `owner_user_id = (select auth.uid())`.
- Match policies to grants. Do not create write policies on read-only web tables unless needed.

Service role:
- Do not create frontend code that uses `service_role`.
- SQL comments should say `service_role` is for local importer/server-side tooling only.
- Supabase `service_role` bypasses RLS, but explicit table grants still document importer capability.

Migration validation queries:
- `select tablename from pg_tables where schemaname = 'public' order by tablename;`
- `select c.relname, c.relrowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' order by c.relname;`
- `select policyname, tablename, roles from pg_policies where schemaname = 'public' order by tablename, policyname;`
- `select policyname from pg_policies where schemaname = 'public' and 'anon' = any(roles);`
- `select grantee, table_name, privilege_type from information_schema.role_table_grants where table_schema = 'public' order by table_name, grantee, privilege_type;`
