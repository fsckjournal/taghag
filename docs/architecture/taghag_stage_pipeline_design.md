# Taghag Stage Pipeline Design

## Purpose

Add one Taghag-owned command that accepts a local FLAC file or directory and
processes it into a validated, deduplicated, local FLAC batch with metadata
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
  flac/
  receipts/
    stage.jsonl
  reports/
    audio_duplicates.csv
    metadata_candidates.csv
    summary.json
```

`--dry-run` performs discovery, validation, fingerprinting, duplicate planning,
and reporting without creating the output tree or staging audio.

## Safety Boundary

- Source FLACs are read-only.
- No source file is moved, renamed, trashed, or deleted.
- No Tagslut command, module, configuration, or database is used.
- No Supabase connection is made by `stage`.
- Audio remains on local disks.
- Dedupe is report-only at the source layer.
- Exact audio duplicates are blocked from admission and staging, but remain
  untouched on disk.
- Release, album, and compilation context never permits duplicate audio.
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

Invalid FLACs are never staged. One invalid file does not stop unrelated
valid files.

### 3. Fingerprint And Dedupe

Compute both:

- A full SHA-256 file checksum for provenance and exact-file detection.
- A SHA-256 digest of canonical decoded PCM samples that ignores container
  metadata and embedded artwork.

Files with the same decoded-audio fingerprint are audio duplicates even when
their tags, artwork, release folder, or FLAC container bytes differ.

Within the input batch, select the lexicographically first path as the
deterministic keeper. Other members are reported as blocked audio duplicates
and are not staged.

Before admission, compare each keeper fingerprint against the local source-PCM
fingerprint index written beside previously admitted Taghag FLACs. A decoded
FLAC cannot reproduce the source PCM hash, so the index preserves the
source fingerprint associated with each validated FLAC path. If the audio
already exists there, block the new FLAC instead of creating another FLAC.
Compilation membership and release context do not override this rule. This
comparison is local and does not require Supabase.

Also report, without automatically deduping:

- Repeated non-empty ISRC values with different checksums.
- Repeated normalized artist/title pairs with different checksums.

These are review candidates because releases, edits, masters, and mixes may
legitimately share metadata. They are not duplicates unless their decoded-audio
fingerprints match.

### 4. Stage Output

Copy each valid exact-hash keeper to a mirrored path beneath
`<output>/flac/`.

Copying contract:

- FLAC files are copied verbatim.
- Existing non-empty destination FLACs are skipped.
- Partial or failed output files are removed.

### 5. Validate Output

Use Taghag's existing validation behavior to verify:

- FLAC codec.
- Decode succeeds (`flac -t`).
- Duration is present.
- Bit depth and sample rate are acceptable.

Failed outputs remain reported and are excluded from metadata receipt events.

### 6. Build Metadata Receipt

For every successfully validated and admitted MP3, reuse Taghag's existing MP3
identity, ID3 extraction, genre normalization, observation, and quality-check
logic. Persist its decoded-audio fingerprint in the metadata receipt so later
stage runs can block duplicate audio.

The stage receipt contains:

- Stage start and tool versions.
- FLAC discovery and validation records.
- Audio-duplicate block decisions, including the keeper or existing Taghag FLAC.
- Metadata-only duplicate candidates.
- Transcode result per keeper.
- FLAC metadata and quality events.
- Final counts and paths to generated reports.

The receipt must not contain credentials or audio data.

## Exit Behavior

Return success when every non-duplicate eligible FLAC is either successfully
staged or already has its valid destination FLAC. Blocked audio duplicates
are an expected result and are counted separately, not treated as processing
failures.

Return failure when:

- The source does not exist or is not a FLAC/file directory input.
- Required binaries are unavailable.
- Any eligible keeper fails FLAC validation, staging, or FLAC validation.

Reports and receipts should still be written for partial failures unless
`--dry-run` is active.

## Verbosity

Verbose output is the default. Print one decision for every discovered FLAC:

- `invalid`
- `audio-duplicate-blocked`
- `metadata-candidate`
- `existing`
- `stage`
- `validated`
- `failed`

Use `--quiet` for summary-only output.

## Testing

Tests must cover:

- Single-file and directory discovery.
- Ignored non-FLAC and junk files.
- FLAC validation success and failure.
- Exact-file duplicate keeper selection.
- Decoded-audio duplicates with different tags or artwork are blocked.
- Compilation folders do not permit duplicate audio.
- Audio already present in the Taghag FLAC corpus is blocked.
- Same ISRC with different checksums remains a review candidate.
- Same artist/title with different checksums remains a review candidate.
- Dry run creates no output directories.
- Blocked duplicate remains on disk and is not staged.
- Mirrored 320 kbps stage command.
- Existing FLAC resume behavior.
- Failed partial FLAC cleanup.
- FLAC validation before receipt inclusion.
- Receipt contains metadata only.
- No database configuration or client is initialized.

## Deferred Work

- Running Essentia models inside `stage`.
- Uploading receipts or analysis to Supabase.
- Moving duplicate files to Trash or quarantine.
- Fuzzy perceptual matching of materially different masters or edits.
- Automatically collapsing ISRC or artist/title candidates.
