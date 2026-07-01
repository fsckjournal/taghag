# Task for Gemini (hag side): resolve the spotify_id→ISRC bridge misses

**Context:** Opus reconstructed the `spotify_id → ISRC → v4 track_id` bridge for the
`automix_payloads` corpus **offline** from the Anna's-Archive Spotify metadata dump
(`kaggle lordpatil/spotify-metadata-by-annas-archive`, `tracks.parquet`), using
`tools/build_spotify_isrc_bridge.py resolve-parquet`. Then `join` produced the
slut-ingest artifact `track_alias_spotify_id.sql`.

**Coverage today:** 22,190 real payloads → 20,180 found in the dump →
**18,492 joined to v4 tracks**. Two gaps remain:

| Gap | Count | Cause |
|-----|-------|-------|
| Not in dump | 2,010 | spotify_id absent from the Anna's-Archive parquet |
| Resolved but ISRC ∉ v4 | 1,688 | ISRC not in `track.isrc` (library gap / mismatch) |

## Your job: close the 2,010 dump-misses via the live Spotify API

The tool already has the fallback path — you just need a valid token.

1. **Re-auth Spotify** (token in `~/.config/tagslut/tokens.json` is expired, no
   refresh_token): run `ts-auth spotify` (needs `SPOTIFY_CLIENT_ID`/`SECRET`).
2. **Resolve the misses.** The `resolve` subcommand is resumable and skips ids
   already in `spotify_isrc_bridge.jsonl`, so it will only fetch the ~2,010 not
   yet present:
   ```
   python3 tools/build_spotify_isrc_bridge.py resolve
   ```
   (`GET /v1/tracks?ids=` batches 50/call → ~40 calls. Handles 401/429.)
3. **Re-join:** `python3 tools/build_spotify_isrc_bridge.py join` — regenerates
   `track_alias_spotify_id.sql` with the newly covered payloads folded in.
4. Report the new coverage number.

## Optional: investigate the 1,688 ISRC-not-in-v4

These resolved to a real ISRC that isn't in `music_v4.db`'s `track.isrc`. Likely a
mix of: (a) library tracks whose ISRC wasn't captured in v4, (b) Spotify returning
a different release's ISRC than the FLAC master. Low priority — spot-check a few
against `pool_metadata_backup.jsonl` / the FLAC tags before deciding if it's worth a
secondary match (e.g. by title+artist fuzzy join).

**Do NOT** write to `music_v4.db` — Taghag is read-only on Tagslut. The bridge's
only output is `track_alias_spotify_id.sql`, handed to the slut side to ingest.
