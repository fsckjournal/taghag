-- Time-base anchor: make every cue/segment re-zeroable onto one canonical clock
-- (master-FLAC PCM sample 0) without rewriting existing time_ms. Additive-only,
-- idempotent, backward-compatible. See docs/design/2026-06-21-time-base-anchor.md.

-- 1. Rendition geometry on audio_file ---------------------------------------
alter table public.audio_file
  add column if not exists sample_rate_hz integer;
alter table public.audio_file
  add column if not exists encoder_delay_samples integer; -- priming; FLAC=0, AAC~2112/2624, MP3~576+

-- 2. Clock provenance on track_cue and track_segment ------------------------
alter table public.track_cue
  add column if not exists measured_against_file_id uuid references public.audio_file(id);
alter table public.track_cue
  add column if not exists time_base text not null default 'unknown'
    check (time_base in ('master_flac','rendition','external_grid','unknown'));

alter table public.track_segment
  add column if not exists measured_against_file_id uuid references public.audio_file(id);
alter table public.track_segment
  add column if not exists time_base text not null default 'unknown'
    check (time_base in ('master_flac','rendition','external_grid','unknown'));

-- Index the new foreign-key columns (avoid unindexed-FK advisor warnings).
create index if not exists track_cue_measured_against_file_idx
  on public.track_cue(measured_against_file_id);
create index if not exists track_segment_measured_against_file_idx
  on public.track_segment(measured_against_file_id);

-- 3. Reconciled offsets: rendition_time_offset -----------------------------
-- One row per (canonical rendition, source rendition, source_system).
-- canonical_ms = measured_ms - offset_ms.
create table if not exists public.rendition_time_offset (
  id                       uuid primary key default gen_random_uuid(),
  owner_user_id            uuid not null,
  audio_file_id            uuid not null references public.audio_file(id),  -- canonical (master FLAC)
  measured_against_file_id uuid references public.audio_file(id),           -- source rendition; NULL for external grids
  source_system            text not null,
  offset_ms                numeric not null,        -- add to canonical to get measured; subtract to canonicalize
  offset_method            text not null check (offset_method in
                             ('identity','declared_priming','downbeat_anchor','cross_correlation')),
  residual_ms              numeric,                 -- calibration tightness (lower = better)
  confidence               real not null default 0.0,
  computed_at              timestamptz not null default now(),
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  unique (audio_file_id, measured_against_file_id, source_system)
);

-- Index the new foreign-key column not already covered as a leftmost key.
create index if not exists rendition_time_offset_measured_against_file_idx
  on public.rendition_time_offset(measured_against_file_id);
create index if not exists rendition_time_offset_owner_idx
  on public.rendition_time_offset(owner_user_id);

drop trigger if exists set_updated_at_rendition_time_offset on public.rendition_time_offset;
create trigger set_updated_at_rendition_time_offset
before update on public.rendition_time_offset
for each row execute function public.set_updated_at();

-- RLS: mirror the exact owner-scoped policies of track_cue / track_segment.
-- No DROP POLICY (additive-only): guard each CREATE with pg_policies existence.
alter table public.rendition_time_offset enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies
    where schemaname = 'public' and tablename = 'rendition_time_offset'
      and policyname = 'authenticated_select_rendition_time_offset') then
    create policy "authenticated_select_rendition_time_offset"
      on public.rendition_time_offset for select to authenticated
      using (owner_user_id = (select auth.uid()));
  end if;

  if not exists (select 1 from pg_policies
    where schemaname = 'public' and tablename = 'rendition_time_offset'
      and policyname = 'authenticated_insert_rendition_time_offset') then
    create policy "authenticated_insert_rendition_time_offset"
      on public.rendition_time_offset for insert to authenticated
      with check (owner_user_id = (select auth.uid()));
  end if;

  if not exists (select 1 from pg_policies
    where schemaname = 'public' and tablename = 'rendition_time_offset'
      and policyname = 'authenticated_update_rendition_time_offset') then
    create policy "authenticated_update_rendition_time_offset"
      on public.rendition_time_offset for update to authenticated
      using (owner_user_id = (select auth.uid()))
      with check (owner_user_id = (select auth.uid()));
  end if;

  if not exists (select 1 from pg_policies
    where schemaname = 'public' and tablename = 'rendition_time_offset'
      and policyname = 'authenticated_delete_rendition_time_offset') then
    create policy "authenticated_delete_rendition_time_offset"
      on public.rendition_time_offset for delete to authenticated
      using (owner_user_id = (select auth.uid()));
  end if;
end
$$;

grant select, insert, update, delete on public.rendition_time_offset to authenticated;
grant select, insert, update, delete on public.rendition_time_offset to service_role;

-- 4. Canonical views (consumers read these, never raw time_ms) -------------
-- security_invoker so the views respect each caller's RLS on the base tables.
create or replace view public.track_cue_canonical
  with (security_invoker = true) as
select c.*,
  case
    when c.time_base = 'master_flac' then c.time_ms::numeric
    else c.time_ms - coalesce(o.offset_ms, 0)
  end as canonical_time_ms,
  (c.time_base in ('rendition','external_grid') and o.offset_ms is null) as offset_missing
from public.track_cue c
left join public.rendition_time_offset o
  on  o.audio_file_id = c.audio_file_id
  and o.measured_against_file_id is not distinct from c.measured_against_file_id
  and o.source_system = c.source_system;

create or replace view public.track_segment_canonical
  with (security_invoker = true) as
select s.*,
  case
    when s.time_base = 'master_flac' then s.ms_start::numeric
    else s.ms_start - coalesce(o.offset_ms, 0)
  end as canonical_ms_start,
  case
    when s.time_base = 'master_flac' then s.ms_end::numeric
    else s.ms_end - coalesce(o.offset_ms, 0)
  end as canonical_ms_end,
  (s.time_base in ('rendition','external_grid') and o.offset_ms is null) as offset_missing
from public.track_segment s
left join public.rendition_time_offset o
  on  o.audio_file_id = s.audio_file_id
  and o.measured_against_file_id is not distinct from s.measured_against_file_id
  and o.source_system = s.source_system;

grant select on public.track_cue_canonical to authenticated;
grant select on public.track_cue_canonical to service_role;
grant select on public.track_segment_canonical to authenticated;
grant select on public.track_segment_canonical to service_role;
