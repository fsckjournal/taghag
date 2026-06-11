### Environment mapping

| legacy_key | canonical_key | group |
| --- | --- | --- |
| AUTH_URL | AUTH_OAUTH_AUTHORIZE_URL | AUTH |
| AUTO_APPROVE_THRESHOLD | MISC_AUTO_APPROVE_THRESHOLD | MISC |
| CLIENT_ID | AUTH_OAUTH_CLIENT_ID | AUTH |
| DATABASE_URL | DB_POSTGRES_URL | DB |
| DISCARD_ROOT | PATHS_DISCARD_ROOT | PATHS |
| FIX_ROOT | PATHS_FIX_ROOT | PATHS |
| LIBRARY_ROOT | PATHS_LIBRARY_ROOT | PATHS |
| LOCAL_STAGING | PATHS_LOCAL_STAGING_ROOT | PATHS |
| MASTER_LIBRARY | PATHS_MASTER_LIBRARY_ROOT | PATHS |
| MP3_LIBRARY | PATHS_MP3_LIBRARY_ROOT | PATHS |
| OPENAI_API_KEY | OPENAI_API_KEY | OPENAI |
| PLAYLIST_ROOT | PATHS_PLAYLIST_ROOT | PATHS |
| PREFER_HIGH_BITRATE | MISC_PREFER_HIGH_BITRATE | MISC |
| PREFER_HIGH_SAMPLE_RATE | MISC_PREFER_HIGH_SAMPLE_RATE | MISC |
| PREFER_VALID_INTEGRITY | MISC_PREFER_VALID_INTEGRITY | MISC |
| QUARANTINE_RETENTION_DAYS | MISC_QUARANTINE_RETENTION_DAYS | MISC |
| QUARANTINE_ROOT | PATHS_QUARANTINE_ROOT | PATHS |
| REDIRECT_URI | AUTH_OAUTH_REDIRECT_URI | AUTH |
| ROON_PLAYLIST_PREFIX | STREAMING_ROON_PLAYLIST_PREFIX | STREAMING |
| ROOT_BP | PATHS_BEATPORT_DOWNLOAD_ROOT | PATHS |
| ROOT_TD | PATHS_TIDAL_DOWNLOAD_ROOT | PATHS |
| SCAN_CHECK_HASH | MISC_SCAN_CHECK_HASH | MISC |
| SCAN_CHECK_INTEGRITY | MISC_SCAN_CHECK_INTEGRITY | MISC |
| SCAN_INCREMENTAL | MISC_SCAN_INCREMENTAL | MISC |
| SCAN_PROGRESS_INTERVAL | MISC_SCAN_PROGRESS_INTERVAL | MISC |
| SCAN_WORKERS | MISC_SCAN_WORKERS | MISC |
| SPOTIFY_ACCOUNTS_URL | STREAMING_SPOTIFY_ACCOUNTS_URL | STREAMING |
| SPOTIFY_API_BASE_URL | STREAMING_SPOTIFY_API_BASE_URL | STREAMING |
| SPOTIFY_CLIENT_ID | STREAMING_SPOTIFY_CLIENT_ID | STREAMING |
| SPOTIFY_CLIENT_SECRET | STREAMING_SPOTIFY_CLIENT_SECRET | STREAMING |
| STAGING_ROOT | PATHS_STAGING_ROOT | PATHS |
| SUPABASE_CLIENT_API_KEY | SUPABASE_API_KEY | SUPABASE |
| SUPABASE_URL | SUPABASE_URL | SUPABASE |
| TAGSLUT_ARTIFACTS | PATHS_ARTIFACTS_ROOT | PATHS |
| TAGSLUT_DB | DB_SQLITE_PATH | DB |
| TAGSLUT_REPORTS | PATHS_REPORTS_ROOT | PATHS |
| TIDAL_CLIENT_ID | STREAMING_TIDAL_CLIENT_ID | STREAMING |
| TIDAL_CLIENT_SECRET | STREAMING_TIDAL_CLIENT_SECRET | STREAMING |
| TIDDL_DOWNLOAD_ROOT | PATHS_TIDDL_DOWNLOAD_ROOT | PATHS |
| TOKEN_URL | AUTH_OAUTH_TOKEN_URL | AUTH |
| TURSO_AUTH_TOKEN | TURSO_AUTH_TOKEN | TURSO |
| TURSO_URL | TURSO_URL | TURSO |
| VOLUME_LIBRARY | PATHS_VOLUME_LIBRARY_ROOT | PATHS |
| VOLUME_QUARANTINE | PATHS_VOLUME_QUARANTINE_ROOT | PATHS |
| VOLUME_STAGING | PATHS_VOLUME_STAGING_ROOT | PATHS |
| VOLUME_SUSPECT | PATHS_VOLUME_SUSPECT_ROOT | PATHS |
| VOLUME_WORK | PATHS_VOLUME_WORK_ROOT | PATHS |

