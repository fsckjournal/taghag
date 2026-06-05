Goal:
Implement a local MP3-only import command.

Command:
`python -m taghag_import.cli import-batch --root /path/to/mp3-batch --run-name "batch-name"`

Flags:
- `--root` required
- `--run-name` optional but recommended
- `--dry-run`
- `--no-upload`
- `--postman-evidence /path/to/evidence.log`
- `--unsafe-title-artist-evidence-match` disabled by default
- `--receipt-dir` optional default `artifacts/import_runs`
- `--verbose`

Local-first rule:
- Always write local JSONL receipt before attempting database upload.
- If Supabase upload fails, receipt still exists.
- Missing tags produce `quality_check` issues, not failed imports.
- Out-of-scope audio files are counted and reported, not imported.
- Importing same folder twice must not duplicate `mp3_file` rows.
- Each run must create `mp3_observation` rows.

Discovery:
- Include only files with suffix `.mp3`, case-insensitive.
- Report these as out-of-scope audio: `.m4a`, `.aac`, `.flac`, `.wav`, `.aiff`, `.aif`, `.alac`, `.ogg`, `.opus`, `.wma`.
- Report other likely audio suffixes as `out_of_scope_audio`.
- Ignore junk: `.DS_Store`, AppleDouble files beginning `._`, temporary files, hidden metadata folders, `__MACOSX`, `.Trashes`, `.Spotlight-V100`, `.fseventsd`.
- Do not delete anything.
- Do not move anything.

MP3 tag extraction:
- Use `mutagen`.
- Extract `artist`, `title`, `album`, `label`, `catalog_number`, `date/release_date/year`, `bpm`, `musical_key`, `genre`, `subgenre`, `isrc`, `compilation`, `rating`, `energy` where present.
- Do not write MP3 tags in the importer v1.
- Do not use comments as Taghag storage.
- Treat MP3 comments as Mixed in Key territory. Read only if useful for energy detection, but never rely on comments as canonical app notes.

Audio probe:
- Use `ffprobe` for `duration_s`, `bitrate_kbps`, `codec`.
- Use `ffmpeg` decode check with null output for `decode_ok` when available.
- If `ffprobe`/`ffmpeg` missing, import still proceeds with quality issue code `tool_missing_ffprobe` or `tool_missing_ffmpeg`.
- `codec` must be `mp3` or quality issue `codec_not_mp3`.
- If suffix is `.mp3` but codec is not `mp3`, create quality issue `codec_mismatch`.

Checksum:
- Prefer full `checksum_sha256`.
- `file_key` should be `sha256:<hex>` when full checksum exists.
- `checksum_prefix` can be first 16 or 24 hex characters.
- If full checksum fails, use documented fallback `file_key = stat:<size>:<mtime_ns>:<normalized_relative_path_hash>`.
- `identity_source` values: `checksum_sha256`, `stat_fallback`.
- `identity_confidence` values: `1.0` for `checksum_sha256`, lower value such as `0.4` for `stat_fallback`.
- Do not use ISRC as `file_key`.

Genre normalization:
- Use `tools/taghag_import/genre.py`.
- Use `tools/taghag_import/genre_rules.json`.
- Store normalized `canonical_genre` and `canonical_subgenre` in `dj_tag`.
- Missing genre/subgenre is a quality issue, not import failure.

Issue codes:
- `missing_artist`
- `missing_title`
- `missing_genre`
- `missing_subgenre`
- `missing_bpm`
- `missing_key`
- `missing_label`
- `missing_isrc`
- `decode_failed`
- `duration_missing`
- `bitrate_missing`
- `bitrate_low`
- `codec_mismatch`
- `checksum_failed`
- `tool_missing_ffprobe`
- `tool_missing_ffmpeg`
- `duplicate_checksum_candidate`
- `out_of_scope_audio`

Receipt:
- Generate `run_id` locally as UUID before scan.
- Write to `artifacts/import_runs/<run_id>/receipt.jsonl`.
- Receipt lines should be stable JSON objects.
- Receipt event types should include `import_run_start`, `mp3_observed`, `out_of_scope_audio`, `quality_check`, `tag_evidence`, `import_run_summary`, `upload_result`.
- Receipt should contain enough information to retry upload without rescanning.
- Receipt should not contain secrets.
- Receipt should not contain raw audio data.

Database upsert:
- Use service role only in local tools.
- Read service credentials from environment, never web env.
- Upsert `import_run` by `id`.
- Upsert `mp3_file` by `owner_user_id + file_key`.
- Insert `mp3_observation` for every run occurrence.
- Upsert `dj_tag` by `owner_user_id + mp3_file_id`.
- Insert `quality_check` per run/file check.
- Insert `tag_evidence` rows if evidence exists.
- Upload must be idempotent for `mp3_file` and `dj_tag`.
- Upload should not dedupe observations across runs.

Environment:
- `TAGHAG_SUPABASE_URL`
- `TAGHAG_SUPABASE_SERVICE_ROLE_KEY` or `TAGHAG_SUPABASE_SECRET_KEY`
- `TAGHAG_OWNER_USER_ID`
- Do not read `VITE_` env vars in tools.
- Do not write service keys to `web/`.

Implementation files:
- `tools/taghag_import/cli.py`
- `tools/taghag_import/discover.py`
- `tools/taghag_import/tags.py`
- `tools/taghag_import/audio_probe.py`
- `tools/taghag_import/genre.py`
- `tools/taghag_import/receipt.py`
- `tools/taghag_import/db_client.py`
- `tools/taghag_import/config.py`
- `tools/tests/test_import_cli.py`
- `tools/tests/test_discover.py`
- `tools/tests/test_receipt.py`
