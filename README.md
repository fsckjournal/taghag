# Taghag

Taghag is a clean-room, MP3-only private DJ metadata app. It keeps MP3 files on local disks and stores only metadata, tagging decisions, crate organization, and import receipts in the database.

## What Taghag is

Taghag is a private control surface for DJs who want to scan local MP3 libraries, normalize metadata, review tag evidence, and organize tracks into crates and saved views.

## What it refuses to inherit

This repository does not inherit legacy schema design, code imports, or mixed-format assumptions from the old tagslut project. Taghag is a fresh schema and app boundary built specifically for MP3-first metadata workflows.

## MP3-only v1 scope

Version 1 accepts `.mp3` files only. FLAC, AAC, M4A, ALAC, and other non-MP3 formats are treated as out of scope and are reported as skipped during discovery.

## Metadata-only database model

The database stores import runs, MP3 track metadata, DJ tags, tag evidence, quality checks, crates, crate membership, and saved views. It does not store binary audio assets.

## Local files remain local

Taghag never uploads or deletes local MP3 files. Import receipts reference local paths for operator use, while the database stores metadata only.

## Server-only key never goes to frontend

The importer reads server-side upload credentials from environment variables only. Frontend code must use frontend-safe variables only and must never embed a server-only key.

## Source-controlled migrations

All SQL changes belong in source-controlled migrations under [database/migrations](/Users/g/Projects/taghag/database/migrations).

## Initial developer setup

1. Create a Python virtual environment for the importer and install [tools/pyproject.toml](/Users/g/Projects/taghag/tools/pyproject.toml).
2. Copy [.env.example](/Users/g/Projects/taghag/.env.example) to a local env file and fill in server-side values outside the frontend.
3. Apply [database/migrations/0001_initial_schema.sql](/Users/g/Projects/taghag/database/migrations/0001_initial_schema.sql) to your Postgres or Supabase-backed project.
4. Install the frontend dependencies in [web/package.json](/Users/g/Projects/taghag/web/package.json).

Example:

```bash
cd tools && python3 -m venv .venv && source .venv/bin/activate && pip install -e .
cd ../web && npm install
```

## First import flow

1. Scan a local MP3 tree and write a JSONL receipt:

```bash
taghag-import scan --root /path/to/mp3-library --out ./receipts/first-import.jsonl
```

2. Review the JSONL receipt locally.
3. Load the receipt into the database with server-side credentials in the environment:

```bash
taghag-import load --receipt ./receipts/first-import.jsonl
```
