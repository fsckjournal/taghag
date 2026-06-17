# Taghag and Cuecifer Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Cuecifer a Taghag-owned DJ recommendation and set-sequencing capability without importing the Tagslut schema, runtime, or mixed-format workflow.

**Architecture:** Taghag processes MP3 files on local disks and never uploads audio. Its local tools discover MP3s, extract tags and technical metadata, run the Essentia workflow, and produce receipt-backed metadata uploads to Supabase. Supabase is the system of record for MP3 metadata, Essentia analysis, operator tier decisions, Rekordbox observations, and recommendation sessions; Rekordbox is read through a local adapter and is never written directly.

**Tech Stack:** Python 3.11+, Supabase/Postgres with RLS, Vite/React/TypeScript, JSON/JSONL interchange, Essentia sidecar schema `essentia-lexicon-sidecar/2`, pyrekordbox for local read-only Rekordbox access.

---

## Decision Summary

1. Do not merge the Git repositories or copy Tagslut's `track_identity`, `asset_file`, `asset_analysis`, or `identity_key` model into Taghag.
2. Move the Cuecifer product boundary into Taghag. Keep `/Users/g/Projects/tagslut/cuecifer/DESIGN.md` as migration evidence until its accepted rules are represented in Taghag docs and tests.
3. Implement the Essentia workflow inside Taghag. Existing Tagslut sidecars may be used once as migration fixtures, but Taghag must not depend on a Tagslut database, command, or Python package.
4. Use `mp3_file.id` as Cuecifer's durable internal track key. ISRC remains non-unique evidence; path, checksum, duration, artist, and title contribute to reconciliation.
5. Store stable tier as an operator-owned field. Keep set-relative intensity direction in recommendation-session output only.
6. Read Rekordbox locally. Persist normalized observations and sync receipts in Taghag, but do not persist the Rekordbox database or write colors directly.
7. Keep the latest Tagslut FLAC integrity, dedupe action pages, Finder Quick Actions, transcoding, and file deletion workflows outside Taghag. Taghag accepts and processes local MP3s only.

## Source Findings

- Cuecifer currently joins Tagslut analysis and Rekordbox metadata, preferring ISRC and falling back to Tagslut `identity_key`; Taghag replaces this with its own MP3 records and analysis workflow.
- Its accepted stable fields are tier, rating meaning, Essentia attributes, and play-history observations.
- Its runtime-only field is relative intensity direction (`+`/`-`), which must not be stored as a static tag.
- The current tier policy is intended to be operator-calibrated and versioned, but `cuecifer/tier_policy.json` has not yet landed.
- The June 7 Tagslut work after the Cuecifer design commit adds standalone FLAC dedupe review actions and Finder Quick Actions. It does not add a Cuecifer runtime or alter the design contract.
- Taghag already has the correct clean-room base tables, including `mp3_file`, `dj_tag`, `tag_evidence`, `quality_check`, crates, receipts, owner scoping, and RLS.

## Target File Structure

```text
taghag/
  docs/
    CUECIFER.md
    superpowers/plans/2026-06-07-merge-taghag-cuecifer.md
  contracts/
    essentia_lexicon_sidecar_v2.schema.json
    rekordbox_observation_v1.schema.json
  supabase/migrations/
    <timestamp>_add_cuecifer_metadata.sql
    <timestamp>_add_cuecifer_recommendations.sql
  tools/taghag_import/
    analysis_contract.py
    analysis_runner.py
    analysis_import.py
    rekordbox_reader.py
    rekordbox_sync.py
    tier_policy.py
    recommendations.py
  tools/tests/
    fixtures/
      essentia_sidecar_v2.json
      rekordbox_observations_v1.json
    test_analysis_contract.py
    test_analysis_runner.py
    test_analysis_import.py
    test_rekordbox_sync.py
    test_tier_policy.py
    test_recommendations.py
  web/src/
    lib/database.types.ts
    features/cuecifer/
      CueciferPage.tsx
      TierReview.tsx
      RecommendationPanel.tsx
      types.ts
```

## Phase 1: Freeze The Boundary

### Task 1: Promote Cuecifer rules into Taghag

**Files:**
- Create: `docs/CUECIFER.md`
- Modify: `README.md`
- Test: `tools/tests/test_cleanroom_audit.py`

