# Manifest-Driven Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow `taghag-import stage` to process an explicit JSONL allowlist of FLAC files as one validation and decoded-audio dedupe cohort.

**Architecture:** Add a focused manifest parser that returns validated source and relative-path pairs. Refactor the existing stage planner around a shared entry planner, keeping directory discovery and manifest loading as separate input adapters. The CLI selects exactly one adapter and preserves all existing execution, report, receipt, and database-free behavior.

**Tech Stack:** Python 3.11+, `pathlib`, JSONL, pytest, existing FFmpeg/FLAC/Mutagen stage modules.

---

### Task 1: Manifest Contract

**Files:**
- Modify: `tools/taghag_import/stage.py`
- Test: `tools/tests/test_stage.py`

- [ ] **Step 1: Write failing parser tests**

Add tests that write JSONL entries with `source` and `relative_path`, then assert
that valid rows are sorted by source and that missing files, non-FLAC sources,
absolute relative paths, traversal, duplicate sources, and duplicate relative
paths raise `ValueError`.

- [ ] **Step 2: Run the focused tests**

Run: `cd tools && pytest tests/test_stage.py -q`

Expected: FAIL because `load_stage_manifest` does not exist.

- [ ] **Step 3: Implement the parser**

Add an immutable `StageSource` record and `load_stage_manifest(path)` in
`stage.py`. Parse non-blank JSONL lines, validate string fields and filesystem
constraints, reject source/destination duplicates, and return sources sorted by
absolute source path.

- [ ] **Step 4: Verify the parser**

Run: `cd tools && pytest tests/test_stage.py -q`

Expected: PASS.

### Task 2: Shared Planner

**Files:**
- Modify: `tools/taghag_import/stage.py`
- Test: `tools/tests/test_stage.py`

- [ ] **Step 1: Write failing manifest-planner tests**

Add tests proving that `plan_stage_manifest` uses manifest relative paths for
destinations and blocks equal decoded PCM across entries from different source
directories.

- [ ] **Step 2: Run the focused tests**

Run: `cd tools && pytest tests/test_stage.py -q`

Expected: FAIL because `plan_stage_manifest` does not exist.

- [ ] **Step 3: Refactor and implement**

Extract the existing item loop into a private planner accepting
`list[StageSource]`. Keep `plan_stage(source, output)` as a discovery adapter
and add `plan_stage_manifest(manifest, output)` as a manifest adapter.

- [ ] **Step 4: Verify stage behavior**

Run: `cd tools && pytest tests/test_stage.py tests/test_flac.py tests/test_transcode.py -q`

Expected: PASS.

### Task 3: CLI Selection

**Files:**
- Modify: `tools/taghag_import/cli.py`
- Test: `tools/tests/test_stage_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add tests that `stage --manifest manifest.jsonl --dry-run` calls
`plan_stage_manifest`, and argparse rejects commands that provide both inputs
or neither input.

- [ ] **Step 2: Run the focused tests**

Run: `cd tools && pytest tests/test_stage_cli.py -q`

Expected: FAIL because `--manifest` is unavailable.

- [ ] **Step 3: Implement CLI routing**

Make `--source` and `--manifest` a required mutually exclusive group. Route to
`plan_stage_manifest` when a manifest is present and retain the existing source
route otherwise.

- [ ] **Step 4: Verify CLI behavior**

Run: `cd tools && pytest tests/test_stage_cli.py tests/test_transcode_cli.py -q`

Expected: PASS.

### Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `tools/README.md`

- [ ] **Step 1: Document the JSONL contract**

Add a manifest-stage example, explicitly note that source files remain
read-only, and explain that one manifest creates one cross-folder dedupe domain.

- [ ] **Step 2: Run importer verification**

Run:

```bash
python tools/audit_cleanroom.py
cd tools && pytest -q
```

Expected: clean-room audit passes and all tests pass.

- [ ] **Step 3: Build and dry-run the private Roon manifest**

Create an ignored artifact containing all resolved Roon rows, then run:

```bash
tools/.venv/bin/taghag-import stage \
  --manifest artifacts/roon_compilations/manifest.jsonl \
  --output /Volumes/LOSSY/taghag/roon-electronic-compilations \
  --dry-run \
  --quiet
```

Expected: all entries are discovered, missing-path count is zero, invalid count
is zero, and duplicates are reported without writing output.

- [ ] **Step 4: Commit and push**

Stage only the implementation, tests, and docs. Commit with
`feat: add manifest-driven stage input` and push the current branch.
