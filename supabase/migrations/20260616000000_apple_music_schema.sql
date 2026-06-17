begin;

create table public.apple_track_analysis (
    id uuid primary key default gen_random_uuid(),
    owner_user_id uuid not null references auth.users(id) on delete cascade,
    audio_file_id uuid not null,
    source_artifact_sha256 text not null,
    global_bpm numeric,
    key_mode text,
    key_tonic text,
    pace_curve jsonb,
    drum_activity jsonb,
    bass_activity jsonb,
    vocal_activity jsonb,
    computed_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint apple_track_analysis_audio_file_owner_fk
        foreign key (audio_file_id, owner_user_id)
        references public.audio_file(id, owner_user_id)
        on delete cascade,
    unique (owner_user_id, audio_file_id, source_artifact_sha256)
);

create index apple_track_analysis_owner_file_idx
  on public.apple_track_analysis(owner_user_id, audio_file_id, computed_at desc);

create trigger set_apple_track_analysis_updated_at
before update on public.apple_track_analysis
for each row execute function public.set_updated_at();

revoke all on public.apple_track_analysis from anon;
grant select on public.apple_track_analysis to authenticated;
grant select, insert, update, delete on public.apple_track_analysis to service_role;

alter table public.apple_track_analysis enable row level security;

create policy "authenticated_select_apple_track_analysis"
  on public.apple_track_analysis
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

comment on table public.apple_track_analysis is
'Metadata from Apple Music Understanding framework (WWDC26).';

commit;
