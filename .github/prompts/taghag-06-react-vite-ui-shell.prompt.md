Goal:
Create a simple data-first private app shell.

Screens:
1. Import Runs
2. Library Table
3. Track Detail
4. Crates
5. Dashboard

Rules:
- No schema creation from UI.
- No generated SQL pasted from UI tools.
- No service role in browser.
- All data queries use typed Supabase client.
- Empty states must be clean.
- Route-level placeholders are fine where data is not ready.
- Keep filters URL-backed where practical.

Routes:
- `/` imports dashboard by default or redirects to `/dashboard`.
- `/imports` shows `import_run` list.
- `/library` shows library table.
- `/tracks/:id` shows track detail.
- `/crates` shows crates.
- `/dashboard` shows counts.

Library Table columns:
- `filename` from `mp3_file`
- `artist` from `dj_tag`
- `title` from `dj_tag`
- `label` from `dj_tag`
- `bpm` from `dj_tag`
- `musical_key` from `dj_tag`
- `canonical_genre` from `dj_tag`
- `canonical_subgenre` from `dj_tag`
- quality status from latest `quality_check`
- evidence status from `tag_evidence` aggregate

Dashboard counts:
- total MP3s
- missing artist/title
- missing BPM/key
- missing genre/subgenre
- missing label
- duplicate checksum candidates
- provider evidence statuses

Filters:
- `import_run`
- genre
- bpm range
- key
- quality status
- provider status

Implementation approach:
- Use React Router or a tiny local route state if already configured.
- Use `URLSearchParams` for filters.
- Keep components small.
- Do not over-design the first shell.
- Prefer truthful empty states over fake demo data.

Suggested files:
- `web/src/lib/supabase.ts`
- `web/src/lib/database.types.ts`
- `web/src/lib/queries.ts`
- `web/src/App.tsx`
- `web/src/components/AppShell.tsx`
- `web/src/components/LibraryTable.tsx`
- `web/src/components/DashboardCards.tsx`
- `web/src/routes/ImportRuns.tsx`
- `web/src/routes/Library.tsx`
- `web/src/routes/TrackDetail.tsx`
- `web/src/routes/Crates.tsx`
- `web/src/routes/Dashboard.tsx`
