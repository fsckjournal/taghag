# Taghag Import Tooling

FLAC-focused import tooling for the Taghag clean-room audio intelligence app.

## Audit FLAC metadata and quality

```bash
taghag-import audit-flac \
  --root /path/to/flacs \
  --output-dir ../artifacts/audio_audit/manual-check
```

The command writes `audio_audit.jsonl`, `audio_audit.csv`, and `summary.json`.
Reports contain Vorbis comment metadata and technical audio data only, including duration, bitrate,
sample rate, channels, codec, decode status, and issue codes.

## Dump and selectively write Vorbis tags

```bash
taghag-import dump-tags --root /path/to/flacs --out ../artifacts/flac_tags.jsonl
taghag-import write-tags --plan /path/to/path-field-value.csv
```

`write-tags` requires CSV columns `path,field,value`. It is dry-run by default;
add `--execute` to save and `--force` to replace requested non-empty fields.
Unknown Vorbis frames and comments are preserved. Taghag does not write receipt,
debug, or provenance text into FLAC comments.

## Collect provider evidence

```bash
taghag-import provider-evidence \
  --isrc USABC2400001 \
  --collection /path/to/provider-evidence-collection \
  --environment /path/to/provider-environment.json \
  --output-dir ../artifacts/provider_evidence/manual-check
```

The runner verifies and prints a redacted Postman command, targets exact
Spotify, TIDAL, Beatport, and Qobuz ISRC requests, and writes
`provider_evidence.log` plus `summary.json`. The marker log can be passed
unchanged to:

```bash
taghag-import import-batch \
  --root /path/to/flacs \
  --postman-evidence ../artifacts/provider_evidence/manual-check/provider_evidence.log \
  --no-upload
```

Use `--isrc-file` and `--prepare-only` to validate a long batch without
launching Postman. The operator can then run the verified command directly.

## Backfill historical tag data

#TODO: Rename legacy backfill commands and database tables to remove "DJ" branding.

```bash
taghag-import extract-dj-slice --sqlite-db /path/to/music_v3.db --verbose
```

This command reads the legacy SQLite snapshot in read-only mode and upserts
matching rows into `audio_file` and tag tables. It requires a Postgres connection
string via `DB_POSTGRES_URL` or `TAGHAG_DB_POSTGRES_URL` plus
`TAGHAG_OWNER_USER_ID`.

## Run Apple Music Understanding analysis

Analyze registered FLACs with the local Cuecifer Swift analyzer. Dry run prints
the first analyzer JSON without mutating Supabase:

```bash
taghag-import analyze --target /path/to/flac-or-directory --dry-run
```

Without `--dry-run`, the command uploads raw Apple run provenance,
`apple_track_analysis`, `apple_derived_features`, Apple sections/segments/phrases,
and beat/bar cues for tracks already registered in `audio_file`. The local FLAC
is never uploaded.

## Transcode to lossy formats (optional)

```bash
taghag-import transcode \
  --source /path/to/flacs \
  --output /path/to/lossy-copies \
  --dry-run
```

Remove `--dry-run` to write mirrored 320 kbps lossy copies. The command is
filesystem-only and does not initialize a database client. It prints every
transcode and existing-file skip by default; use `--quiet` for summary only.

For validation, decoded-audio dedupe, staging, verification, reports, and
a receipt in one database-free operation:

```bash
taghag-import stage --source /path/to/flacs --output /path/to/taghag-batch
```

The discovery layer also recognizes `.m3u` and `.m3u8` playlist files alongside FLACs, so they are tracked explicitly instead of being silently ignored.

## Stage an explicit FLAC manifest

Use a JSONL manifest to stage selected FLACs from multiple source folders in
one decoded-audio dedupe cohort:

```bash
taghag-import stage \
  --manifest /path/to/selected-flacs.jsonl \
  --output /Volumes/LOSSY/taghag/selected-batch \
  --dry-run
```

Each non-blank line contains an existing absolute FLAC source and its safe
relative destination path:

```json
{"source":"/absolute/path/track.flac","relative_path":"release/track.flac"}
```

The source FLACs remain read-only. Remove `--dry-run` only after every manifest
entry validates and destination paths are unique.