### Script inventory

| path | status | reason |
| --- | --- | --- |
| beatport_match.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| clean_friday.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| clean_xml.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| do_restructure.py | ARCHIVE | One-off migration note or local restructuring helper that should stay as reference only. |
| essentia_sidecar_patch.py | ARCHIVE | One-off migration note or local restructuring helper that should stay as reference only. |
| finalize_friday.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| inject_djpool.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| inject_staging.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| lexicon_vs_reccobeats_join.py | ARCHIVE | One-off migration note or local restructuring helper that should stay as reference only. |
| postman_tag_resolver.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| rekordbox_blank_215_keys.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| repair_friday.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| resolve_dupes.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/analyze_missing_tracks.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/apply_genre_corrections.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/automate_music_tagging.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/backfill_compilation_upc.py | PROMOTE | Head lines reference forbidden legacy concepts, so the logic needs a clean-room port. |
| scripts/backfill_missing_dates.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/backfill_track_identity_upc.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/backfill_v3_identity_links.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/build_friday_crates.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/check_cli_docs_consistency.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/check_hardcoded_paths.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/check_kaggle_cli.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/clean_missing_csv.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/cleanup_suffix_dupes.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/compilation_workflow.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/consolidate_mp3_leftovers.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/consolidate_mp3lib.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/db/check_promotion_preferred_invariant_v3.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/db/compute_identity_status_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/db/compute_preferred_asset_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/db/doctor_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/db/merge_identities_by_beatport_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/db/migrate_v2_to_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/db/plan_backfill_identity_conflicts_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/db/verify_v3_migration.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/dedupe_against_pool.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/dedupe_excel_to_m3u.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/dedupe_library_xml.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/delete_tidal_root_m4a_duplicates.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/dj-single-track.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/dj/build_export_v3.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/dj/build_pool_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/dj/dj_yes_transcode.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/dj/export_candidates_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/dj/export_ready_v3.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/dj/extract_dj_candidates_from_DJ.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/dj/profile_v3.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/export_dj_tags.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/export_full_tags.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/export_playlist_files.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/extract_tracklists_from_links.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/filter_spotify_against_db.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/filter_valid_log_hits.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/fix_playlist_album_contamination.py | PROMOTE | Head lines reference forbidden legacy concepts, so the logic needs a clean-room port. |
| scripts/friday_candidates_xml.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/friday_lexicon_reconcile.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/friday_metadata_db.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/friday_pool_build.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/get_apple_track_isrc.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/get_apple_track_isrc.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/gig/00_verify_environment.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/gig/01_plan_mode.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/gig/02_execute.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/gig/03_validate_pool.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/inject_friday_crates.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/library_export.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/library_xml_export_m3u.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/lint_policy_profiles.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/long_sleep_scan.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/make_bundle.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/map_master_library.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/master_tag_remediation.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/match_history_m3u_to_master_flac.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/match_missing_to_spotify_then_roon.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/match_rekordbox_to_db.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/match_therest_to_roon_isrc.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/migrate_legacy_db.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/mp3_leftovers_extract.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/mp3_library_remediate.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/mypy_baseline_check.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/normalize_genres.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/process_dedupe.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/push_then_post_work.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/rebuild_playlist_from_exports.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/rebuild_pool_library.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/reconcile_playlist_scan_loose.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/recover_missing_tracks.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/reenrich_dj_genres.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/refresh_qobuz_token.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/rekordbox/build_rekordbox_xml_from_pool.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/rekordbox/rb_edit_comments.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/rekordbox/rb_fix_xml_genre.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/rekordbox/rekordbox_recovery_and_cleaning.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/rekordbox/rewrite_rekordbox_db_paths.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/rekordbox/rewrite_rekordbox_xml_paths.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/render_playlist_scan_m3u8.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/requery_beatport.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/resolve_lossless_winner.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/resolve_lossless_winner.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/resolve_missing_against_paths.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/resolve_missing_m3u8.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/resolve_missing_m3u8_against_roon_xlsx.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/run_backlog.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/run_staging_intake.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/run_staging_process_roots.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/scan_audio_metadata_to_db.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/scrub_mp3_tags_keep_only.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/seed_dj_blocklists.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/spotiflacnext_pretranscode_check.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/spotify_dedup_playlist.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/sync_tokens_to_postman_env.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/tagslut-supabase-check.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/tagslut_cli.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/tagslut_rls_apply.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/test-tidal-metadata.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/tidal-auth-flow.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/tidal-get-token.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/transcode_excel_backlog.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/transcode_m3u_to_mp3_macos.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/transcode_m4a_to_flac_lossless.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/triage_tidal_staging.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| scripts/validate_v3_dual_write_parity.py | IMPORT | Depends on tagslut-only Python modules that do not exist in taghag. |
| scripts/verify_transcodes.sh | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |
| tagslut_flac_to_mp3.py | PROMOTE | Reusable operational utility with no direct tagslut package dependency. |

