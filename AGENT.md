# Taghag Agent Rules

- MP3-only v1.
- No FLAC, AAC, M4A, ALAC, or mixed-format intake support.
- No old tagslut schema.
- Do not reference the source project package from code.
- Do not create or use `asset_file`, `track_identity`, or `preferred_asset`.
- No file deletion or trashing.
- No server-only key in frontend code.
- SQL changes must be source-controlled migrations.
- Commit intentionally staged changes and push.