- [ ] Write `docs/CUECIFER.md` with the accepted tier meanings, rating semantics, Essentia attribute meanings, play-history session rule, read-only Rekordbox rule, and runtime-only intensity rule.
- [ ] Replace the `identity_key` fallback with the Taghag reconciliation contract: exact `mp3_file.id` mapping first, then checksum, then reviewed ISRC/metadata candidates.
- [ ] Document that `danceability` is retained but excluded from default tier prediction because the observed corpus has weak discriminating power.
- [ ] Link the new product document from `README.md`.
- [ ] Extend the clean-room test so active Python and SQL still reject Tagslut schema nouns while documentation may cite them only in clearly marked migration sections.
- [ ] Run `python tools/audit_cleanroom.py` and `pytest tools/tests/test_cleanroom_audit.py -q`.
- [ ] Commit with `docs: define Taghag Cuecifer boundary`.

## Phase 2: Add Durable Cuecifer Data

### Task 2: Add analysis, policy, and Rekordbox observation tables

**Files:**
- Create: `supabase/migrations/<timestamp>_add_cuecifer_metadata.sql`
- Modify: `tools/taghag_import/schema_contract.py`
- Test: `tools/tests/test_schema_contract.py`

- [ ] Add `track_analysis` keyed by owner and `mp3_file_id`, with `schema_name`, `analyzer`, `analyzer_version`, `happy`, `aggressive`, `relaxed`, `party`, `danceability`, raw genre candidates, source artifact digest, and `computed_at`.
- [ ] Add `tier_policy` with immutable version, policy JSON, source worksheet digest, accepted timestamp, and active flag.
- [ ] Add `rekordbox_track_observation` with Rekordbox content ID, optional ISRC, rating, color, play count, last played time, cue summary JSON, beat-grid summary JSON, source database fingerprint, and observed timestamp.
- [ ] Add `external_track_match` to record reviewed mappings from external source IDs to `mp3_file.id`, including method, confidence, evidence JSON, and review status.
- [ ] Add nullable `tier smallint` and `tier_source` to `dj_tag`; constrain tier to 1-3 and distinguish `operator`, `rekordbox_color`, and `policy_suggestion`.
- [ ] Do not add a static intensity-direction column.
- [ ] Apply owner-scoped foreign keys, RLS, no anon access, authenticated read policies, and service-role importer grants matching the initial migration.
- [ ] Update `APP_TABLES` and schema tests for all new tables, triggers, policies, and constraints.
- [ ] Run `pytest tools/tests/test_schema_contract.py -q`.
- [ ] Apply the migration to the configured development Supabase project and run the schema validation SQL.
- [ ] Commit with `feat: add Cuecifer metadata schema`.

## Phase 3: Implement The Local Essentia Workflow

### Task 3: Validate Taghag Essentia analysis artifacts

**Files:**
- Create: `contracts/essentia_lexicon_sidecar_v2.schema.json`
- Create: `tools/taghag_import/analysis_contract.py`
- Create: `tools/tests/fixtures/essentia_sidecar_v2.json`
- Test: `tools/tests/test_analysis_contract.py`

- [ ] Encode the minimum accepted `essentia-lexicon-sidecar/2` structure: schema marker, Taghag file key, local path, genre candidates, five Cuecifer attributes, analyzer metadata, and timestamps when present.
- [ ] Reject unknown schema versions, non-finite floats, missing track maps, and attributes outside 0-1.
- [ ] Preserve unknown fields in raw evidence so forward-compatible data is not discarded.
- [ ] Calculate a SHA-256 digest for the complete source artifact and include it in every import receipt.
- [ ] Add fixtures covering valid records, absent optional attributes, invalid ranges, and wrong schema versions.
- [ ] Run `pytest tools/tests/test_analysis_contract.py -q`.
- [ ] Commit with `feat: add Essentia sidecar contract`.

### Task 4: Run Essentia locally from Taghag

**Files:**
- Create: `tools/taghag_import/analysis_runner.py`
- Modify: `tools/taghag_import/cli.py`
- Test: `tools/tests/test_analysis_runner.py`

