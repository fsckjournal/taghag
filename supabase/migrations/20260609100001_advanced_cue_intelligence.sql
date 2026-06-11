begin;

-- Upgrade existing track_cue table
alter table public.track_cue
add column cue_family text, -- intro, buildup, drop, breakdown, outro, etc.
add column cue_kind text, -- memory, hot, loop, predicted
add column beat_time numeric(10,3),
add column source_system text not null default 'human',
add column confidence real not null default 1.0;

-- Create segment table
create table public.track_segment (
    id uuid primary key default gen_random_uuid(),
    audio_file_id uuid not null,
    owner_user_id uuid not null,
    role text not null, -- intro, rise, peak, breakdown, outro, etc.
    ms_start integer not null,
    ms_end integer not null,
    beat_start integer,
    beat_end integer,
    control_vec extensions.vector(7),
    source_system text not null default 'model',
    confidence real not null default 1.0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint track_segment_audio_file_fk
        foreign key (audio_file_id, owner_user_id)
        references public.audio_file(id, owner_user_id)
        on delete cascade
);

create index track_segment_audio_file_idx on public.track_segment(audio_file_id);
create index track_segment_control_vec_idx on public.track_segment using hnsw (control_vec extensions.vector_cosine_ops);

create trigger set_track_segment_updated_at
before update on public.track_segment
for each row execute function public.set_updated_at();

-- Create transition edge table
create table public.transition_edge (
    from_segment_id uuid not null references public.track_segment(id) on delete cascade,
    to_segment_id uuid not null references public.track_segment(id) on delete cascade,
    owner_user_id uuid not null references auth.users(id) on delete cascade,
    success_count integer not null default 0,
    skip_count integer not null default 0,
    pin_bias real not null default 0,
    note_blob jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (from_segment_id, to_segment_id)
);

create trigger set_transition_edge_updated_at
before update on public.transition_edge
for each row execute function public.set_updated_at();

-- RLS for track_segment
alter table public.track_segment enable row level security;

create policy "authenticated_select_track_segment"
  on public.track_segment for select to authenticated using (owner_user_id = (select auth.uid()));

create policy "authenticated_insert_track_segment"
  on public.track_segment for insert to authenticated with check (owner_user_id = (select auth.uid()));

create policy "authenticated_update_track_segment"
  on public.track_segment for update to authenticated using (owner_user_id = (select auth.uid())) with check (owner_user_id = (select auth.uid()));

create policy "authenticated_delete_track_segment"
  on public.track_segment for delete to authenticated using (owner_user_id = (select auth.uid()));

grant select, insert, update, delete on public.track_segment to authenticated;
grant select, insert, update, delete on public.track_segment to service_role;

-- RLS for transition_edge
alter table public.transition_edge enable row level security;

create policy "authenticated_select_transition_edge"
  on public.transition_edge for select to authenticated using (owner_user_id = (select auth.uid()));

create policy "authenticated_insert_transition_edge"
  on public.transition_edge for insert to authenticated with check (owner_user_id = (select auth.uid()));

create policy "authenticated_update_transition_edge"
  on public.transition_edge for update to authenticated using (owner_user_id = (select auth.uid())) with check (owner_user_id = (select auth.uid()));

create policy "authenticated_delete_transition_edge"
  on public.transition_edge for delete to authenticated using (owner_user_id = (select auth.uid()));

grant select, insert, update, delete on public.transition_edge to authenticated;
grant select, insert, update, delete on public.transition_edge to service_role;

commit;
