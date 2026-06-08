# Taghag Import Tooling

Standalone MP3-focused import tooling for the Taghag clean-room metadata app.
## Import Essentia metadata

Validate a local `essentia-lexicon-sidecar/2` artifact and write a metadata-only
receipt:

```bash
taghag-import import-analysis --input /path/to/sidecar.json --no-upload
```

Without `--no-upload`, the command uploads analysis only for tracks already
registered in `mp3_file`. The local MP3 is never uploaded.

## Transcode local FLACs

```bash
taghag-import transcode \
  --source /path/to/flacs \
  --output /path/to/local/mp3s \
  --dry-run
```

Remove `--dry-run` to write mirrored 320 kbps MP3 files. The command is
filesystem-only and does not initialize a database client. It prints every
transcode and existing-file skip by default; use `--quiet` for summary only.

For validation, decoded-audio dedupe, transcode, MP3 verification, reports, and
a receipt in one database-free operation:

```bash
taghag-import stage --source /path/to/flacs --output /path/to/taghag-batch
```

The discovery layer also recognizes `.m3u` playlist files alongside MP3s and
out-of-scope audio, so they are tracked explicitly instead of being silently
ignored.

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
