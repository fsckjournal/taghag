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

create table public.import_run (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  run_name text,
  source_root text,
  status text not null default 'pending',
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  tool_versions_json jsonb not null default '{}'::jsonb,
  summary_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint import_run_status_check
    check (status in ('pending', 'running', 'completed', 'failed', 'cancelled')),
  unique (id, owner_user_id)
);

create table public.audio_file (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  file_key text not null,
  path text not null,
  filename text not null,
  size_bytes bigint,
  mtime_ns bigint,
  duration_s numeric,
  bitrate_kbps integer,
  codec text not null default 'mp3',
  checksum_sha256 text,
  checksum_prefix text,
  identity_source text,
  identity_confidence numeric,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, file_key),
  unique (id, owner_user_id),
  constraint audio_file_codec_check check (codec = 'mp3'),
  constraint audio_file_identity_confidence_check
    check (identity_confidence is null or identity_confidence between 0 and 1),
  constraint audio_file_size_bytes_check check (size_bytes is null or size_bytes >= 0),
  constraint audio_file_duration_s_check check (duration_s is null or duration_s >= 0),
  constraint audio_file_bitrate_kbps_check check (bitrate_kbps is null or bitrate_kbps > 0)
);

create table public.audio_observation (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  import_run_id uuid not null,
  audio_file_id uuid,
  observed_path text not null,
  observed_size_bytes bigint,
  observed_mtime_ns bigint,
  observed_checksum_sha256 text,
  status text not null,
  issue_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint audio_observation_import_run_owner_fk
    foreign key (import_run_id, owner_user_id)
    references public.import_run(id, owner_user_id)
    on delete cascade,
  constraint audio_observation_audio_file_owner_fk
    foreign key (audio_file_id, owner_user_id)
    references public.audio_file(id, owner_user_id)
    on delete set null (audio_file_id),
  constraint audio_observation_status_check
    check (status in ('observed', 'imported', 'skipped', 'out_of_scope', 'failed'))
);

create table public.dj_tag (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  audio_file_id uuid not null,
  artist text,
  title text,
  album text,
  label text,
  catalog_number text,
  release_date date,
  year integer,
  bpm numeric,
  musical_key text,
  canonical_genre text,
  canonical_subgenre text,
  isrc text,
  compilation boolean,
  rating integer,
  energy text,
  role text,
  notes text,
  tag_source text,
  manual_override boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint dj_tag_audio_file_owner_fk
    foreign key (audio_file_id, owner_user_id)
    references public.audio_file(id, owner_user_id)
    on delete cascade,
  unique (owner_user_id, audio_file_id),
  constraint dj_tag_rating_check check (rating is null or rating between 0 and 5),
  constraint dj_tag_bpm_check check (bpm is null or bpm > 0),
  constraint dj_tag_year_check check (year is null or year between 1900 and 2100)
);

create table public.tag_evidence (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  audio_file_id uuid not null,
  provider text not null,
  lookup_type text not null,
  lookup_key text not null,
  provider_track_id text,
  status text not null,
  confidence numeric,
  winning_fields_json jsonb not null default '{}'::jsonb,
  candidates_json jsonb not null default '[]'::jsonb,
  raw_marker_json jsonb not null default '{}'::jsonb,
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint tag_evidence_audio_file_owner_fk
    foreign key (audio_file_id, owner_user_id)
    references public.audio_file(id, owner_user_id)
    on delete cascade,
  constraint tag_evidence_status_check
    check (status in ('matched', 'no_match', 'ambiguous', 'error', 'malformed', 'duplicate')),
  constraint tag_evidence_confidence_check
    check (confidence is null or confidence between 0 and 1)
);

create table public.quality_check (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  import_run_id uuid,
  audio_file_id uuid not null,
  decode_ok boolean,
  duration_ok boolean,
  bitrate_ok boolean,
  missing_tag_flags_json jsonb not null default '[]'::jsonb,
  duplicate_flags_json jsonb not null default '[]'::jsonb,
  issue_codes_json jsonb not null default '[]'::jsonb,
  tool_name text,
  tool_version text,
  checked_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint quality_check_import_run_owner_fk
    foreign key (import_run_id, owner_user_id)
    references public.import_run(id, owner_user_id)
    on delete set null (import_run_id),
  constraint quality_check_audio_file_owner_fk
    foreign key (audio_file_id, owner_user_id)
    references public.audio_file(id, owner_user_id)
    on delete cascade
);

create table public.crate (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, name),
  unique (id, owner_user_id)
);

create table public.crate_track (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  crate_id uuid not null,
  audio_file_id uuid not null,
  position integer not null default 0,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint crate_track_crate_owner_fk
    foreign key (crate_id, owner_user_id)
    references public.crate(id, owner_user_id)
    on delete cascade,
  constraint crate_track_audio_file_owner_fk
    foreign key (audio_file_id, owner_user_id)
    references public.audio_file(id, owner_user_id)
    on delete cascade,
  unique (crate_id, audio_file_id)
);

create table public.saved_view (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  route text not null,
  filters_json jsonb not null default '{}'::jsonb,
  sort_json jsonb not null default '{}'::jsonb,
  chart_state_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, name)
);

