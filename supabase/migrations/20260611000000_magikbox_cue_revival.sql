-- supabase/migrations/20260611000000_magikbox_cue_revival.sql
begin;

-- Enable the pgvector extension in the extensions schema (should already be done, but keeping safe)
create schema if not exists extensions;
create extension if not exists vector with schema extensions;

-- Create unified sonic_analysis view combining embeddings and human curation
create or replace view public.sonic_analysis as
select 
  e.audio_file_id,
  e.owner_user_id,
  e.embedding as sonic_vector,
  e.producer_vibes_json as producer_vibes,
  e.dynamic_evolution,
  e.evolution_delta,
  coalesce(c.pinned, false) as pinned,
  coalesce(c.human_vibes_json, '[]'::jsonb) as human_vibes,
  c.note,
  e.computed_at,
  e.created_at,
  e.updated_at
from public.track_embedding e
left join public.track_curation c 
  on e.audio_file_id = c.audio_file_id 
  and e.owner_user_id = c.owner_user_id;

-- Revoke all on the view from public, grant select to authenticated and full access to service_role
revoke all on public.sonic_analysis from public;
grant select on public.sonic_analysis to authenticated;
grant select on public.sonic_analysis to service_role;

commit;