### Postman collections

| current filename | proposed new filename | environment variables referenced | action |
| --- | --- | --- | --- |
| gig_mp3_decode_error_size_anomaly.json | gig_mp3_decode_error_size_anomaly.json | - | ARCHIVE |
| gig_mp3_decode_error_size_anomaly_authority_summary.json | gig_mp3_decode_error_size_anomaly_authority_summary.json | - | ARCHIVE |
| gig_mp3_decode_error_size_anomaly_catalog_retry.json | gig_mp3_decode_error_size_anomaly_catalog_retry.json | - | ARCHIVE |
| gig_mp3_decode_error_size_anomaly_catalog_retry_authority_summary.json | gig_mp3_decode_error_size_anomaly_catalog_retry_authority_summary.json | - | ARCHIVE |
| gig_mp3_decode_error_size_anomaly_final_authority.json | gig_mp3_decode_error_size_anomaly_final_authority.json | - | ARCHIVE |
| environment.secrets.example.json | provider-secrets.template.json | beatport_access_token, beatport_refresh_token, beatport_token_expiry, spotify_access_token, spotify_client_secret, spotify_token_expiry, tidal_access_token, tidal_refresh_token, tidal_token_expiry | RENAME_AND_REMAP_VARS |
| tagslut-env.environment.json | provider-auth.environment.json | baseUrl_spotify, beatport_access_token, beatport_client_id, beatport_password, beatport_refresh_token, beatport_token_expiry, beatport_token_type, beatport_token_url, beatport_username, client_id, client_secret, grant_type, qobuz_app_id, qobuz_auth_token, qobuz_user_auth_token, spotify_accounts_url, spotify_api_base_url, spotify_client_id, spotify_client_secret, spotify_token_url, tidal_access_token, tidal_client_id, tidal_client_secret, tidal_refresh_token, tidal_refresh_url, tidal_token_expiry, tidal_token_type | RENAME_AND_REMAP_VARS |
| tagslut.environment.json | provider-runtime.environment.json | DATABASE_URL, MASTER_LIBRARY, PLAYLIST_ROOT, TAGSLUT_DB, VOLUME_STAGING, access_token, baseUrl_spotify, baseUrl_tidal, beatport_access_token, beatport_authorization_code, beatport_client_id, beatport_client_secret, beatport_djapp_client_id, beatport_input_url, beatport_password, beatport_pkce_code_verifier, beatport_redirect_uri, beatport_refresh_token, beatport_token_expiry, beatport_token_type, beatport_token_url, beatport_username, client_id, client_secret, countryCode, limit, local_album, local_folder, lookup_isrc, lookup_upc, market, qobuz_app_id, qobuz_auth_token, qobuz_limit, qobuz_user_auth_token, runner_dataset_path, spotify_access_token, spotify_accounts_url, spotify_album_id, spotify_api_base_url, spotify_client_id, spotify_client_secret, spotify_limit, spotify_market, spotify_token_expiry, spotify_token_type, spotify_token_url, tidal_access_token, tidal_authorization_code, tidal_client_id, tidal_client_secret, tidal_country_code, tidal_device_code, tidal_include, tidal_pkce_code_verifier, tidal_redirect_uri, tidal_refresh_token, tidal_refresh_url, tidal_token_expiry, tidal_token_type, token_expiry, token_type | RENAME_AND_REMAP_VARS |
| spotify-tagslut-api.postman_collection.json | spotify-provider-api.postman_collection.json | access_token, album_id, client_id, client_secret, include_external, limit, market, offset, refresh_token, search_query, spotify_accounts_url, spotify_api_base_url | RENAME_AND_REMAP_VARS |

### Supabase strategy

# Supabase migration plan

## 1. Legacy migrations

