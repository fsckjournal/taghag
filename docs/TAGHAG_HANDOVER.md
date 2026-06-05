# Taghag Handover

This note is for the next AI agent taking over the Taghag repository with no prior context.

## Project Intent

Taghag is a clean-room, MP3-only, metadata-only private DJ app. The durable plan is in `docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md`. Execution is broken into ordered prompts under `.github/prompts/`, from repo layout through migration, importer, web shell, tests, clean-room audit, verification, and definition of done.

## What Has Been Implemented

Completed work aligns partially with prompts `03`, `04`, `06`, and `07`, but not yet with `01` and `02`.

- Prompt library and master plan are present under `docs/` and `.github/prompts/`.
- A Python importer package exists in `tools/taghag_import/`.
- Implemented importer pieces:
  - MP3 discovery in `tools/taghag_import/discover.py`
  - ID3 tag extraction in `tools/taghag_import/tags.py`
  - local JSONL receipt read/write in `tools/taghag_import/receipt.py`
  - optional Postman evidence parsing in `tools/taghag_import/postman_evidence.py`
  - PostgREST upload client in `tools/taghag_import/db_client.py`
  - CLI entrypoints in `tools/taghag_import/cli.py`
- Extracted clean-room utilities exist:
  - genre normalization via `tools/taghag_import/genre.py`
  - provider evidence parsing via `tools/taghag_import/postman_evidence.py`
- A first React/Vite shell exists in `web/` with a placeholder UI in `web/src/App.tsx`.
- Basic Python tests exist and currently pass:
  - `tools/tests/test_genre.py`
  - `tools/tests/test_postman_evidence.py`
  - `pytest tools/tests -q` currently reports `5 passed`
- Contributor guidance now exists in `AGENTS.md`.

## Current Divergence From The Plan

The highest-risk gap is that prompts `01` and `02` are not complete, and later work was built on top of the wrong schema nouns.

- The repo still uses `database/`, not the preferred `supabase/` layout from prompt `01`.
- The existing migration at `database/migrations/0001_initial_schema.sql` is not the target schema from prompt `02`.
- The migration creates `mp3_track`, which the plan explicitly forbids; it must be `mp3_file`.
- The migration models `dj_tag` as a tag dictionary, not per-file DJ metadata.
- The migration does not create `mp3_observation`.
- The importer currently uploads to `mp3_track`, matching the wrong schema.
- The importer command shape does not yet match prompt `03` (`scan`/`load` exist; `import-batch` with receipt-first local workflow is not complete).
- The web shell is placeholder-only and is not yet wired to generated Supabase database types from prompt `05`.

## Recommended Read Order

1. `AGENT.md`
2. `README.md`
3. `docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md`
4. `.github/prompts/README.md`
5. `.github/prompts/taghag-01-repo-layout.prompt.md`
6. `.github/prompts/taghag-02-first-migration.prompt.md`
7. `.github/prompts/taghag-03-import-cli.prompt.md`

## Immediate Next Step

Do not extend the importer or UI first. The next agent should execute prompts `01` and `02` before building further.

Priority order:

1. Rename `database/` to `supabase/` and update repo docs and references.
2. Replace `0001_initial_schema.sql` with the correct 9-table MP3 metadata schema centered on `mp3_file`.
3. Update the importer code to target `mp3_file`, `mp3_observation`, `dj_tag`, `quality_check`, and `tag_evidence` using the receipt-first flow from prompt `03`.

## Quick Reality Check Commands

```bash
git status --short
pytest tools/tests -q
sed -n '1,220p' database/migrations/0001_initial_schema.sql
sed -n '1,220p' .github/prompts/taghag-01-repo-layout.prompt.md
sed -n '1,260p' .github/prompts/taghag-02-first-migration.prompt.md
```
