Goal:
Wire optional `[Tag Evidence JSON]` logs into Taghag without coupling to tagslut.

CLI flag:
`--postman-evidence /path/to/evidence.log`

Parser:
- Use `tools/taghag_import/postman_evidence.py`.
- Parse only lines containing `[Tag Evidence JSON]`.
- Malformed JSON becomes a parser warning or malformed evidence receipt event.
- Do not crash import on malformed evidence.
- Store `matched`, `no_match`, `ambiguous`, and `error` statuses.

Matching:
- Match evidence to MP3 rows by ISRC first.
- If MP3 has no ISRC, do not match by title/artist in v1.
- If `--unsafe-title-artist-evidence-match` is provided, allow experimental matching, but mark `lookup_type unsafe_title_artist` and never merge fields automatically.
- Do not merge `mp3_file` rows because two files share ISRC.
- Do not treat ISRC as identity.

Storage:
- Insert `tag_evidence` for every relevant marker.
- Preserve `raw_marker_json`.
- Store `candidates_json`.
- Store `winning_fields_json`.
- Store `provider`, `lookup_type`, `lookup_key`, `provider_track_id`, `status`, `confidence`, `fetched_at`.

Merging into `dj_tag`:
- Merge provider fields only when confidence and provider authority are clear.
- If evidence is ambiguous, store it but do not update `dj_tag` fields.
- If `no_match` or `error`, store it but do not update `dj_tag` fields.
- Beatport is preferred authority for label and genre/subgenre.
- Spotify or equivalent release provider can inform album/release identity, but only when local release context does not conflict.
- ISRC can support lookup, not automatic row merge.
- If not certain, leave `dj_tag` unchanged and add quality/evidence issue.

Tests:
- matched result
- no_match result
- ambiguous result
- error result
- malformed JSON
- duplicate evidence line
- evidence import never blocks MP3 import
- raw evidence preserved
