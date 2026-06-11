begin;

create schema if not exists extensions;
create extension if not exists vector with schema extensions;


create table if not exists public.track_embedding (
    id uuid primary key default gen_random_uuid(),
    owner_user_id uuid not null references auth.users(id) on delete cascade,
    audio_file_id uuid not null,
    vector_schema text not null,
    embedding extensions.vector(7) not null,
    producer_vibes_json jsonb not null default '[]'::jsonb,
    dynamic_evolution boolean not null default false,
    evolution_delta numeric,
    source_analysis_id uuid,
    computed_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint track_embedding_audio_file_owner_user_id_fkey
        foreign key (audio_file_id, owner_user_id)
        references public.audio_file(id, owner_user_id)
        on delete cascade,
    unique (owner_user_id, audio_file_id, vector_schema)
);

comment on column public.track_embedding.embedding is '[energy_norm, bpm_norm, danceability, party, happy, aggressive, relaxed]';

create index if not exists track_embedding_cosine_idx
    on public.track_embedding
    using hnsw (embedding extensions.vector_cosine_ops);

create table if not exists public.track_curation (
    id uuid primary key default gen_random_uuid(),
    owner_user_id uuid not null references auth.users(id) on delete cascade,
    audio_file_id uuid not null,
    pinned boolean not null default false,
    human_vibes_json jsonb not null default '[]'::jsonb,
    note text,
    corrected_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint track_curation_audio_file_owner_user_id_fkey
        foreign key (audio_file_id, owner_user_id)
        references public.audio_file(id, owner_user_id)
        on delete cascade,
    unique (owner_user_id, audio_file_id)
);

alter table public.track_embedding enable row level security;
alter table public.track_curation enable row level security;

revoke all privileges on table public.track_embedding from anon;
revoke all privileges on table public.track_curation from anon;

grant select on public.track_embedding to authenticated;
grant select, insert, update on public.track_curation to authenticated;

grant select, insert, update, delete on public.track_embedding to service_role;
grant select, insert, update, delete on public.track_curation to service_role;

drop policy if exists track_embedding_select_own on public.track_embedding;
create policy track_embedding_select_own
on public.track_embedding
for select
to authenticated
using (owner_user_id = (select auth.uid()));

drop policy if exists track_curation_select_own on public.track_curation;
drop policy if exists track_curation_insert_own on public.track_curation;
drop policy if exists track_curation_update_own on public.track_curation;

create policy track_curation_select_own
on public.track_curation
for select
to authenticated
using (owner_user_id = (select auth.uid()));

create policy track_curation_insert_own
on public.track_curation
for insert
to authenticated
with check (owner_user_id = (select auth.uid()));

create policy track_curation_update_own
on public.track_curation
for update
to authenticated
using (owner_user_id = (select auth.uid()))
with check (owner_user_id = (select auth.uid()));

drop trigger if exists set_updated_at on public.track_embedding;
create trigger set_updated_at
before update on public.track_embedding
for each row
execute function public.set_updated_at();

drop trigger if exists set_updated_at on public.track_curation;
create trigger set_updated_at
before update on public.track_curation
for each row
execute function public.set_updated_at();

commit;
