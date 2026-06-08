# MP3 Tools And Provider Export Design

## Purpose

Export the useful Tagslut MP3 audit, tag, and provider-evidence behavior into
Taghag as clean-room, MP3-only tooling. The exported tools must run inside the
Taghag `tools/taghag_import/` package, reuse the existing Taghag contracts, and
avoid any runtime dependency on Tagslut code, databases, schema names, or file
movement machinery.

## Scope

Add four operator commands:

- `taghag-import audit-mp3`
- `taghag-import dump-tags`
- `taghag-import write-tags`
- `taghag-import provider-evidence`

The commands support MP3 metadata inspection, local quality auditing, controlled
ID3 writes, and Postman provider evidence collection. Provider evidence output
must remain compatible with the existing
`taghag-import import-batch --postman-evidence <log>` flow.

## Existing Module Reuse

Reuse and extend these modules instead of creating overlapping abstractions:

- `tools/taghag_import/tags.py`: ID3 extraction, raw tag dumping, field write
  planning, and selective ID3 writes.
- `tools/taghag_import/audio_probe.py`: MP3 technical probe and decode checks.
- `tools/taghag_import/postman_evidence.py`: marker parsing, malformed evidence
  handling, and evidence row conversion.
- `tools/taghag_import/discover.py`: MP3-only discovery and out-of-scope
  reporting.

Add only focused new modules:

- `tools/taghag_import/mp3_audit.py`: audit orchestration and CSV/JSONL report
  writing.
- `tools/taghag_import/provider_runner.py`: checked-command Postman execution,
  readiness checks, subprocess failure capture, and marker-log output.

Do not create a separate `mp3_tags.py`.

## MP3 Audit

`audit-mp3` scans a local root with Taghag discovery. It imports only MP3 rows
into the audit report and records non-MP3 audio/playlists as skipped/out of
scope. For each MP3, it combines:

- ID3 metadata from `tags.py`.
- duration, bitrate, codec, and decode status from `audio_probe.py`.
- metadata issue codes consistent with `import-batch`.
- optional canonical genre/subgenre classification through existing genre
  normalization.

Outputs are metadata-only files under an operator-chosen output directory or a
safe default artifact directory:

- `mp3_audit.jsonl`
- `mp3_audit.csv`
- `summary.json`

Long audits should be prepared and verified as runnable commands, then left for
the operator to execute. The implementation should not poll a large library
inside an agent session.

## Tag Dump And Writes

`dump-tags` reads explicit MP3 paths, an MP3 root, or a paths file and writes a
metadata-only JSONL tag dump. Binary frames such as artwork are summarized by
length instead of copied into reports.

`write-tags` applies selected DJ-facing fields from either CLI flags or a CSV
plan. Writes are conservative:

- Dry-run by default.
- Require `--execute` for mutation.
- Preserve unknown ID3 frames.
- Update only requested known fields.
- Skip existing non-empty fields unless `--force` is set.
- Never use comments for receipts, debug data, provenance, or Taghag app notes.
- Do not delete, move, or trash files.

Supported fields are the Taghag DJ metadata surface: artist, title, album,
label, catalog number, release date/year, genre, subgenre, BPM, musical key,
ISRC, rating, energy, track number, and composer.

## Provider Evidence

`provider-evidence` is a Taghag-owned runner for the checked-in Postman
provider evidence contract. It does not call Tagslut Python and does not open
any Tagslut database. It runs exact Postman collection items for ISRC lookup
and writes the raw console marker log so `import-batch --postman-evidence` can
parse it unchanged.

The runner must:

- Verify the Postman binary/collection/environment command before presenting it.
- Redact secrets in displayed commands.
- Run exact item names, not broad provider folders.
- Accept one ISRC, repeated `--isrc`, or an input file/receipt with ISRCs.
- Continue across per-ISRC subprocess failures and record failure events.
- Treat malformed marker JSON as evidence warnings, not importer crashes.
- Write a marker-compatible log plus metadata-only summary artifacts.

For long provider batches, the tool should make the command and inputs clear so
the operator can run it directly rather than asking the agent to wait on a
large network-bound batch.

## Clean-Room Boundary

The implementation must not include:

- Imports from Tagslut.
- Tagslut SQLite/database access.
- Tagslut v3 schema nouns or legacy asset model terms in active code.
- Runtime dependency on Tagslut repo paths.
- Mixed-format intake.
- Audio upload, deletion, trashing, or movement.

The Tagslut Postman marker schema string is allowed only as an external
evidence contract already consumed by Taghag.

## FLAC Preprocessing Documentation

Keep the existing FLAC staging documentation. In Taghag it describes a
database-free preprocessing workflow that produces local MP3s. It is not
Taghag database intake and should not be removed as part of this export.

## Testing

Add focused pytest coverage for:

- Audit report generation from MP3 discovery and probe/tag fixtures.
- Dry-run write safety: no file mutation without `--execute`.
- Selective writes that preserve unknown frames and skip existing values unless
  forced.
- No comment writes for receipts/debug/provenance.
- Provider runner command construction and secret redaction.
- Provider subprocess failures recorded as metadata-only output.
- Malformed provider evidence preserved as warning rows.
- Provider output compatibility with `import-batch --postman-evidence`.
- Receipts and reports containing metadata only, never audio bytes or secrets.

Verification should include:

```bash
python tools/audit_cleanroom.py
cd tools && pytest tests -q
```

