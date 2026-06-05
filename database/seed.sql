begin;

insert into public.dj_tag (owner_user_id, name, tag_type, color_hex, description)
values
  ('00000000-0000-0000-0000-000000000001', 'Peak Time', 'moment', '#d97706', 'Late-night pressure moments'),
  ('00000000-0000-0000-0000-000000000001', 'Warmup', 'moment', '#0f766e', 'Opening-room energy');

insert into public.crate (owner_user_id, name, description)
values
  ('00000000-0000-0000-0000-000000000001', 'Friday Warmup', 'Starter selections for a slower floor'),
  ('00000000-0000-0000-0000-000000000001', '2AM Tools', 'Reliable peak-hour utility tracks');

commit;
