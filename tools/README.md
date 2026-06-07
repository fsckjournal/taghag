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
