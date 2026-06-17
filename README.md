# Taghag

Taghag is a clean-room, multi-format private DJ metadata app. It keeps audio files on local disks and stores only metadata, tagging decisions, crate organization, and import receipts in the database.

## What Taghag is

Taghag is a private control surface for DJs who want to scan local audio libraries, normalize metadata, review tag evidence, and organize tracks into crates and saved views.

## What it refuses to inherit

This repository does not inherit legacy schema design, code imports, or mixed-format assumptions from the old tagslut project. Taghag is a fresh schema and app boundary built specifically for audio-first metadata workflows.

## Multi-format scope

Taghag accepts `.mp3` and `.flac` files, including robust local staging and deduplication for FLAC-to-MP3 transcoding.

## Metadata-only database model

The database stores import runs, audio file metadata, DJ tags, tag evidence, quality checks, crates, crate membership, and saved views. It does not store binary audio assets.

## Local files remain local

Taghag never uploads or deletes local audio files. Import receipts reference local paths for operator use, while the database stores metadata only.

## Server-only key never goes to frontend

The importer reads server-side upload credentials from environment variables only. Frontend code must use frontend-safe variables only and must never embed a server-only key.

The legacy DJ-slice backfill extractor also needs a Postgres connection string in `DB_POSTGRES_URL` or `TAGHAG_DB_POSTGRES_URL` so it can write through `psycopg2`.

## Source-controlled migrations

All SQL changes belong in source-controlled migrations under [supabase/migrations](/Users/g/Projects/taghag/supabase/migrations).

## Supabase setup assumptions

Taghag is Supabase-backed metadata software. It is not a SQLite app unless a future task explicitly changes that direction. Local audio files remain local, while Supabase stores metadata, tags, crates, and import receipts.

Docker is required only when running the local Supabase CLI stack. In particular, verification with `supabase db reset` expects Docker because it starts and resets a local Supabase/Postgres environment.

To avoid Docker during early development, use a free hosted Supabase dev project. Hosted Supabase has a free tier, and Taghag's metadata-only workload should fit that path initially. Apply the SQL files in [supabase/migrations](/Users/g/Projects/taghag/supabase/migrations) to the hosted project, then configure the local env values from [.env.example](/Users/g/Projects/taghag/.env.example). Do not put service-role keys in frontend env vars.

## Active docs

Use these files as the active project docs for future agent sessions:

- [README.md](/Users/g/Projects/taghag/README.md)
- [AGENT.md](/Users/g/Projects/taghag/AGENT.md)
- [docs/TAGHAG_HANDOVER.md](/Users/g/Projects/taghag/docs/TAGHAG_HANDOVER.md)
- [docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md](/Users/g/Projects/taghag/docs/TAGHAG_MASTER_IMPLEMENTATION_PLAN.md)
- [docs/TAGHAG_CUECIFER_SUPABASE_DATABASE.md](/Users/g/Projects/taghag/docs/TAGHAG_CUECIFER_SUPABASE_DATABASE.md)
- [.github/prompts/README.md](/Users/g/Projects/taghag/.github/prompts/README.md)

## Prompt library

Reusable project prompts live under [.github/prompts](/Users/g/Projects/taghag/.github/prompts).

Prompt filename template:
- `taghag-<order>-<scope>.prompt.md`

Example names:
- `taghag-00-master-implementation-plan.prompt.md`
- `taghag-03-import-cli.prompt.md`
- `taghag-09-verification-checklist.prompt.md`

## Initial developer setup

1. Create a Python virtual environment for the importer and install [tools/pyproject.toml](/Users/g/Projects/taghag/tools/pyproject.toml).
2. Copy [.env.example](/Users/g/Projects/taghag/.env.example) to a local env file and fill in server-side values outside the frontend.
3. Apply [supabase/migrations](/Users/g/Projects/taghag/supabase/migrations) to either a local Supabase CLI project or a free hosted Supabase dev project.
4. Install the frontend dependencies in [web/package.json](/Users/g/Projects/taghag/web/package.json).

