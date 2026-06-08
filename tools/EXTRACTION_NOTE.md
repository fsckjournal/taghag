# Extraction Note

This directory contains small, standalone utilities extracted from the allowed `tagslut` sources and adapted to run locally under `tools/taghag_import/` without importing `tagslut`.

## Copied

- `tools/taghag_import/genre.py`
  - Reimplemented from `/Users/g/Projects/tagslut/tagslut/metadata/genre_normalization.py`.
  - Preserves the source normalizer's core behaviors:
    - case-insensitive map lookup
    - parenthetical splitting
    - compound genre splitting
    - style-to-parent promotion
    - canonical-genre fallback handling
    - tag-key cascade support via `choose_normalized()`
- `tools/taghag_import/genre_rules.json`
  - Copied from `/Users/g/Projects/tagslut/tools/rules/genre_normalization.json`.
- `tools/taghag_import/postman_evidence.py`
  - Reimplemented from the marker parser and merge logic in `/Users/g/Projects/tagslut/postman_tag_resolver.py`.
  - Preserves the source seam:
    - parse `[Tag Evidence JSON]` marker lines
    - retain malformed lines as warning evidence
    - reconstruct wrapped Postman console markers
    - filter to the documented tag-evidence schema payloads
    - merge matched provider candidates with provider authority weighting
    - expose merged resolved-tag results without any database dependency
- `tools/taghag_import/provider_runner.py`
  - Reimplements the exact-item Postman command boundary from
    `/Users/g/Projects/tagslut/postman_tag_resolver.py`.
  - Requires an explicit local collection and environment rather than a source
    repo path.
  - Writes normalized marker-only logs compatible with Taghag import receipts.
- `tools/taghag_import/tags.py`
  - Extracts the MP3-only ID3 dump and selective write behavior needed by
    Taghag.
  - Preserves unknown frames, keeps comments untouched, and defaults writes to
    dry-run.
- `tools/taghag_import/mp3_audit.py`
  - Rewrites MP3 inventory and quality-report behavior around Taghag discovery,
    tag, genre, and probe contracts.

## Adapted

- `genre.py`
  - Packaged rule loading now uses the local `taghag_import/genre_rules.json` resource by default.
  - A small `classify_genre()` wrapper remains for existing local CLI compatibility.
- `postman_evidence.py`
  - Parsing and provider-field merging remain independent from execution.
  - Non-`matched` statuses are tracked in `raw_status`, but only `matched` candidates are eligible to populate resolved fields in the standalone resolver.
- `provider_runner.py`
  - Owns command verification, redaction, subprocess execution, failure
    evidence, and long-batch prepare-only behavior.
- `discover.py` and `audio_probe.py`
  - Extend the MP3-only scanner with hidden-directory filtering, `.m3u8`
    reporting, audio-stream selection, sample rate, and channel metadata.

## Intentionally Not Copied

- Any import from `tagslut`
- Any `tagslut` schema or database integration
- Any dependency on local `tagslut` databases
- Any Rekordbox XML support
- Any AAC-specific admission rules
- Any move/provenance or asset-linking models
- Any broader resolver orchestration outside the marker parser and merge seam

## Tests Added

- `tools/tests/test_genre.py`
  - genre normalization
- `tools/tests/test_postman_evidence.py`
  - matched result
  - no-match result
  - ambiguous result
  - error result
  - malformed and wrapped marker results
- `tools/tests/test_provider_runner.py`
  - exact request targeting and redaction
  - subprocess failure evidence
  - prepare-only safety
  - importer-compatible marker logs
- `tools/tests/test_tags.py`
  - binary-safe tag dumps
  - dry-run write safety
  - selective writes and unknown-frame preservation
- `tools/tests/test_mp3_audit.py`
  - metadata-only MP3 audit reports
- `tools/tests/test_audio_probe.py`
  - audio stream selection and probe metadata
- `tools/tests/test_discover.py`
  - MP3 discovery, playlists, and hidden-path filtering
- `tools/tests/test_import_cli.py`
  - command wiring and dry-run importer behavior
