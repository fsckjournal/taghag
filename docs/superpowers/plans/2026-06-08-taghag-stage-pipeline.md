# Taghag Stage Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a database-free `taghag-import stage` command that validates FLACs, blocks identical decoded audio, transcodes admitted files to local MP3s, validates outputs, and writes metadata-only reports and receipts.

**Architecture:** A focused `stage.py` orchestrator composes pure discovery, probing, fingerprinting, dedupe, and report helpers with the existing `transcode.py`, `audio_probe.py`, and MP3 import record builder. PCM fingerprints are computed by streaming canonical signed 16-bit little-endian PCM from FFmpeg into SHA-256; source files are never modified.

**Tech Stack:** Python 3.11+, FFmpeg/ffprobe, `flac -t`, mutagen, CSV/JSON/JSONL, pytest.

---

### Task 1: FLAC Discovery, Validation, And Fingerprinting

**Files:**
- Create: `tools/taghag_import/flac.py`
- Test: `tools/tests/test_flac.py`

- [ ] Write failing tests for single-file/directory discovery, junk filtering, `flac -t` failures, ffprobe metadata, and deterministic PCM SHA-256.
- [ ] Run `pytest tools/tests/test_flac.py -q` and confirm missing-module failures.
- [ ] Implement `discover_flacs`, `probe_flac`, `extract_flac_tags`, `sha256_file`, and `pcm_sha256`.
- [ ] Run `pytest tools/tests/test_flac.py -q` and confirm all tests pass.

### Task 2: Hard Audio-Duplicate Admission

**Files:**
- Create: `tools/taghag_import/stage.py`
- Test: `tools/tests/test_stage.py`

- [ ] Write failing tests proving lexicographic keeper selection, compilation duplicates are blocked, metadata-only matches remain candidates, and existing output-corpus audio blocks admission.
- [ ] Run `pytest tools/tests/test_stage.py -q` and confirm missing behavior.
- [ ] Implement immutable stage records and a planner that groups by PCM hash, indexes existing MP3 PCM hashes, and emits admitted/blocked/candidate decisions.
- [ ] Run `pytest tools/tests/test_stage.py -q`.

### Task 3: Transcode, Validate, Reports, And Receipt

**Files:**
- Modify: `tools/taghag_import/stage.py`
- Modify: `tools/taghag_import/transcode.py`
- Test: `tools/tests/test_stage.py`

- [ ] Add failing tests for dry-run no writes, duplicate losers not transcoded, failed-output exclusion, metadata-only JSONL, CSV reports, and partial-failure summaries.
- [ ] Implement execution using existing `TranscodeJob`, validate outputs with `probe_mp3`, and write `audio_duplicates.csv`, `metadata_candidates.csv`, `summary.json`, and `receipts/stage.jsonl`.
- [ ] Run `pytest tools/tests/test_stage.py tools/tests/test_transcode.py -q`.

### Task 4: CLI And Documentation

**Files:**
- Modify: `tools/taghag_import/cli.py`
- Modify: `tools/taghag_import/__init__.py`
- Modify: `README.md`
- Modify: `tools/README.md`
- Test: `tools/tests/test_stage_cli.py`

- [ ] Write a failing CLI test for file/folder input, verbose default, `--quiet`, and `--dry-run`.
- [ ] Add `taghag-import stage --source --output [--dry-run] [--quiet]`.
- [ ] Document the exact Qobuz command and safety guarantees.
- [ ] Run `pytest tools/tests/test_stage_cli.py -q`.

### Task 5: End-To-End Verification

- [ ] Run `pytest tools/tests -q`.
- [ ] Run `python tools/audit_cleanroom.py`.
- [ ] Run `cd web && npm run build`.
- [ ] Dry-run the 58-file Qobuz folder and verify no filesystem writes.
- [ ] Run a temporary fixture containing two differently tagged FLAC containers with identical PCM and verify only one MP3 is produced.
- [ ] Commit and push with `feat: add deduplicating Taghag stage pipeline`.
