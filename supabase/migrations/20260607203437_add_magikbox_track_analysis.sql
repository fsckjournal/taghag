begin;

create table public.track_analysis (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  mp3_file_id uuid not null,
  schema_name text not null,
  model_profile text,
  models_json jsonb not null default '{}'::jsonb,
  source_artifact_sha256 text not null,
  source_path text,
  genres_json jsonb not null default '[]'::jsonb,
  happy numeric not null,
  aggressive numeric not null,
  relaxed numeric not null,
  party numeric not null,
  danceability numeric not null,
  raw_json jsonb not null default '{}'::jsonb,
  computed_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint track_analysis_mp3_file_owner_fk
    foreign key (mp3_file_id, owner_user_id)
    references public.mp3_file(id, owner_user_id)
    on delete cascade,
  constraint track_analysis_attribute_range_check
    check (
      happy between 0 and 1
      and aggressive between 0 and 1
      and relaxed between 0 and 1
      and party between 0 and 1
      and danceability between 0 and 1
    ),
  unique (owner_user_id, mp3_file_id, schema_name, source_artifact_sha256)
);

create index track_analysis_owner_file_computed_idx
  on public.track_analysis(owner_user_id, mp3_file_id, computed_at desc);

create trigger set_track_analysis_updated_at
before update on public.track_analysis
for each row execute function public.set_updated_at();

revoke all on public.track_analysis from anon;
grant select on public.track_analysis to authenticated;
grant select, insert, update, delete on public.track_analysis to service_role;

alter table public.track_analysis enable row level security;

create policy "authenticated_select_track_analysis"
  on public.track_analysis
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

comment on table public.track_analysis is
'Metadata-only Essentia/Magikbox analysis for local MP3 files. Audio content remains on local disks.';

commit;
