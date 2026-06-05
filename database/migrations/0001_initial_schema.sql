begin;

create extension if not exists pgcrypto;

revoke all on schema public from public;
grant usage on schema public to authenticated, service_role;

create table if not exists public.import_run (
  id uuid primary key default gen_random_uuid(),
  started_by_user_id uuid,
  source_root text not null,
  status text not null default 'pending' check (status in ('pending', 'scanned', 'loaded', 'failed')),
  notes text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.mp3_track (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  import_run_id uuid references public.import_run(id) on delete set null,
  library_fingerprint text not null,
  file_name text not null,
  source_root text not null,
  relative_path_hint text not null,
  file_size_bytes bigint,
  duration_seconds numeric(10,3),
  bit_rate integer,
  title text,
  artist text,
  album text,
  raw_genre text,
  normalized_genre text,
  genre_family text,
  bpm numeric(6,2),
  musical_key text,
  release_year text,
  track_number text,
  composer text,
  comment text,
  decode_ok boolean not null default false,
  probe_ok boolean not null default false,
  raw_id3 jsonb not null default '{}'::jsonb,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, library_fingerprint)
);

create table if not exists public.dj_tag (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  name text not null,
  tag_type text not null default 'label' check (tag_type in ('label', 'genre', 'energy', 'vibe', 'moment')),
  color_hex text,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, name, tag_type)
);

create table if not exists public.tag_evidence (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  mp3_track_id uuid not null references public.mp3_track(id) on delete cascade,
  dj_tag_id uuid references public.dj_tag(id) on delete set null,
  import_run_id uuid references public.import_run(id) on delete set null,
  evidence_source text not null default 'import',
  evidence_payload jsonb not null default '{}'::jsonb,
  confidence numeric(4,3),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.quality_check (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  mp3_track_id uuid not null references public.mp3_track(id) on delete cascade,
  import_run_id uuid references public.import_run(id) on delete set null,
  check_type text not null,
  status text not null check (status in ('pass', 'warn', 'fail')),
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.crate (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  name text not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, name)
);

create table if not exists public.crate_track (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  crate_id uuid not null references public.crate(id) on delete cascade,
  mp3_track_id uuid not null references public.mp3_track(id) on delete cascade,
  sort_index integer not null default 0,
  created_at timestamptz not null default now(),
  unique (crate_id, mp3_track_id)
);

create table if not exists public.saved_view (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  name text not null,
  view_definition jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, name)
);

revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;

alter table public.import_run enable row level security;
alter table public.mp3_track enable row level security;
alter table public.dj_tag enable row level security;
alter table public.tag_evidence enable row level security;
alter table public.quality_check enable row level security;
alter table public.crate enable row level security;
alter table public.crate_track enable row level security;
alter table public.saved_view enable row level security;

create policy "authenticated_rw_import_run"
  on public.import_run
  for all
  to authenticated
  using (started_by_user_id = auth.uid())
  with check (started_by_user_id = auth.uid());

create policy "authenticated_rw_mp3_track"
  on public.mp3_track
  for all
  to authenticated
  using (owner_user_id = auth.uid())
  with check (owner_user_id = auth.uid());

create policy "authenticated_rw_dj_tag"
  on public.dj_tag
  for all
  to authenticated
  using (owner_user_id = auth.uid())
  with check (owner_user_id = auth.uid());

create policy "authenticated_rw_tag_evidence"
  on public.tag_evidence
  for all
  to authenticated
  using (owner_user_id = auth.uid())
  with check (owner_user_id = auth.uid());

create policy "authenticated_rw_quality_check"
  on public.quality_check
  for all
  to authenticated
  using (owner_user_id = auth.uid())
  with check (owner_user_id = auth.uid());

create policy "authenticated_rw_crate"
  on public.crate
  for all
  to authenticated
  using (owner_user_id = auth.uid())
  with check (owner_user_id = auth.uid());

create policy "authenticated_rw_crate_track"
  on public.crate_track
  for all
  to authenticated
  using (owner_user_id = auth.uid())
  with check (owner_user_id = auth.uid());

create policy "authenticated_rw_saved_view"
  on public.saved_view
  for all
  to authenticated
  using (owner_user_id = auth.uid())
  with check (owner_user_id = auth.uid());

commit;