| filename | estimated intent | action |
| --- | --- | --- |
| 20260315154756_tagslut_schema.sql | bootstrap legacy public schema | SUPERSEDED_BY_TAGHAG |
| 20260315180550_enable_rls.sql | enable row-level security on legacy tables | BACKPORT |
| 20260315203836_rls_policies_service_role.sql | add early service-role RLS policies | REFERENCE_ONLY |
| 20260322000000_add_ingestion_provenance.sql | add ingestion provenance tables and writes | SUPERSEDED_BY_TAGHAG |
| 20260322100000_confidence_tier_check.sql | add confidence-tier constraint hardening | REFERENCE_ONLY |
| 20260516120000_set_security_invoker_on_public_views.sql | set security invoker on public views | REFERENCE_ONLY |
| 20260516165640_rls_policies_service_role.sql | refresh service-role RLS policies | BACKPORT |
| 20260516225500_sync_sqlite_v23_parity.sql | align Supabase tables with SQLite v23 parity work | REFERENCE_ONLY |
| 20260531082956_add_reorder_dj_set_tracks_rpc.sql | add crate or DJ set reorder RPC support | BACKPORT |
| 20260601003000_add_planner_compat_contract.sql | add planner compatibility contract surface | REFERENCE_ONLY |

## 2. taghag config.toml

```toml
project_id = "TOKEN"

[api]
enabled = true
port = 54321
schemas = ["public", "graphql_public"]
extra_search_path = ["public", "extensions"]
max_rows = 1000

[db]
port = 54322
shadow_port = 54320
major_version = 17

[db.migrations]
enabled = true
schema_paths = []

[db.seed]
enabled = true
sql_paths = ["./seed.sql"]

[realtime]
enabled = true

[studio]
enabled = true
port = 54323
api_url = "http://127.0.0.1"
openai_api_key = "env(OPENAI_API_KEY)"

[auth]
enabled = true
site_url = "http://127.0.0.1:5173"
additional_redirect_urls = ["http://127.0.0.1:5173", "http://localhost:5173"]
jwt_expiry = 3600
enable_refresh_token_rotation = true
refresh_token_reuse_interval = 10
enable_signup = true
enable_anonymous_sign_ins = false
```

## 3. Backfill strategy

1. Open `music_v3.db` in read-only mode and create a durable `import_run` row keyed by a migration-specific `run_name` so every subsequent write is resumable.
2. Build a deterministic source snapshot keyed by legacy path, file size, mtime, checksum, and any existing stable identity tokens before touching Supabase.
3. Upsert `audio_file` on `(owner_user_id, file_key)` using a file key derived from the legacy canonical path or checksum so reruns rewrite the same row instead of duplicating it.
4. For every scanned source row, upsert one `audio_observation` tied to the active `import_run`, carrying observed path, size, mtime, checksum, status, and any issue JSON gathered during extraction.
5. Map legacy musical metadata into `dj_tag` with one row per `audio_file`, preserving artist, title, album, label, catalog number, release date, year, bpm, musical key, canonical genres, ISRC, rating, energy, role, notes, and override flags where present.
6. Convert provider lookups or historical enrichment blobs into `tag_evidence`, normalizing provider name, lookup type, lookup key, provider track id, status, confidence, winning fields, candidate sets, and raw marker JSON.
7. Translate scan and validation outputs into `quality_check`, using JSON arrays for missing-tag flags, duplicate flags, and issue codes so repeated runs can upsert by `(owner_user_id, audio_file_id, checked_at, tool_name)` or replace the latest record per tool.
8. Backfill playlists or set folders into `crate`, then populate `crate_track` with stable `(crate_id, audio_file_id)` membership and deterministic `position` values so reruns only reorder when the source order changed.
9. Import any persisted saved filters or dashboard layouts into `saved_view`, storing route, filter, sort, and chart JSON exactly once per `(owner_user_id, name)`.
10. Load any Essentia or Magikbox sidecars into `track_analysis` only after the parent `audio_file` rows exist, using the existing unique constraint on `(owner_user_id, audio_file_id, schema_name, source_artifact_sha256)` for idempotency.
11. Run post-load verification queries for row counts, nullability, duplicate keys, and foreign-key coverage, then mark the `import_run` as `completed` only when every table-level reconciliation passes.

### Legacy reference

  tagslut at /Users/g/Projects/tagslut is archived read-only.
  All active development continues from taghag.
  Do not push to tagslut.

### How to run a legacy script

  cd /Users/g/Projects/taghag
  source migration/legacy_env.sh
  python3 legacy/scripts/<script_name>.py
