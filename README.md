# Taghag

Taghag is a clean-room, MP3-only private DJ metadata app. It keeps MP3 files on local disks and stores only metadata, tagging decisions, crate organization, and import receipts in the database.

## What Taghag is

Taghag is a private control surface for DJs who want to scan local MP3 libraries, normalize metadata, review tag evidence, and organize tracks into crates and saved views.

## What it refuses to inherit

This repository does not inherit legacy schema design, code imports, or mixed-format assumptions from the old tagslut project. Taghag is a fresh schema and app boundary built specifically for MP3-first metadata workflows.

## MP3-only v1 scope

Version 1 accepts `.mp3` files only. FLAC, AAC, M4A, ALAC, and other non-MP3 formats are treated as out of scope and are reported as skipped during discovery.

## Metadata-only database model

The database stores import runs, MP3 file metadata, DJ tags, tag evidence, quality checks, crates, crate membership, and saved views. It does not store binary audio assets.

## Local files remain local

Taghag never uploads or deletes local MP3 files. Import receipts reference local paths for operator use, while the database stores metadata only.

## Server-only key never goes to frontend

The importer reads server-side upload credentials from environment variables only. Frontend code must use frontend-safe variables only and must never embed a server-only key.

## Source-controlled migrations

All SQL changes belong in source-controlled migrations under [supabase/migrations](/Users/g/Projects/taghag/supabase/migrations).

## Supabase setup assumptions

Taghag is Supabase-backed metadata software. It is not a SQLite app unless a future task explicitly changes that direction. Local MP3 files remain local, while Supabase stores metadata, tags, crates, and import receipts.

Docker is required only when running the local Supabase CLI stack. In particular, verification with `supabase db reset` expects Docker because it starts and resets a local Supabase/Postgres environment.

To avoid Docker during early development, use a free hosted Supabase dev project. Hosted Supabase has a free tier, and Taghag's metadata-only workload should fit that path initially. Apply the SQL files in [supabase/migrations](/Users/g/Projects/taghag/supabase/migrations) to the hosted project, then configure the local env values from [.env.example](/Users/g/Projects/taghag/.env.example). Do not put service-role keys in frontend env vars.

## Active docs

Use these files as the active project docs for future agent sessions:

- [README.md](/Users/g/Projects/taghag/README.md)
- [AGENT.md](/Users/g/Projects/taghag/AGENT.md)
- [docs/TAGHAG_HANDOVER.md](/Users/g/Projects/taghag/docs/TAGHAG_HANDOVER.md)
- [docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md](/Users/g/Projects/taghag/docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md)
- [.github/prompts/README.md](/Users/g/Projects/taghag/.github/prompts/README.md)

## Prompt library

Reusable project prompts live under [.github/prompts](/Users/g/Projects/taghag/.github/prompts).

Prompt filename template:
- `taghag-<order>-<scope>.prompt.md`

Example names:
- `taghag-00-master-implementation-plan.prompt.md`
- `taghag-03-import-cli.prompt.md`
- `taghag-09-verification-checklist.prompt.md`

## Initial developer setup

1. Create a Python virtual environment for the importer and install [tools/pyproject.toml](/Users/g/Projects/taghag/tools/pyproject.toml).
2. Copy [.env.example](/Users/g/Projects/taghag/.env.example) to a local env file and fill in server-side values outside the frontend.
3. Apply [supabase/migrations](/Users/g/Projects/taghag/supabase/migrations) to either a local Supabase CLI project or a free hosted Supabase dev project.
4. Install the frontend dependencies in [web/package.json](/Users/g/Projects/taghag/web/package.json).

Example:

```bash
cd tools && python3 -m venv .venv && source .venv/bin/activate && pip install -e .
pytest tests
cd ../web && npm install && npm run build
```

## First import flow

Scan a local MP3 tree, write a JSONL receipt, and skip upload:

```bash
cd tools
taghag-import import-batch --root /path/to/mp3-library --run-name first-import --no-upload
```

Upload uses the server-side Taghag env vars from [.env.example](/Users/g/Projects/taghag/.env.example):

```bash
taghag-import import-batch --root /path/to/mp3-library --run-name first-import
```

## Verification

Run `supabase db reset` only when using the local Supabase CLI stack with Docker available. For a hosted dev project, verify by applying the source-controlled migrations to that project and running the validation SQL from the implementation plan against the hosted database.

```bash
python tools/audit_cleanroom.py
pytest tools/tests -q
supabase db reset
cd web && npm run build
```