Example:

```bash
cd tools && python3 -m venv .venv && source .venv/bin/activate && pip install -e .
pytest tests
cd ../web && npm install && npm run build
```

## First import flow

Scan a local audio tree, write a JSONL receipt, and skip upload:

```bash
cd tools
taghag-import import-batch --root /path/to/audio-library --run-name first-import --no-upload
```

Upload uses the server-side Taghag env vars from [.env.example](/Users/g/Projects/taghag/.env.example):

```bash
taghag-import import-batch --root /path/to/audio-library --run-name first-import
```

## Legacy DJ slice backfill

Extract the core MP3 DJ slice from a legacy `music_v3.db` snapshot and upsert it into the clean-room `audio_file` and `dj_tag` tables:

```bash
cd tools
taghag-import extract-dj-slice --sqlite-db /path/to/music_v3.db --verbose
```

This path opens the SQLite source in read-only mode and requires `DB_POSTGRES_URL` or `TAGHAG_DB_POSTGRES_URL` plus `TAGHAG_OWNER_USER_ID`.

## Audio audit and tag tools

Write metadata-only JSONL, CSV, and summary reports for a local audio tree:

```bash
cd tools
taghag-import audit-mp3 \
  --root /path/to/audio-library \
  --output-dir ../artifacts/audio_audit/manual-check
```

The audit reuses Taghag discovery, ID3 extraction, genre normalization,
`ffprobe`, and `ffmpeg` decode checks. It reports playlists and unsupported
audio separately and never copies audio bytes into reports.

Dump readable ID3/Vorbis frames for explicit audio files or a whole audio root:

```bash
taghag-import dump-tags \
  --root /path/to/audio-library \
  --out ../artifacts/mp3_tags.jsonl
```

Binary frames such as artwork are summarized by byte count. To plan selective
ID3 updates, create a CSV with `path,field,value` columns:

```bash
taghag-import write-tags --plan /path/to/updates.csv
```

`write-tags` is dry-run by default. Add `--execute` to save changes and
`--force` only when requested fields should replace existing values. Unknown
frames and existing comments are preserved; Taghag never writes receipts or
debug data into comments.

## Provider evidence

Run exact Postman ISRC lookups and write a marker log compatible with
`import-batch --postman-evidence`:

```bash
taghag-import provider-evidence \
  --isrc USABC2400001 \
  --collection /path/to/provider-evidence-collection \
  --environment /path/to/provider-environment.json \
  --output-dir ../artifacts/provider_evidence/manual-check
```

Set `TAGHAG_POSTMAN_COLLECTION`, `TAGHAG_POSTMAN_ENVIRONMENT`, and optionally
`TAGHAG_POSTMAN_BIN` to avoid repeating those paths. The runner verifies the
real binary, collection, and environment, targets the four exact Spotify,
TIDAL, Beatport, and Qobuz ISRC requests, and writes only normalized evidence
markers plus a metadata-only summary.

For a long provider batch, verify commands without launching Postman:

```bash
taghag-import provider-evidence \
  --isrc-file /path/to/isrcs.txt \
  --collection /path/to/provider-evidence-collection \
  --environment /path/to/provider-environment.json \
  --prepare-only
```

Run the prepared command directly as the operator rather than leaving an agent
session polling a network-bound batch. Feed a completed evidence log into the
normal receipt-first importer:

```bash
taghag-import import-batch \
  --root /path/to/mp3-library \
  --postman-evidence ../artifacts/provider_evidence/manual-check/provider_evidence.log \
  --no-upload
```

## Essentia metadata import

Taghag accepts `essentia-lexicon-sidecar/2` analysis artifacts and uploads only
metadata. MP3 audio remains on local disks.

Each track should include its Taghag `file_key`. For migration artifacts that
predate Taghag, the importer can calculate the key when the referenced local
audio path still exists.

