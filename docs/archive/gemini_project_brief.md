# Taghag Project Brief for Gemini Pro

## Project Summary

Taghag is a private DJ metadata application for managing local music libraries.
Its purpose is to scan, validate, enrich, and organize tracks without uploading
or deleting the user's audio. The application is MP3-first: local MP3 files are
the managed assets, while Supabase stores only metadata, import history, quality
results, provider evidence, crates, and saved views.

## Core Principles

- Audio files remain on local disks and are never stored in Supabase.
- Taghag never deletes, moves, or uploads source audio.
- Version 1 manages MP3 files; other formats are out of scope for database
  intake.
- FLAC is supported only through a separate, local staging workflow that
  validates and transcodes selected files to 320 kbps MP3.
- Import receipts are written locally before any database upload.
- Missing or uncertain metadata is reported for review rather than guessed.
- ISRC, artist/title matches, and provider results are evidence, not automatic
  identity or deduplication rules.
- Secret and service-role credentials must remain server-side. The frontend may
  use only `VITE_` variables and a Supabase publishable key.
- The project is a clean-room implementation and must not import legacy
  Tagslut code, schema, or file-management behavior.

## Implemented System

### Python Importer

The `tools/taghag_import/` package provides the `taghag-import` command. It can:

- Discover MP3s and explicitly report unsupported audio and playlists.
- Extract ID3 metadata, inspect audio properties, compute file identity, and
  normalize genres.
- Produce metadata-only JSONL receipts and optionally upload them to Supabase.
- Import provider evidence and Essentia/Cuecifer analysis metadata.
- Transcode local FLAC files to mirrored 320 kbps MP3 outputs.
- Run an end-to-end FLAC staging pipeline with validation, decoded-audio
  fingerprinting, deterministic duplicate blocking, MP3 verification, reports,
  and receipts.
- Accept either a source tree or an explicit JSONL manifest for staging.

The staging workflow is deliberately database-free and treats source FLACs as
read-only.

### Supabase Backend

Source-controlled migrations in `supabase/migrations/` define a private,
owner-scoped PostgreSQL schema with Row Level Security. The main entities are:

- Import runs, MP3 files, and file observations.
- DJ metadata, provider evidence, and quality checks.
- Crates, crate membership, and saved views.
- Per-track Essentia/Cuecifer analysis values and genre candidates.

`mp3_file` is the primary asset record. Audio bytes are not part of the schema.

### React Web App

The `web/` directory contains a Vite, React, and TypeScript application using a
typed Supabase client. The current UI includes:

- A metadata-quality dashboard.
- Import-run history.
- A filterable library and track detail pages.
- A basic crate listing.

The frontend is currently a functional read-oriented shell rather than a
finished DJ workflow. Authentication UI, editing interactions, richer crate
management, and production-level pagination are not yet visible in the current
implementation.

## Repository Map

- `web/`: React/Vite frontend.
- `tools/`: Python importer, staging pipeline, and pytest suite.
- `supabase/`: database configuration, migrations, and seed file.
- `docs/`: implementation plans, design notes, and handover material.
- `.github/prompts/`: reusable implementation prompts.

## Working With This Repository

When proposing or making changes:

1. Preserve the local-audio and metadata-only boundary.
2. Do not introduce automatic file deletion, movement, or audio upload.
3. Keep database changes in timestamped Supabase migrations.
4. Keep service-role credentials out of the browser.
5. Prefer existing project patterns and make focused changes.
6. Add or update Python tests for importer behavior.
7. Run `python tools/audit_cleanroom.py`, `pytest tools/tests -q`, and
   `cd web && npm run build` before considering a change complete.
8. Treat older planning and handover documents as historical context when they
   conflict with current code or migrations.

The immediate product direction should be confirmed with the operator, but the
clearest current opportunities are completing authenticated web workflows,
adding safe metadata and crate editing, improving large-library querying, and
connecting staged MP3 receipts more directly to the normal import flow.
