Goal:
Prevent Taghag from silently becoming tagslut v3 again.

Script:
`tools/audit_cleanroom.py`

Command:
`python tools/audit_cleanroom.py`

Forbidden active-code terms:
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

Scope:
- Scan active code, SQL migrations, config, and tests.
- Allow forbidden terms only in docs sections explicitly marked as historical or forbidden.
- Suggested allow markers:
  `cleanroom-audit: allow-start`
  `cleanroom-audit: allow-end`
- Do not allow forbidden terms in migrations or active code.
- The audit must fail with file path and line number.

Tests:
- Audit passes on clean project.
- Audit fails if a forbidden import appears in Python.
- Audit fails if a forbidden schema name appears in SQL.
- Audit allows marked docs warning sections only.

Docs:
- README includes `python tools/audit_cleanroom.py`.
- `AGENT.md` says run clean-room audit before commit when schema/importer/web behavior changes.