Write and inspect a receipt without contacting Supabase:

```bash
cd tools
taghag-import import-analysis \
  --input /path/to/sidecar.json \
  --receipt-dir ../artifacts/analysis_imports \
  --no-upload
```

Remove `--no-upload` to resolve each `file_key` against an existing `audio_file`
row and upsert the five Cuecifer attributes, genre candidates, model metadata,
and source-artifact digest into `track_analysis`. Audio bytes, model inputs,
and temporary analysis files are never included in database payloads.

## Cuecifer engine and sync tools

The Cuecifer engine now reads `track_analysis` and `dj_tag` from Postgres,
normalizes a seven-dimensional vector, and upserts the result into
`track_embedding`.

Run it from `tools/` with the owner-scoped database env vars:

```bash
cd tools
python cuecifer/sonic_discovery.py recompute-all
python cuecifer/sonic_discovery.py similar --path /absolute/path/to/track.mp3 --limit 10
python cuecifer/crates.py --seed /absolute/path/to/track.mp3 --limit 30 --out-dir ../artifacts/crates
python cuecifer/map.py --out-dir ../artifacts/cuecifer_map
python cuecifer/human_correction.py apply --music-dir /Volumes/LOSSY/taghag/mp3s --execute
python cuecifer/human_correction.py audit --out ../artifacts/manual_review_needed.csv
python cuecifer/sync_vibes.py --execute
```

`human_correction.py` upserts pinned rows into `track_curation`, and
`sync_vibes.py` writes the resolved vibes back into local MP3 comments.

## Local FLAC-to-MP3 transcode

Taghag includes a database-free transcode command. It recursively discovers
FLAC files, mirrors their folder structure, copies source metadata through
FFmpeg, and writes 320 kbps MP3 files. Existing non-empty MP3 files are skipped.
This is local preprocessing that produces MP3 inputs; FLAC remains outside
Taghag database intake.

Preview the Qobuz staging batch without writing anything:

```bash
cd tools
taghag-import transcode \
  --source /Volumes/MUSIC/staging/StreamripDownloads-2/Qobuz \
  --dry-run
```

Set `TAGHAG_MP3_OUTPUT_ROOT=/Volumes/LOSSY/taghag` in your local `.env` to
make that the default output root for both `transcode` and `stage`. Remove
`--dry-run` to transcode. This command does not read or write Tagslut,
Supabase, or any other database. Per-file progress is printed by default; add
`--quiet` for summary-only output.

## End-to-end FLAC staging

Use `stage` for the practical A-to-Z workflow:

```bash
cd tools
taghag-import stage \
  --source /Volumes/MUSIC/staging/StreamripDownloads-2/Qobuz \
```

The command validates FLACs, hashes canonical decoded PCM, blocks duplicate
audio even across compilations, transcodes admitted tracks, validates MP3s, and
writes local reports and a metadata-only receipt. Source FLACs are never moved
or deleted, and neither Tagslut nor Supabase is accessed. Add `--dry-run` to
perform the full validation and dedupe plan without writing the output tree.

For an explicit allowlist spanning multiple source folders, provide a JSONL
manifest instead of `--source`:

```bash
cd tools
taghag-import stage \
  --manifest /path/to/selected-flacs.jsonl \
  --output /Volumes/LOSSY/taghag/selected-batch \
  --dry-run
```

Each non-blank line must contain an existing absolute FLAC `source` and a safe
relative FLAC `relative_path`:

```json
{"source":"/absolute/path/track.flac","relative_path":"release/track.flac"}
```

One manifest is planned as one decoded-audio dedupe cohort. Source files remain
read-only.

## Verification

Run `supabase db reset` only when using the local Supabase CLI stack with Docker available. For a hosted dev project, verify by applying the source-controlled migrations to that project and running the validation SQL from the implementation plan against the hosted database.

```bash
python tools/audit_cleanroom.py
pytest tools/tests -q
supabase db reset
cd web && npm run build
```
