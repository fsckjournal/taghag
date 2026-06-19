-- Store deterministic Apple Music Understanding provenance and derived scalars.

create table if not exists public.apple_analysis_runs (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  audio_file_id uuid not null,
  source_artifact_sha256 text not null,
  source_path text,
  analyzer text not null default 'cuecifer-analyzer',
  analyzer_version text,
  raw_result_json jsonb not null,
  computed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint apple_analysis_runs_audio_file_fk
    foreign key (audio_file_id, owner_user_id)
    references public.audio_file(id, owner_user_id)
    on delete cascade,
  constraint apple_analysis_runs_unique_source
    unique (owner_user_id, audio_file_id, source_artifact_sha256)
);

alter table public.apple_track_analysis
  add column if not exists analysis_run_id uuid references public.apple_analysis_runs(id) on delete set null,
  add column if not exists loudness_momentary jsonb,
  add column if not exists loudness_short_term jsonb,
  add column if not exists loudness_integrated numeric,
  add column if not exists loudness_peak numeric;

create table if not exists public.apple_derived_features (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  audio_file_id uuid not null,
  analysis_run_id uuid references public.apple_analysis_runs(id) on delete set null,
  source_artifact_sha256 text not null,
  apple_bpm numeric,
  apple_key text,
  key_stable boolean,
  key_change_count integer,
  beat_count integer,
  bar_count integer,
  section_count integer,
  segment_count integer,
  phrase_count integer,
  pace_mean numeric,
  pace_median numeric,
  pace_volatility numeric,
  pace_min numeric,
  pace_max numeric,
  intro_length_ms integer,
  outro_length_ms integer,
  has_vocal_activity boolean,
  has_drum_activity boolean,
  vocal_intensity_mean numeric,
  drum_intensity_mean numeric,
  bass_intensity_mean numeric,
  loudness_integrated numeric,
  loudness_peak numeric,
  loudness_range_db numeric,
  loudness_mean numeric,
  loudness_std numeric,
  bpm_agreement_score numeric,
  computed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint apple_derived_features_audio_file_fk
    foreign key (audio_file_id, owner_user_id)
    references public.audio_file(id, owner_user_id)
    on delete cascade,
  constraint apple_derived_features_unique_source
    unique (owner_user_id, audio_file_id, source_artifact_sha256)
);

create index if not exists apple_analysis_runs_owner_audio_idx
  on public.apple_analysis_runs(owner_user_id, audio_file_id);

create index if not exists apple_derived_features_owner_audio_idx
  on public.apple_derived_features(owner_user_id, audio_file_id);

drop trigger if exists set_updated_at_apple_analysis_runs on public.apple_analysis_runs;
create trigger set_updated_at_apple_analysis_runs
before update on public.apple_analysis_runs
for each row execute function public.set_updated_at();

drop trigger if exists set_updated_at_apple_derived_features on public.apple_derived_features;
create trigger set_updated_at_apple_derived_features
before update on public.apple_derived_features
for each row execute function public.set_updated_at();

alter table public.apple_analysis_runs enable row level security;
alter table public.apple_derived_features enable row level security;

drop policy if exists "apple_analysis_runs_select_own" on public.apple_analysis_runs;
create policy "apple_analysis_runs_select_own"
on public.apple_analysis_runs for select
to authenticated
using (owner_user_id = auth.uid());

drop policy if exists "apple_derived_features_select_own" on public.apple_derived_features;
create policy "apple_derived_features_select_own"
on public.apple_derived_features for select
to authenticated
using (owner_user_id = auth.uid());

grant select on public.apple_analysis_runs to authenticated;
grant select on public.apple_derived_features to authenticated;
grant select, insert, update, delete on public.apple_analysis_runs to service_role;
grant select, insert, update, delete on public.apple_derived_features to service_role;
