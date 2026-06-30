-- Fix security definer view: recreate sonic_analysis with security_invoker=true
-- so RLS on track_embedding and track_curation applies to the querying user.
create or replace view public.sonic_analysis
  with (security_invoker = true)
as
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

revoke all on public.sonic_analysis from public;
grant select on public.sonic_analysis to authenticated;
grant select on public.sonic_analysis to service_role;
