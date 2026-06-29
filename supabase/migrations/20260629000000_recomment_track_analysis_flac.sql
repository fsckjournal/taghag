-- Fix the stale comment on public.track_analysis.
--
-- The original comment ("Essentia/Magikbox analysis for local MP3 files") is wrong
-- on three counts: the project is FLAC-only (not MP3); "Magikbox" is a dead name
-- (now "similarity"); and the table is the live store the similarity engine reads
-- sonic7_v1 embeddings from. This is a comment-only change — no schema/data effect.
-- See docs/architecture/slut_hag_split.md.

comment on table public.track_analysis is
  'Metadata-only sonic analysis and sonic7_v1 embeddings for local FLAC masters. '
  'Read by the similarity engine. Audio content remains on local disk.';
