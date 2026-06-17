# MP3 Tools And Provider Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Taghag-native MP3 audit, tag dump/write, and Postman provider-evidence commands while preserving the clean-room and metadata-only boundaries.

**Architecture:** Extend the existing Taghag ID3, probe, evidence, discovery, and CLI modules. Add one focused audit module and one focused provider runner; keep report and receipt formats metadata-only and make all file writes explicit and conservative.

**Tech Stack:** Python 3.11+, argparse, pathlib, csv/json, subprocess, mutagen, pytest.

---

### Task 1: Extend ID3 Read, Dump, And Selective Write Behavior

**Files:**
- Modify: `tools/taghag_import/tags.py`
- Create: `tools/tests/test_tags.py`

- [ ] **Step 1: Write failing tests for safe tag dumping**

Add tests that create an ID3-tagged MP3 fixture with text, artwork, comment, and
an unknown `TXXX` frame. Assert `dump_mp3_tags()` preserves text values,
summarizes artwork as metadata such as `"<binary:4 bytes>"`, and never includes
raw binary bytes.

- [ ] **Step 2: Run the tag tests and confirm the new API is missing**

Run:

```bash
cd tools && pytest tests/test_tags.py -q
```

Expected: failure because `dump_mp3_tags` is not defined.

- [ ] **Step 3: Implement safe dumping in `tags.py`**

Add:

```python
def dump_mp3_tags(path: str | Path, *, max_value_len: int = 2000) -> dict[str, list[str]]:
    """Return safe string summaries for every readable ID3 frame in an MP3."""
```

Use `mutagen.id3.ID3`, preserve frame keys, convert textual frame data to
strings, and summarize binary payloads by byte count.

- [ ] **Step 4: Write failing tests for dry-run and selective writes**

Cover:

- `apply_mp3_tag_updates(path, updates, execute=False)` does not mutate the file.
- `execute=True` writes only requested known fields.
- Existing values are preserved without `force=True`.
- Unknown `TXXX` frames survive writes.
- No `COMM` frame is added or changed by Taghag writes.

- [ ] **Step 5: Implement selective writes**

Add:

```python
@dataclass(frozen=True)
class TagWriteResult:
    path: str
    planned_fields: list[str]
    applied_fields: list[str]
    skipped_fields: list[str]
    executed: bool


def apply_mp3_tag_updates(
    path: str | Path,
    updates: Mapping[str, object],
    *,
    execute: bool = False,
    force: bool = False,
) -> TagWriteResult:
    """Plan or apply selected Taghag DJ metadata fields to one MP3."""
```

Map Taghag field names to ID3 frames and `TXXX` descriptions. Load the existing
ID3 object, modify only selected frames, preserve all other frames, and save
only when `execute` is true.

- [ ] **Step 6: Run focused tests**

Run:

```bash
cd tools && pytest tests/test_tags.py -q
```

Expected: all tag tests pass.

### Task 2: Add MP3 Audit Reports

**Files:**
- Create: `tools/taghag_import/mp3_audit.py`
- Create: `tools/tests/test_mp3_audit.py`
- Modify: `tools/taghag_import/cli.py`
- Modify: `tools/tests/test_import_cli.py`

- [ ] **Step 1: Write failing audit report tests**

Test `run_mp3_audit()` with patched discovery, tag extraction, and probing.
Assert it writes:

- `mp3_audit.jsonl`
- `mp3_audit.csv`
- `summary.json`

Assert rows contain metadata and issue codes only, skipped files are reported,
and no audio payload field appears.

- [ ] **Step 2: Verify the audit tests fail**

Run:

```bash
cd tools && pytest tests/test_mp3_audit.py -q
```

Expected: failure because `taghag_import.mp3_audit` does not exist.

- [ ] **Step 3: Implement audit orchestration**

Create:

```python
@dataclass(frozen=True)
class AuditResult:
    output_dir: Path
    jsonl_path: Path
    csv_path: Path
    summary_path: Path
    summary: dict[str, object]


def run_mp3_audit(root: str | Path, output_dir: str | Path) -> AuditResult:
    """Write metadata-only MP3 audit reports for a local root."""
```

Reuse `discover_audio_files`, `extract_mp3_tags`, `probe_mp3`, and
`classify_genre`. Keep issue-code construction aligned with `import-batch`.

- [ ] **Step 4: Add `audit-mp3` CLI tests and implementation**

Add parser coverage for:

```bash
taghag-import audit-mp3 --root /path/to/mp3s --output-dir artifacts/mp3_audit
```

The CLI prints the prepared report paths and summary counts.

- [ ] **Step 5: Run audit and CLI tests**

Run:

```bash
cd tools && pytest tests/test_mp3_audit.py tests/test_import_cli.py -q
```

Expected: all tests pass.

### Task 3: Add Dump And Write Commands

**Files:**
- Modify: `tools/taghag_import/cli.py`
- Modify: `tools/tests/test_import_cli.py`
- Modify: `tools/tests/test_tags.py`

- [ ] **Step 1: Write failing CLI parser tests**

Cover:

```bash
taghag-import dump-tags --root /path/to/mp3s --out tags.jsonl
taghag-import write-tags --plan updates.csv
taghag-import write-tags --plan updates.csv --execute --force
```