- [ ] Add `taghag-import analyze --root <mp3-root> --out <artifact>` and process only discovered `.mp3` files.
- [ ] Reuse Taghag discovery and audio probing so every analysis row carries `file_key`, path, checksum evidence, duration, and extracted ID3 metadata.
- [ ] Invoke the pinned Essentia models required to produce `happy`, `aggressive`, `relaxed`, `party`, `danceability`, and genre candidates.
- [ ] Record model names, model digests, Essentia version, command version, processing time, and per-file errors.
- [ ] Write the versioned sidecar locally and never upload audio samples, embeddings, temporary WAV data, or model input buffers.
- [ ] Make the command resumable by skipping rows whose file fingerprint and analyzer version are unchanged.
- [ ] Test MP3-only discovery, deterministic artifacts, resume behavior, failed-file receipts, and absence of audio payloads.
- [ ] Run `pytest tools/tests/test_analysis_runner.py -q`.
- [ ] Commit with `feat: run local Essentia analysis`.

## Phase 4: Store Essentia Metadata

### Task 5: Bind analysis to the scanned MP3 record

**Files:**
- Create: `tools/taghag_import/analysis_import.py`
- Modify: `tools/taghag_import/cli.py`
- Test: `tools/tests/test_analysis_import.py`

- [ ] Add `taghag-import import-analysis --input <sidecar> --no-upload`.
- [ ] Bind each analysis row through its Taghag `file_key` and verify the current local fingerprint before upload.
- [ ] Write a receipt event for source validation, every match result, every uploaded analysis row, and the final counts.
- [ ] Upsert only normalized metadata and Essentia outputs into `track_analysis`; never include audio bytes or temporary analysis files.
- [ ] Reject stale artifacts when the local MP3 fingerprint no longer matches.
- [ ] Make reruns idempotent by owner, file, schema, analyzer version, computed timestamp, and source digest.
- [ ] Test dry-run behavior, idempotency, stale-file rejection, metadata-only payloads, and secret-free receipts.
- [ ] Run `pytest tools/tests/test_analysis_import.py -q`.
- [ ] Commit with `feat: import Cuecifer analysis snapshots`.

## Phase 5: Import Rekordbox Observations

### Task 6: Add a local read-only Rekordbox adapter

**Files:**
- Create: `contracts/rekordbox_observation_v1.schema.json`
- Create: `tools/taghag_import/rekordbox_reader.py`
- Create: `tools/taghag_import/rekordbox_sync.py`
- Test: `tools/tests/test_rekordbox_sync.py`

- [ ] Use pyrekordbox to read a user-supplied `master.db` path; never hard-code `/Users/g/Library/Pioneer/rekordbox/master.db`.
- [ ] Refuse write mode and fail clearly when Rekordbox appears to be running or the schema is unsupported.
- [ ] Normalize rating, color, play history, cues, and beat-grid summaries into the versioned observation contract.
- [ ] Infer play sessions from gaps greater than 30 minutes in a pure function with direct tests.
- [ ] Reconcile observations through `external_track_match`; do not join solely on ISRC.
- [ ] Add `taghag-import sync-rekordbox --db <path> --no-upload`.
- [ ] Persist source database fingerprint and sync receipt, not the database itself.
- [ ] Run `pytest tools/tests/test_rekordbox_sync.py -q`.
- [ ] Commit with `feat: sync read-only Rekordbox observations`.

## Phase 6: Tier Policy And Recommendations

### Task 7: Compile operator-reviewed tier policy

**Files:**
- Create: `tools/taghag_import/tier_policy.py`
- Test: `tools/tests/test_tier_policy.py`

- [ ] Accept a CSV with `mp3_file_id`, analysis columns, `suggested_tier`, operator `tier`, and notes.
- [ ] Reject unlabeled rows, tiers outside 1-3, duplicate file IDs, and missing source analysis digests.
- [ ] Compile immutable `cuecifer-tier-policy/1` JSON containing accepted thresholds, worksheet digest, corpus summary, and creation metadata.
- [ ] Apply operator tiers to `dj_tag.tier` with `tier_source='operator'`.
- [ ] Use policy output only as a suggestion for unlabeled tracks; never overwrite operator tiers.
- [ ] Keep the 113-123 BPM band review-required unless a later accepted policy explicitly narrows it.
- [ ] Run `pytest tools/tests/test_tier_policy.py -q`.
- [ ] Commit with `feat: compile operator-reviewed tier policy`.

### Task 8: Add explainable next-track recommendations

**Files:**
- Create: `supabase/migrations/<timestamp>_add_cuecifer_recommendations.sql`
- Create: `tools/taghag_import/recommendations.py`
- Test: `tools/tests/test_recommendations.py`