create index audio_file_owner_file_key_idx on public.audio_file(owner_user_id, file_key);
create index audio_file_owner_checksum_sha256_idx on public.audio_file(owner_user_id, checksum_sha256);
create index audio_file_owner_checksum_prefix_idx on public.audio_file(owner_user_id, checksum_prefix);
create index audio_file_owner_filename_idx on public.audio_file(owner_user_id, filename);
create index audio_observation_owner_import_run_idx on public.audio_observation(owner_user_id, import_run_id);
create index audio_observation_owner_audio_file_idx on public.audio_observation(owner_user_id, audio_file_id);
create index dj_tag_owner_isrc_idx on public.dj_tag(owner_user_id, isrc);
create index dj_tag_owner_genre_idx on public.dj_tag(owner_user_id, canonical_genre, canonical_subgenre);
create index dj_tag_owner_label_idx on public.dj_tag(owner_user_id, label);
create index dj_tag_owner_artist_title_idx on public.dj_tag(owner_user_id, artist, title);
create index tag_evidence_owner_lookup_idx on public.tag_evidence(owner_user_id, provider, lookup_type, lookup_key);
create index tag_evidence_owner_file_fetched_idx on public.tag_evidence(owner_user_id, audio_file_id, fetched_at desc);
create index quality_check_owner_file_checked_idx on public.quality_check(owner_user_id, audio_file_id, checked_at desc);
create index crate_owner_sort_order_idx on public.crate(owner_user_id, sort_order);
create index crate_track_crate_position_idx on public.crate_track(crate_id, position);
create index saved_view_owner_route_idx on public.saved_view(owner_user_id, route);

create trigger set_import_run_updated_at
before update on public.import_run
for each row execute function public.set_updated_at();

create trigger set_audio_file_updated_at
before update on public.audio_file
for each row execute function public.set_updated_at();

create trigger set_audio_observation_updated_at
before update on public.audio_observation
for each row execute function public.set_updated_at();

create trigger set_dj_tag_updated_at
before update on public.dj_tag
for each row execute function public.set_updated_at();

create trigger set_tag_evidence_updated_at
before update on public.tag_evidence
for each row execute function public.set_updated_at();

create trigger set_quality_check_updated_at
before update on public.quality_check
for each row execute function public.set_updated_at();

create trigger set_crate_updated_at
before update on public.crate
for each row execute function public.set_updated_at();

create trigger set_crate_track_updated_at
before update on public.crate_track
for each row execute function public.set_updated_at();

create trigger set_saved_view_updated_at
before update on public.saved_view
for each row execute function public.set_updated_at();

revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;

grant select on public.import_run to authenticated;
grant select on public.audio_file to authenticated;
grant select on public.audio_observation to authenticated;
grant select on public.tag_evidence to authenticated;
grant select on public.quality_check to authenticated;
grant select, insert, update on public.dj_tag to authenticated;
grant select, insert, update, delete on public.crate to authenticated;
grant select, insert, update, delete on public.crate_track to authenticated;
grant select, insert, update, delete on public.saved_view to authenticated;

grant select, insert, update, delete on public.import_run to service_role;
grant select, insert, update, delete on public.audio_file to service_role;
grant select, insert, update, delete on public.audio_observation to service_role;
grant select, insert, update, delete on public.dj_tag to service_role;
grant select, insert, update, delete on public.tag_evidence to service_role;
grant select, insert, update, delete on public.quality_check to service_role;
grant select, insert, update, delete on public.crate to service_role;
grant select, insert, update, delete on public.crate_track to service_role;
grant select, insert, update, delete on public.saved_view to service_role;

alter table public.import_run enable row level security;
alter table public.audio_file enable row level security;
alter table public.audio_observation enable row level security;
alter table public.dj_tag enable row level security;
alter table public.tag_evidence enable row level security;
alter table public.quality_check enable row level security;
alter table public.crate enable row level security;
alter table public.crate_track enable row level security;
alter table public.saved_view enable row level security;

create policy "authenticated_select_import_run"
  on public.import_run
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_select_audio_file"
  on public.audio_file
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_select_audio_observation"
  on public.audio_observation
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_select_tag_evidence"
  on public.tag_evidence
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_select_quality_check"
  on public.quality_check
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_select_dj_tag"
  on public.dj_tag
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_insert_dj_tag"
  on public.dj_tag
  for insert
  to authenticated
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_update_dj_tag"
  on public.dj_tag
  for update
  to authenticated
  using (owner_user_id = (select auth.uid()))
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_select_crate"
  on public.crate
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_insert_crate"
  on public.crate
  for insert
  to authenticated
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_update_crate"
  on public.crate
  for update
  to authenticated
  using (owner_user_id = (select auth.uid()))
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_delete_crate"
  on public.crate
  for delete
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_select_crate_track"
  on public.crate_track
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_insert_crate_track"
  on public.crate_track
  for insert
  to authenticated
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_update_crate_track"
  on public.crate_track
  for update
  to authenticated
  using (owner_user_id = (select auth.uid()))
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_delete_crate_track"
  on public.crate_track
  for delete
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_select_saved_view"
  on public.saved_view
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_insert_saved_view"
  on public.saved_view
  for insert
  to authenticated
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_update_saved_view"
  on public.saved_view
  for update
  to authenticated
  using (owner_user_id = (select auth.uid()))
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_delete_saved_view"
  on public.saved_view
  for delete
  to authenticated
  using (owner_user_id = (select auth.uid()));

comment on schema public is
'Taghag public app schema. service_role grants are for local/server importer tooling only; frontend code must use publishable authenticated access.';

commit;
