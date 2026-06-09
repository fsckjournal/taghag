# Taghag Handover

This note is for the next AI agent taking over the Taghag repository with no prior context.

## Project Intent

Taghag is a clean-room, MP3-only, metadata-only private DJ app. The durable plan is in `docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md`. Execution is broken into ordered prompts under `.github/prompts/`, from repo layout through migration, importer, web shell, tests, clean-room audit, verification, and definition of done.

## What Has Been Implemented

The foundational implementation is effectively complete through Prompt 08 (`taghag-08-clean-room-audit.prompt.md`).

- Prompt library and master plan are present under `docs/` and `.github/prompts/`.
- The database schema (Prompt 02) has been fully corrected. The `mp3_track` legacy table was removed and correctly replaced with `mp3_file`. All 9 core tables (including `mp3_observation`) exist with proper RLS policies and grants.
- A Python importer package exists in `tools/taghag_import/` and uses the receipt-first flow (Prompt 03) targeting `mp3_file`.
- A React/Vite shell exists in `web/` with routing, and it is successfully wired to generated Supabase database types from Prompt 05 (`web/src/lib/database.types.ts`).
- Extracted clean-room utilities exist:
  - genre normalization via `tools/taghag_import/genre.py`
  - provider evidence parsing via `tools/taghag_import/postman_evidence.py`
- MP3 operator tooling:
  - `audit-mp3`, `dump-tags`, `write-tags`, `provider-evidence`, `transcode`, and `stage` are functional.
- Python tests cover the importer, MP3 audit/tag tools, provider evidence, staging, transcode, analysis imports, and clean-room utilities.
- Clean-room audit script (`tools/audit_cleanroom.py`) verifies no legacy tagslut terms leak into active code or migrations.

## Current Repository Status Check
Both tests and audits are passing cleanly:
```bash
pytest tools/tests -q
python tools/audit_cleanroom.py
```
(As of the latest check, pytest passes with 78 tests, and the clean-room audit passes perfectly.)

## Recommended Read Order

1. `AGENT.md`
2. `README.md`
3. `docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md`
4. `.github/prompts/README.md`

## Immediate Next Step

The project foundation is solid. The next agent should focus on the final verification and sign-off steps, or proceed to feature development.

Priority order:

1. Execute the verification checklist in `.github/prompts/taghag-09-verification-checklist.prompt.md`.
2. Ensure the project meets the `.github/prompts/taghag-10-definition-of-done.prompt.md`.
3. Proceed with further feature implementation for the web shell or advanced importer requirements as directed by the user.

## Quick Reality Check Commands

```bash
git status --short
pytest tools/tests -q
python tools/audit_cleanroom.py
```
