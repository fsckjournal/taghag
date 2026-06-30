# Repository Guidelines

> [!NOTE]
> **AGENT WORKSPACE CONTEXT**
> This agent works exclusively on `taghag`. The `tagslut` repository is READ-ONLY for this agent.

## Project Structure & Module Organization
`web/` contains the Vite + React frontend. Primary source files live in `web/src/`, while `web/dist/` is build output and should stay generated. `tools/` contains the standalone Python importer package `taghag_import`, with tests under `tools/tests/`. Supabase assets live in `supabase/`, especially `supabase/migrations/` for source-controlled schema changes and `supabase/seed.sql` for seed data. Reusable agent prompts live in `.github/prompts/`.

## Build, Test, and Development Commands
- `cd web && npm install && npm run dev`: start the frontend locally with Vite.
- `cd web && npm run build`: type-check TypeScript with `tsc --noEmit` and produce a production build.
- `cd web && npm run preview`: serve the built frontend locally.
- `cd tools && python3 -m venv .venv && source .venv/bin/activate && pip install -e .`: set up the importer environment.
- `cd tools && pytest`: run the Python test suite.
- `python tools/audit_cleanroom.py`: fail if active code or migrations use forbidden legacy Tagslut terms.
- `cd tools && taghag-import import-batch --root /path/to/flac-library --run-name batch --no-upload`: scan a local FLAC tree and write a receipt.
- `cd tools && taghag-import import-batch --root /path/to/flac-library --run-name batch`: scan and upload with server-side env vars.

## Coding Style & Naming Conventions
Use TypeScript with ES modules in `web/` and Python 3.11+ in `tools/`. Follow the existing style: 2-space indentation in TSX, 4-space indentation in Python, double quotes in frontend code, and explicit type hints in Python. Keep React components in PascalCase (`App.tsx`), Python modules in snake_case (`postman_evidence.py`), and SQL migrations timestamp-prefixed (`20260606000000_initial_mp3_metadata_schema.sql`).

## Testing Guidelines
Python tests use `pytest` and live in `tools/tests/` as `test_*.py`. Mirror the module or behavior under test, and keep fixtures in `tools/tests/conftest.py` when shared. The frontend currently has no test runner configured, so at minimum run `npm run build` before submitting UI changes.

## Commit & Pull Request Guidelines
Recent history mixes imperative summaries and Conventional Commit prefixes such as `feat:`. Prefer short, imperative commit subjects, using prefixes when they add clarity. PRs should describe scope, call out migration or env changes, link related issues, and include screenshots for frontend work.

## Security & Configuration Tips
Taghag natively processes lossless FLAC files and is metadata-only: do not add logic that uploads or deletes local audio files. Keep server-side database credentials out of frontend code; only `VITE_` variables belong in `web/`. Put schema changes in `supabase/migrations/`, not ad hoc SQL notes.
