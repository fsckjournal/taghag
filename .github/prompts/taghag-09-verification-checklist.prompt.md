Run from `/Users/g/Projects/taghag`.

Repository:
- `git status --short`
- `rg "from tagslut|import tagslut" .`
- `rg "asset_file|track_identity|asset_link|preferred_asset|move_plan|move_execution|provenance_event|AAC_LIBRARY|M4A derivative|AAC-first" .`

Supabase:
- `supabase --version`
- `supabase db reset`
- `supabase gen types typescript --local > web/src/lib/database.types.ts`
- Confirm all 9 tables exist.
- Confirm RLS enabled on all 9 tables.
- Confirm no anon policies.
- Confirm explicit grants.
- Confirm no storage/upload schema concepts.

Python:
- `cd tools`
- `pytest tests`

Web:
- `cd web`
- `npm install`
- `npm run typecheck` if configured
- `npm run test` if configured
- `npm run dev` starts cleanly

Importer:
- Run dry-run on a synthetic fixture folder.
- Confirm only `.mp3` files imported.
- Confirm `.flac`/`.m4a`/`.aac`/`.wav`/`.aiff` counted as out of scope.
- Confirm receipt exists before upload.
- Confirm repeated import does not duplicate `mp3_file`.
- Confirm repeated import creates another `mp3_observation`.

Evidence:
- Import evidence log with matched, no_match, ambiguous, error, malformed lines.
- Confirm evidence import never blocks MP3 import.
- Confirm ambiguous evidence is visible.
- Confirm `raw_marker_json` preserved.
- Confirm no row merge happens because of ISRC.

Security:
- Confirm `web/` contains no service role or secret key strings.
- Confirm `.env.example` separates `VITE` publishable vars from local importer service vars.
- Confirm authenticated policies are owner-scoped.
- Confirm service role is only documented for local/server importer.
