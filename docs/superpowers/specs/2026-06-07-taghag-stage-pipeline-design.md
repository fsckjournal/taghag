# Taghag Stage Pipeline Design

## Purpose

Add one Taghag-owned command that accepts a local FLAC file or directory and
processes it into a validated, deduplicated, local MP3 batch with metadata
receipts. The command must not import Tagslut code, access the Tagslut database,
upload audio, or modify source FLAC files.

## Command

```bash
taghag-import stage \
  --source /path/to/file-or-folder \
  --output /path/to/taghag-batch
```

The output root contains:

```text
<output>/
  mp3/
  receipts/
    stage.jsonl
  reports/
    exact_duplicates.csv
    metadata_candidates.csv
    summary.json
```

`--dry-run` performs discovery, validation, fingerprinting, duplicate planning,
and reporting without creating the output tree or transcoding audio.

## Safety Boundary

- Source FLACs are read-only.
- No source file is moved, renamed, trashed, or deleted.
- No Tagslut command, module, configuration, or database is used.
- No Supabase connection is made by `stage`.
- Audio remains on local disks.
- Dedupe is report-only at the source layer.
- Exact duplicate losers are skipped during transcoding, but remain untouched.
- Metadata similarity never causes an automatic skip.

## Pipeline

### 1. Discover

Accept either one `.flac` file or a directory. Directory inputs are scanned
recursively. Ignore non-FLAC files, filesystem junk, and AppleDouble files.
Sort paths deterministically.

### 2. Validate FLAC

For each FLAC:

- Run `flac -t`.
- Read duration, sample rate, channels, bit depth, and codec with `ffprobe`.
- Extract embedded tags needed by Taghag: artist, title, album, album artist,
  label, catalog number, release date/year, genre, subgenre, BPM, key, ISRC,
  track number, compilation, and comments.
- Record validation failures in the receipt.

Invalid FLACs are never transcoded. One invalid file does not stop unrelated
valid files.

### 3. Fingerprint And Dedupe

Compute a full SHA-256 file checksum for every valid FLAC.

Exact duplicate groups are files with the same SHA-256 checksum. Select the
lexicographically first path as the deterministic keeper. Other members are
reported as exact duplicates and skipped during transcoding.

Also report, without automatically deduping:

- Repeated non-empty ISRC values with different checksums.
- Repeated normalized artist/title pairs with different checksums.

These are review candidates because releases, edits, masters, and mixes may
legitimately share metadata.

### 4. Transcode

Transcode each valid exact-hash keeper to a mirrored path beneath
`<output>/mp3/`.

Encoding contract:

- MP3 using `libmp3lame`.
- 320 kbps.
- First audio stream only.
- Source metadata copied.
- ID3v2.3 output.
- Existing non-empty destination MP3s are skipped.
- Partial or failed output files are removed.

The stage command reuses the existing Taghag transcode module rather than
introducing another FFmpeg implementation.

### 5. Validate MP3

Use Taghag's existing `probe_mp3` behavior to verify:

- MP3 codec.
- Decode succeeds.
- Duration is present.
- Bitrate is present and acceptable.

Failed outputs remain reported and are excluded from metadata receipt events.

### 6. Build Metadata Receipt

For every successfully validated MP3, reuse Taghag's existing MP3 identity,
ID3 extraction, genre normalization, observation, and quality-check logic.

The stage receipt contains:

- Stage start and tool versions.
- FLAC discovery and validation records.
- Exact duplicate decisions.
- Metadata-only duplicate candidates.
- Transcode result per keeper.
- MP3 metadata and quality events.
- Final counts and paths to generated reports.

The receipt must not contain credentials or audio data.

## Exit Behavior

Return success when all eligible keeper FLACs are either successfully
transcoded or already have valid destination MP3s.

Return failure when:

- The source does not exist or is not a FLAC/file directory input.
- Required binaries are unavailable.
- Any eligible keeper fails FLAC validation, transcoding, or MP3 validation.

Reports and receipts should still be written for partial failures unless
`--dry-run` is active.

## Verbosity

Verbose output is the default. Print one decision for every discovered FLAC:

- `invalid`
- `exact-duplicate`
- `metadata-candidate`
- `existing`
- `transcode`
- `validated`
- `failed`

Use `--quiet` for summary-only output.

## Testing

Tests must cover:

- Single-file and directory discovery.
- Ignored non-FLAC and junk files.
- FLAC validation success and failure.
- Exact SHA-256 duplicate keeper selection.
- Same ISRC with different checksums remains a review candidate.
- Same artist/title with different checksums remains a review candidate.
- Dry run creates no output directories.
- Exact duplicate loser remains on disk and is not transcoded.
- Mirrored 320 kbps transcode command.
- Existing MP3 resume behavior.
- Failed partial MP3 cleanup.
- MP3 validation before receipt inclusion.
- Receipt contains metadata only.
- No database configuration or client is initialized.

## Deferred Work

- Running Essentia models inside `stage`.
- Uploading receipts or analysis to Supabase.
- Moving duplicate files to Trash or quarantine.
- Acoustic fingerprint dedupe.
- Automatically collapsing ISRC or artist/title candidates.
