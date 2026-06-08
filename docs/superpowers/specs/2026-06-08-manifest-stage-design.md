# Manifest-Driven Stage Design

## Purpose

Extend `taghag-import stage` so one run can process an explicit allowlist of
FLAC files drawn from multiple source trees. This supports the Roon compilation
export without scanning unrelated albums and preserves one dedupe domain across
master-library and staging copies.

## Command

```bash
taghag-import stage \
  --manifest /path/to/compilations.jsonl \
  --output /Volumes/LOSSY/taghag/roon-electronic-compilations \
  --dry-run
```

`--source` and `--manifest` are mutually exclusive and exactly one is required.
The existing `--source` behavior remains unchanged.

## Manifest Contract

The manifest is UTF-8 JSONL. Every non-blank line contains:

```json
{"source": "/absolute/path/to/track.flac", "relative_path": "MASTER_LIBRARY/Various Artists/(2024) Album/track.flac"}
```

- `source` must be an existing absolute FLAC file.
- `relative_path` must be a safe relative FLAC path.
- Absolute relative paths, `..` traversal, non-FLAC entries, duplicate source
  rows, and duplicate destination paths are rejected before audio work starts.
- Manifest order does not control keeper selection. Source paths are sorted
  lexicographically so dedupe remains deterministic.

## Pipeline

Manifest entries feed the existing FLAC validation, file hashing, decoded-PCM
hashing, metadata-candidate reporting, transcode, MP3 validation, fingerprint
index, reports, and receipt logic.

The output destination for an entry is:

```text
<output>/mp3/<relative_path with .mp3 suffix>
```

Decoded-audio duplicates are blocked across the complete manifest, including
duplicates that cross release folders or source namespaces. Source files remain
read-only and no database connection is made by `stage`.

## Roon Operating Workflow

1. Join `COMP_ROON.xlsx` to `COMP_ROON.csv` by export row. The workbook supplies
   Roon metadata and paths; the CSV supplies ISRC.
2. Rewrite the Roon mount prefix to `/Volumes/MUSIC`.
3. Resolve stale `/Users/georgeskhawam/Music/staging` paths to their live
   `/Users/g/Music/staging`, `/Volumes/MUSIC/staging`, or master-library copy.
4. Write one private JSONL manifest containing the 1,331 indexed rows. Do not
   commit the manifest because it contains private filesystem paths.
5. Run manifest stage with `--dry-run`. Do not transcode unless every row
   resolves, every manifest entry is valid, and destination paths are unique.
6. Run the same command without `--dry-run` into an isolated output root.
7. Import only `<output>/mp3`; never import source FLAC trees.
8. Generate Postman evidence for unique non-empty ISRC values and attach the
   marker log with `taghag-import import-batch --postman-evidence`.

## Admission Policy

- Decoded-PCM equality is authoritative for lossless source duplicates.
- Roon `Is Dup?`, ISRC, external ID, title, artist, album, filename, and folder
  membership are evidence only.
- Repeated ISRC or normalized artist/title with different PCM remains a review
  candidate and is not automatically removed.
- Invalid FLACs are excluded and reported.
- Only validated 320 kbps MP3 outputs enter the import receipt.

## Testing

Tests cover valid manifests, deterministic sorting, unsafe paths, missing and
non-FLAC sources, duplicate sources, destination collisions, CLI exclusivity,
dry-run behavior, and reuse of the existing stage planner.

## Deferred Work

- Automatic parsing of Roon exports inside the importer.
- Acoustic similarity matching between lossless sources and unrelated existing
  lossy libraries.
- Automatic provider-evidence execution from Taghag.
