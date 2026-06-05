# Taghag Handover

This is the short continuation note for the next agent working on Taghag. It
connects the two repositories, the master implementation plan, and the ordered
prompt library.

## Repositories

Primary implementation repo:

- `/Users/g/Projects/taghag`
- GitHub: `tagslut-org/taghag`
- Purpose: clean-room, MP3-only, metadata-only private DJ app.

Reference/source-context repo:

- `/Users/g/Projects/tagslut`
- GitHub: `tagslut-org/tagslut`
- Purpose in this work: historical context and source of a few proven standalone
  utilities, not an architecture to copy.

The tagslut-side context matters because it explains the failure modes Taghag is
designed to avoid: mixed-format drift, schema overreach, unsafe identity merges,
and metadata guessing. Taghag should inherit the lessons, not the schema.

## Source Of Truth

Read these in order before implementing:

1. `AGENT.md`
2. `README.md`
3. `docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md`
4. `.github/prompts/README.md`
5. The specific numbered prompt for the task you are executing

The master plan is the durable implementation reference. The prompts are
task-sized execution packets derived from that plan. If a prompt and the master
plan disagree, prefer the master plan and update the prompt in the same patch.

## Prompt Library

The prompt sequence is stored in `.github/prompts/`:

- `taghag-00-master-implementation-plan.prompt.md`
- `taghag-01-repo-layout.prompt.md`
- `taghag-02-first-migration.prompt.md`
- `taghag-03-import-cli.prompt.md`
- `taghag-04-postman-evidence.prompt.md`
- `taghag-05-web-types-and-client.prompt.md`
- `taghag-06-react-vite-ui-shell.prompt.md`
- `taghag-07-tests.prompt.md`
- `taghag-08-clean-room-audit.prompt.md`
- `taghag-09-verification-checklist.prompt.md`
- `taghag-10-definition-of-done.prompt.md`

Use the prompts in order unless the operator explicitly redirects the work. Each
implementation phase should leave the repo in a tested, committed, pushed state.

## Current Architectural Decision

Taghag v1 is MP3-only.

The database stores metadata about local MP3 files. It must not store audio
files, cloud object paths, Supabase Storage objects, or upload locations.

`mp3_file` is the primary asset table. ISRC is useful evidence for lookup and
duplicate detection, but it is not identity and must not automatically merge
rows in v1.

## Clean-Room Boundary

Allowed from tagslut:

- Extracted genre normalization behavior.
- Extracted Postman `[Tag Evidence JSON]` parser behavior.
- The DJ-facing tag contract: label, canonical genre/subgenre, release context,
  evidence status, and quality status.
- The operational rule that uncertainty should be skipped/reported rather than
  guessed.
- The rule that MP3 comments are reserved for Mixed in Key Energy.

Forbidden in active Taghag code and migrations:

- `from tagslut`
- `import tagslut`
- `asset_file`
- `track_identity`
- `asset_link`
- `preferred_asset`
- `move_plan`
- `move_execution`
- `provenance_event`
- `AAC_LIBRARY`
- `M4A derivative`
- `AAC-first`

These terms may appear only in docs sections explicitly marked as historical or
forbidden, and the clean-room audit should become the authoritative gate.

## Known State To Fix First

The current repo may still contain an early migration under
`database/migrations/0001_initial_schema.sql`. That migration is not the target
schema if it creates `mp3_track`, models `dj_tag` as a tag dictionary, omits
`mp3_observation`, or grants authenticated broad CRUD on every table.

The next agent should treat this as the first implementation priority:

1. Run `taghag-01-repo-layout.prompt.md`.
2. Rename `database/` to `supabase/` unless there is a concrete tool reason not
   to.
3. Update README and prompt references to the chosen migration path.
4. Run `taghag-02-first-migration.prompt.md`.
5. Replace the bad initial migration with the 9-table MP3 metadata schema.

Because this project is still early, prefer replacing the incorrect initial
migration over stacking a corrective migration on top of wrong nouns.

## Immediate Next Steps

Start in `/Users/g/Projects/taghag`:

```bash
git status --short
sed -n '1,220p' AGENT.md
sed -n '1,220p' README.md
sed -n '1,220p' docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md
sed -n '1,220p' .github/prompts/taghag-01-repo-layout.prompt.md
sed -n '1,260p' .github/prompts/taghag-02-first-migration.prompt.md
```

Then execute from the repo root:

```bash
supabase --version
supabase db reset
pytest tools/tests
```

If already running from `tools/`, use:

```bash
pytest tests
```

If `supabase db reset` fails because the current schema is wrong, that is
expected until the layout and migration prompts are implemented. Do not build
the importer or web UI on top of the wrong migration.

## Verification Principles

Use `python tools/audit_cleanroom.py` as the final forbidden-term gate once it
exists. Raw `rg` checks are useful diagnostics, but they will find forbidden
terms in prompt warning text.

After the migration phase, verify:

- Exactly the 9 required app tables exist.
- `mp3_file` exists.
- `mp3_track` does not exist.
- RLS is enabled on every public app table.
- No anon policies exist.
- Grants are explicit.
- No storage/upload path concepts exist.
- ISRC is not unique.

After importer work, verify:

- Same batch does not duplicate `mp3_file`.
- Re-running a batch creates new `mp3_observation` rows.
- Out-of-scope audio files are counted and reported.
- Missing metadata creates quality issue codes.
- Receipt JSONL exists even if Supabase upload fails.
- Optional Postman evidence never blocks MP3 import.

After web work, verify:

- The web app imports generated Supabase `Database` types.
- No service-role or secret key appears under `web/`.
- Empty states render cleanly.
- UI code does not create or mutate schema.

## Communication

There is a Codex on the tagslut side that can answer context questions through
the operator. Use that path for intent questions like:

- Why is ISRC not identity?
- Which tagslut utility was extracted and why?
- What does the Postman evidence marker mean?
- Which legacy schema concepts must stay out of Taghag?

Do not guess across the boundary. Ask, then continue with the clean-room rule:
Taghag gets the lesson, not the old system.
