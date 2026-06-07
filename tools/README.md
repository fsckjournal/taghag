# Taghag Import Tooling

Standalone MP3-only import tooling for the Taghag clean-room metadata app.
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
