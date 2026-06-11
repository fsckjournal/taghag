begin;

create table public.track_cue (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  audio_file_id uuid not null,
  name text,
  time_ms integer not null,
  color text,
  cue_type text not null default 'hot_cue',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint track_cue_audio_file_owner_fk
    foreign key (audio_file_id, owner_user_id)
    references public.audio_file(id, owner_user_id)
    on delete cascade
);

create index track_cue_audio_file_idx on public.track_cue(audio_file_id);

create trigger set_track_cue_updated_at
before update on public.track_cue
for each row execute function public.set_updated_at();

grant select, insert, update, delete on public.track_cue to authenticated;
grant select, insert, update, delete on public.track_cue to service_role;

alter table public.track_cue enable row level security;

create policy "authenticated_select_track_cue"
  on public.track_cue
  for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

create policy "authenticated_insert_track_cue"
  on public.track_cue
  for insert
  to authenticated
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_update_track_cue"
  on public.track_cue
  for update
  to authenticated
  using (owner_user_id = (select auth.uid()))
  with check (owner_user_id = (select auth.uid()));

create policy "authenticated_delete_track_cue"
  on public.track_cue
  for delete
  to authenticated
  using (owner_user_id = (select auth.uid()));

commit;