Require exactly one dump input source from `--root`, repeated `--path`, or
`--paths-file`. Require a CSV plan for `write-tags`.

- [ ] **Step 2: Implement path collection and metadata-only dump output**

Add CLI helpers that collect only `.mp3` paths, call `dump_mp3_tags`, and write
one stable JSON object per line:

```json
{"path":"/absolute/track.mp3","tags":{"TIT2":["Title"]}}
```

- [ ] **Step 3: Implement CSV write-plan loading**

Accept columns:

```text
path,field,value
```

Run `apply_mp3_tag_updates` for each row grouped by path. Default to dry-run and
save only with `--execute`.

- [ ] **Step 4: Run command tests**

Run:

```bash
cd tools && pytest tests/test_tags.py tests/test_import_cli.py -q
```

Expected: all tests pass.

### Task 4: Add Provider Evidence Runner

**Files:**
- Create: `tools/taghag_import/provider_runner.py`
- Create: `tools/tests/test_provider_runner.py`
- Modify: `tools/taghag_import/postman_evidence.py`
- Modify: `tools/tests/test_postman_evidence.py`
- Modify: `tools/taghag_import/cli.py`
- Modify: `tools/tests/test_import_cli.py`

- [ ] **Step 1: Write failing command-construction tests**

Assert the runner targets only:

- `Spotify/Lookup - Release Identity by ISRC`
- `TIDAL/Search - by ISRC`
- `Beatport/Search - by ISRC`
- `Qobuz/Search - by ISRC`

Assert `lookup_isrc` is supplied, broad provider folders are absent, and secret
environment values are redacted from displayed commands.

- [ ] **Step 2: Write failing subprocess-failure tests**

Patch `subprocess.run` to return non-zero and emit no markers. Assert the batch
continues, writes a metadata-only failure marker/event to the output log, and
records the failed ISRC in `summary.json`.

- [ ] **Step 3: Implement provider runner**

Add:

```python
@dataclass(frozen=True)
class ProviderBatchResult:
    output_dir: Path
    evidence_log: Path
    summary_path: Path
    summary: dict[str, object]


def build_postman_command(isrc: str, config: ProviderRunnerConfig) -> list[str]:
    """Build the exact Postman command for one ISRC lookup."""


def display_command(command: list[str], secret_keys: set[str]) -> str:
    """Return a shell-display command with secret env values redacted."""


def run_provider_batch(isrcs: Sequence[str], config: ProviderRunnerConfig) -> ProviderBatchResult:
    """Run or prepare a metadata-only provider evidence batch."""
```

Use configurable Postman binary, collection, and environment paths. Verify all
required paths before execution. Preserve raw `[Tag Evidence JSON]` lines in
the log so the existing importer parser can consume the output.

- [ ] **Step 4: Improve malformed/wrapped marker parsing**

Extend `parse_tag_evidence()` so wrapped Postman console output and malformed
marker payloads produce evidence rows instead of raising.

- [ ] **Step 5: Add `provider-evidence` CLI**

Support repeated `--isrc` and `--isrc-file`, plus:

```bash
taghag-import provider-evidence \
  --isrc USABC2400001 \
  --collection /path/to/postman/collection \
  --environment /path/to/environment.json \
  --output-dir artifacts/provider_evidence
```

Print a verified, redacted command before execution. A large batch remains an
operator command; tests use small patched subprocess fixtures only.

- [ ] **Step 6: Verify provider compatibility**

Feed the generated evidence log to `_build_import_batch_records(root,
postman_evidence=str(evidence_log))` and assert `tag_evidence` receipt events
are produced.

- [ ] **Step 7: Run provider tests**

Run:

```bash
cd tools && pytest tests/test_provider_runner.py tests/test_postman_evidence.py tests/test_import_cli.py -q
```

Expected: all tests pass.

### Task 5: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `tools/README.md`
- Modify: `tools/EXTRACTION_NOTE.md`

- [ ] **Step 1: Document the four commands**

Document dry-run defaults, `--execute`, metadata-only reports, exact Postman
inputs, and the handoff from `provider-evidence` to
`import-batch --postman-evidence`.

- [ ] **Step 2: Preserve FLAC preprocessing documentation**

Leave transcode/stage documentation active and clarify that it is a
database-free preprocessing path producing MP3s, not database intake.

- [ ] **Step 3: Run clean-room audit and focused tests**

Run:

```bash
python tools/audit_cleanroom.py
cd tools && pytest tests/test_tags.py tests/test_mp3_audit.py tests/test_provider_runner.py tests/test_postman_evidence.py tests/test_import_cli.py -q
```

Expected: clean-room audit passes and all focused tests pass.

- [ ] **Step 4: Run the full Taghag tools suite**

Run:

```bash
cd tools && pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 5: Verify CLI help and repository diff**

Run:

```bash
cd tools && python -m taghag_import.cli --help
git diff --check
git status --short
```

Expected: all four new commands appear, no whitespace errors, and only intended
Taghag files are changed.

- [ ] **Step 6: Commit and push**

Stage only the implementation, tests, and active docs. Commit with:

```bash
git commit -m "feat: add MP3 audit and provider tools"
git push origin main
```