- [ ] Add `recommendation_session` and `recommendation_candidate` tables with owner scoping and RLS.
- [ ] Define input context as current track, optional crate, target tier, desired intensity direction, and exclusions.
- [ ] Score candidates from harmonic compatibility, BPM transition, tier movement, Essentia profile distance, rating, recency, and recent-session repetition.
- [ ] Store component scores and reasons so every recommendation is explainable.
- [ ] Store intensity direction only on the recommendation candidate/session result.
- [ ] Exclude unresolved external matches and tracks lacking a local `mp3_file`.
- [ ] Add deterministic tests for tie-breaking, recent-play penalties, rating independence from tier, and upward/downward intensity requests.
- [ ] Run `pytest tools/tests/test_recommendations.py -q`.
- [ ] Commit with `feat: add explainable Cuecifer recommendations`.

## Phase 7: Add The Taghag UI

### Task 9: Build tier review and recommendation surfaces

**Files:**
- Create: `web/src/features/cuecifer/types.ts`
- Create: `web/src/features/cuecifer/TierReview.tsx`
- Create: `web/src/features/cuecifer/RecommendationPanel.tsx`
- Create: `web/src/features/cuecifer/CueciferPage.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/lib/database.types.ts`

- [ ] Regenerate Supabase TypeScript types after both Cuecifer migrations.
- [ ] Add an unmatched-analysis queue showing evidence and requiring explicit operator confirmation.
- [ ] Add tier review filters for BPM boundary, genre, current suggestion, and missing operator tier.
- [ ] Add a recommendation panel that shows ranked candidates and score explanations.
- [ ] Keep Rekordbox color and rating visible as observed values; do not write them directly from the browser.
- [ ] Run `cd web && npm run build`.
- [ ] Start the Vite app and verify the unmatched queue, tier review, and recommendation flow in the in-app browser.
- [ ] Commit with `feat: add Cuecifer review and recommendation UI`.

## Phase 8: Cutover And Remove The Temporary Bridge

### Task 10: Verify migration and declare ownership

**Files:**
- Modify: `docs/CUECIFER.md`
- Modify: `docs/TAGHAG_HANDOVER.md`
- Modify in Tagslut: `cuecifer/DESIGN.md`
- Modify in Tagslut: `docs/CURRENT.md`

- [ ] Run the Taghag Essentia workflow over the selected local MP3 library and record analyzed, skipped, stale, and failed counts.
- [ ] Verify a sample of local MP3 fingerprints against their uploaded metadata rows.
- [ ] Import a read-only Rekordbox snapshot and verify rating/color/play-history mappings on a representative sample.
- [ ] Confirm operator tiers are preserved across repeated analysis and Rekordbox imports.
- [ ] Run `python tools/audit_cleanroom.py`, `pytest tools/tests -q`, and `cd web && npm run build`.
- [ ] Mark Taghag `docs/CUECIFER.md` as the product source of truth.
- [ ] Replace Tagslut's active Cuecifer design with a short pointer to Taghag; no runtime bridge remains.
- [ ] Commit and push Taghag with `docs: complete Cuecifer ownership cutover`.
- [ ] Commit and push Tagslut with `docs: hand Cuecifer ownership to Taghag`.

## Rollout Gates

- Gate 1: No active Taghag code or SQL imports Tagslut modules or schema nouns.
- Gate 2: Local MP3 discovery, Essentia execution, sidecar validation, and stale-fingerprint tests pass before any upload.
- Gate 3: Every uploaded analysis row has a verified Taghag file key and local fingerprint.
- Gate 4: Tier policy cannot overwrite operator labels.
- Gate 5: Rekordbox sync is demonstrably read-only and emits a receipt.
- Gate 6: Recommendation output includes component-level explanations and deterministic tie-breaking.
- Gate 7: Full Taghag Python tests, clean-room audit, and frontend build pass before ownership cutover.

## Explicit Non-Goals

- FLAC discovery, integrity repair, dedupe execution, Finder Quick Actions, or file deletion.
- Importing Tagslut's identity or provenance tables.
- Depending on Tagslut to transcode, admit, or analyze Taghag MP3 files.
- Uploading audio to Supabase.
- Writing Rekordbox `master.db` directly.
- Automatically assigning permanent tiers from BPM alone.
- Treating Essentia and Spotify audio features as interchangeable.
- Reusing static `+`/`-` tags from files or external databases.
