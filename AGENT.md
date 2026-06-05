# Taghag Agent Rules

- MP3-only v1.
- No FLAC, AAC, M4A, ALAC, or mixed-format intake support.
- No old tagslut schema.
- Do not reference the source project package from code.
- Do not create or use `asset_file`, `track_identity`, or `preferred_asset`.
- No file deletion or trashing.
- No server-only key in frontend code.
- SQL changes must be source-controlled migrations under `supabase/migrations/`.
- Active docs are `README.md`, `AGENT.md`, `docs/TAGHAG_HANDOVER.md`, `docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md`, and `.github/prompts/README.md`.
- Reusable prompts belong in `.github/prompts/` and should use the `taghag-<order>-<scope>.prompt.md` naming template.
- Commit intentionally staged changes and push.
