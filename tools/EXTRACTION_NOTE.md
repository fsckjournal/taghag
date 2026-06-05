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
    - ignore malformed lines safely
    - filter to the documented tag-evidence schema payloads
    - merge matched provider candidates with provider authority weighting
    - expose merged resolved-tag results without any subprocess or database dependency

## Adapted

- `genre.py`
  - Packaged rule loading now uses the local `taghag_import/genre_rules.json` resource by default.
  - A small `classify_genre()` wrapper remains for existing local CLI compatibility.
- `postman_evidence.py`
  - The extracted module only handles parsing and merging.
  - Collection execution, environment handling, subprocess invocation, and availability checks were intentionally left out.
  - Non-`matched` statuses are tracked in `raw_status`, but only `matched` candidates are eligible to populate resolved fields in the standalone resolver.

## Intentionally Not Copied

- Any import from `tagslut`
- Any `tagslut` schema or database integration
- Any dependency on local `tagslut` databases
- Any subprocess runner for the Postman collection
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
