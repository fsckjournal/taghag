Goal:
Add minimum reliable tests for importer, schema, and web basics.

Python tests:
- MP3 tag extraction from fixture or mock boundary.
- Out-of-scope audio reporting.
- Genre normalization.
- Idempotent import receipt generation.
- Missing metadata produces issue codes.
- Postman evidence parsing.

Fixture rule:
- Do not commit real music.
- If binary MP3 fixture is needed, generate tiny synthetic MP3 during test.
- Prefer mocking mutagen/ffprobe boundaries when the behavior under test is importer logic.
- Keep tests fast.

Supabase tests:
- `supabase db reset` applies migrations.
- unauthenticated access is denied.
- authenticated access follows owner policies.
- service role can upsert import tables.
- generated TypeScript types match schema.
- all 9 public app tables have RLS enabled.
- no anon policies exist.
- no forbidden legacy table names exist.

Web tests:
- Library table renders fixture data.
- Empty import state renders.
- Dashboard count cards render.
- Crate ordering component handles fixture data.

Commands:
- `pytest tools/tests`
- `supabase db reset`
- `npm install`
- `npm run typecheck` if configured
- `npm test` if configured
