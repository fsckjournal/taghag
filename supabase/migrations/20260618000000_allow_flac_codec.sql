begin;

-- Drop the strict MP3 constraint
alter table public.audio_file drop constraint if exists audio_file_codec_check;

-- Change default codec to flac
alter table public.audio_file alter column codec set default 'flac';

-- Enforce allowing flac and mp3
alter table public.audio_file add constraint audio_file_codec_check check (codec in ('flac', 'mp3'));

commit;
