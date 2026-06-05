# Taghag MP3-Only Metadata App Master Plan

There is another Codex on the tagslut side saying hi.

This is a two-way street: if anything is unclear, ask the operator to pass the question back to the tagslut-side Codex. The tagslut-side Codex can clarify source intent, old failure modes, extracted utility contracts, and why certain legacy concepts are forbidden.

Canonical repo:
- `/Users/g/Projects/taghag`

Canonical product name:
- `Taghag`

Important typo guard:
- If the operator writes `taghad`, assume they mean Taghag unless a new repo is explicitly created.

Goal:
Build Taghag as a clean-room, MP3-only, metadata-only private DJ library app. It should inherit proven lessons and tiny standalone utilities from tagslut, but it must not inherit tagslut v3 schema, identity model, database assumptions, or mixed-format workflow.

Rooted in tagslut means:
- Reuse the extracted genre taxonomy behavior.
- Reuse the extracted Postman `[Tag Evidence JSON]` parser contract.
- Reuse the operational lesson that uncertain metadata must skip and report, not guess.
- Reuse the DJ-facing tag contract: canonical genre, canonical subgenre, label, release identity context, evidence status, quality status.
- Preserve the rule that local music files remain local.
- Preserve the rule that ISRC is evidence, not identity.
- Preserve the rule that comments in MP3 files are reserved for Mixed in Key Energy, not importer receipts or debug notes.

Rooted in tagslut does NOT mean:
- Do not copy tagslut v3 schema.
- Do not create `asset_file`.
- Do not create `track_identity`.
- Do not create `asset_link`.
- Do not create `preferred_asset`.
- Do not create `move_plan`, `move_execution`, or `provenance_event`.
- Do not add AAC-first assumptions.
- Do not add Rekordbox XML machinery.
- Do not add Turso/libSQL assumptions.
- Do not depend on local tagslut databases.
- Do not import tagslut from Taghag code.

Current known repo state to verify before work:
- Check `git status` first.
- Read `README.md` and `AGENT.md`.
- Existing prior migration may be under `database/migrations/0001_initial_schema.sql`.
- That existing migration is not acceptable if it contains `mp3_track` instead of `mp3_file`.
- That existing migration is not acceptable if `dj_tag` is a tag dictionary instead of per-file DJ metadata.
- That existing migration is not acceptable if `mp3_observation` is missing.
- That existing migration is not acceptable if authenticated gets broad full CRUD without thought.
- Prefer the operator-requested `supabase/` layout. If `database/` already exists, rename `database/` to `supabase/` unless there is a concrete tool reason not to.
- If keeping `database/`, document why. Do not silently diverge.

Implementation order:
1. Fix repo layout and docs.
2. Build first Supabase migration.
3. Add schema validation tests.
4. Implement local import receipt pipeline.
5. Implement database upsert pipeline.
6. Wire optional Postman evidence import.
7. Generate web database types and typed client.
8. Build first React/Vite UI shell.
9. Add minimum test suite.
10. Add clean-room audit.
11. Run full verification.
12. Commit and push intentionally scoped changes.

Commit cadence:
- Commit after each independently working phase.
- Do not include unrelated dirty files.
- Push after meaningful completed milestones.
