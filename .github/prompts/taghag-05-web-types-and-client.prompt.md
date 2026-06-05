Goal:
Prepare web app to use generated Supabase database types safely.

Files:
- `web/src/lib/database.types.ts`
- `web/src/lib/supabase.ts`
- `web/package.json`
- `.env.example`
- `README.md`

Type generation:
- Verify CLI command with `supabase gen types typescript --help`.
- Local command is expected to be similar to:
  `npx supabase gen types typescript --local > web/src/lib/database.types.ts`
- Add script in `web/package.json`:
  `"db:types": "supabase gen types typescript --local > src/lib/database.types.ts"`
- If using npm local dependency:
  `"db:types": "npx supabase gen types typescript --local > src/lib/database.types.ts"`

Supabase client:
- Use `@supabase/supabase-js`.
- Import `Database` from `./database.types`.
- Use `VITE_SUPABASE_URL`.
- Use `VITE_SUPABASE_PUBLISHABLE_KEY`.
- Throw a clear error if env vars are missing.
- Do not use service role or secret keys in `web/`.

`.env.example`:
- `VITE_SUPABASE_URL=`
- `VITE_SUPABASE_PUBLISHABLE_KEY=`
- `TAGHAG_SUPABASE_URL=`
- `TAGHAG_SUPABASE_SERVICE_ROLE_KEY=`
- `TAGHAG_OWNER_USER_ID=`

README note:
- Web app uses publishable key and authenticated browser access.
- Import tools use service role locally/server-side.
- Service role must never be committed or placed under `web/`.
