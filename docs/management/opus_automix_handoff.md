# Automix Supabase Integration Plan (Opus Handoff)

**Hello Opus!** 
This document was prepared by a previous Antigravity session to cleanly hand off the context regarding the `automix_payloads` data mine. 

## Context
During this sprint, we successfully scraped 22,629 Automix `.analyzer.json` payloads (Spotify audio features) and safely stored them in the `automix_payloads/` directory at the root of the repository. All scraping and data acquisition scripts have been scrubbed from the repository and vaulted securely.

## The Goal
The user wants to push these Spotify/Automix features to the Supabase Postgres instance so they can be queried just like the `apple_track_analysis` data. 

## Implementation Strategy

### 1. Database Schema
Currently, there is no schema for Spotify data. You need to create a new migration (e.g., `supabase/migrations/20260630000000_spotify_track_analysis_schema.sql`) to define a `spotify_track_analysis` table.
- This table must include `owner_user_id` and `audio_file_id` (UUID) for referential integrity.
- You should extract top-level track features into strongly typed columns:
  - `duration` (float)
  - `loudness` (float)
  - `tempo` (float)
  - `tempo_confidence` (float)
  - `time_signature` (integer)
  - `time_signature_confidence` (float)
  - `key` (integer)
  - `key_confidence` (float)
  - `mode` (integer)
  - `mode_confidence` (float)
- The massive `echoprintstring`, `synchstring`, and `rhythmstring` fields should be stored in a `jsonb` column (or omitted entirely if the user doesn't need them for the offline engine).

### 2. ID Mapping
The 22,629 payload files are named after their respective Spotify/ISRC/Qobuz IDs (e.g., `0W0s27FypnkXjJTJKUAnx0.json`).
- Supabase requires an `audio_file_id` (a UUID representing a tracked FLAC file in `audio_file`).
- You will need to resolve these Spotify IDs to their corresponding `audio_file_id` before uploading them.

### 3. db_client.py Uploader
Add a new method `upsert_spotify_track_analysis` to `tools/taghag_import/db_client.py` that mimics `upsert_apple_track_analysis`.

### 4. Batch Uploader Script
Write a one-off script to iterate through `/Users/g/Projects/tag/hag/automix_payloads/`, batch the JSON files, resolve the IDs, and call the new `db_client.py` method to push them to Supabase via PostgREST.
