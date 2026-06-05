Goal:
Make the project layout predictable for future agents.

Preferred structure:
- `supabase/config.toml`
- `supabase/seed.sql`
- `supabase/migrations/<timestamp>_initial_mp3_metadata_schema.sql`
- `tools/pyproject.toml`
- `tools/taghag_import/`
- `tools/tests/`
- `web/package.json`
- `web/src/`
- `README.md`
- `AGENT.md`

Steps:
1. Run `git status`.
2. Inspect existing `database/` and `supabase/` folders.
3. If `database/` exists and `supabase/` does not, move `database/` to `supabase/`.
4. Update README references from `database/` to `supabase/`.
5. Keep `seed.sql` empty or harmless.
6. Do not seed fake user-owned production data.
7. If seed data is needed for local tests, put it in clearly named test fixtures, not default `seed.sql`.

Acceptance:
- README points to the actual migration folder.
- `AGENT.md` still says SQL changes must be source-controlled migrations.
- `supabase db reset` has a normal Supabase layout to work with.
