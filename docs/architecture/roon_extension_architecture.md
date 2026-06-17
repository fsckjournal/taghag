# Roon Extension Architecture & Headless Intelligence Pivot

Date: 2026-06-15

## 1. Executive Summary

This document details the architectural pivot of the Tagslut/Taghag ecosystem from a cloud-coupled, React-based web application to a fully localized, headless intelligence engine orchestrated by a native Roon Extension.

By abandoning the legacy DJ-centric workflows (Rekordbox XMLs, MP3 transcoding, Vercel deployments, Supabase), we have eliminated massive technical debt. The new architecture leverages Roon as an enterprise-grade, audiophile frontend for browsing and playback, while the local Python intelligence engine operates in the background, triggered seamlessly via the Roon UI.

## 2. System Architecture

The new architecture consists of three distinct layers: the Node.js Roon Extension, the Python IPC Bridge, and the Tagslut Local SQLite backend.

### 2.1 The Roon Extension Frontend (Node.js)
The frontend is a lightweight daemon (`tagslut/roon-extension/app.js`) utilizing the `node-roon-api`. 
- **Transport Subscription:** The extension subscribes to `RoonApiTransport` to maintain a real-time state of the "Now Playing" track across all active listening zones.
- **Browse Actions:** Using `RoonApiBrowse`, the extension injects custom actions into the Roon Settings → Extensions menu.
- **Workflow:** When a user selects "Process Now Playing Track", the extension captures the real-time metadata (Artist, Title, Album) of the currently playing track and passes it to the Python IPC Bridge.

### 2.2 The Python IPC Bridge (`bridge.py`)
Because the `node-roon-api` explicitly hides local filesystem paths (returning abstract `RoonMounts` string mappings), we cannot directly pass a file to the Tagslut backend. 

`bridge.py` acts as the resolution layer:
1. **Invocation:** The Node daemon spawns `bridge.py` via `child_process.spawn()` passing the Artist and Title as CLI arguments.
2. **Reverse Database Lookup:** The bridge connects directly to the local authoritative database (`music_v3.db`). It queries the `track_identity` and `asset_files` tables using fuzzy SQL matching (`LIKE ?`) on the provided metadata.
3. **Path Resolution:** It resolves the exact absolute path of the FLAC file (e.g., `/Volumes/MUSIC/MASTER_LIBRARY/...`).
4. **Subprocess Trigger:** Once the path is resolved, the bridge executes the Tagslut pipeline via a poetry subprocess: `poetry run python -m tagslut tag --force <absolute_file_path>`.

### 2.3 The Tagslut Intelligence Backend
The canonical `tagslut` Python package receives the absolute path and runs the full suite of "Cuecifer" intelligence tools locally:
- **Beatport/Tidal Resolvers:** Fetches canonical ISRC, genres, and energy mappings.
- **Essentia 7D Vectors:** Extracts local acoustic features (danceability, mood, energy).
- **Advanced Cue & Segment Logic:** Maps intro/outro boundaries.
- **ID3/Vorbis Mutation:** Writes the finalized metadata directly to the FLAC file's Vorbis comments.

## 3. Security & Cloud Decoupling

The pivot removes all reliance on Supabase REST clients and remote secrets. 
- **Application Default Credentials:** The system relies entirely on local `gcloud auth application-default login` for any necessary Google Cloud API (Vertex AI) usage, entirely decoupling from the old `TAGHAG_SUPABASE_SERVICE_ROLE_KEY`.
- **Database Authority:** The local SQLite database (`music_v3.db`) is the sole authority. Network outages no longer block library ingestion or intelligence extraction.

## 4. Roon Expansion & Future Horizons

With the foundational pipeline established, the next phases of development will exploit Roon's advanced API capabilities to surface our extracted intelligence directly in the UI.

### 4.1 Bi-Directional Metadata Sync
Currently, the pipeline writes Vorbis comments to the FLAC file, relying on Roon's filesystem watcher to pick up the changes. 
- **Future State:** We will integrate `node-roon-api` endpoints to manipulate the Roon library directly. The Node extension can instantly tag the currently playing track in the Roon database without waiting for a filesystem rescan.

### 4.2 Dynamic UI Rendering via `RoonApiBrowse`
The `RoonApiBrowse` interface supports dynamic list generation. 
- **Future State:** Instead of a static "Process Track" button, the extension can display the live output of the intelligence engine directly in Roon. 
- **Use Case:** Upon processing a track, the Python backend can return JSON to the Node extension, which then populates a Roon menu showing the detected Beatport Sub-genres, the Essentia "Vibe" vector (e.g., "Aggressive: 85%"), and the Camelot Key.

### 4.3 Autonomous Setlist Generation (Neighborhood Crates)
Leveraging the Beam Search pathfinder and 7D sonic vectors developed in the Cuecifer sprint, we can create an action titled "Generate Sonic Vibe Playlist".
- The Python backend calculates a mathematically cohesive transition path starting from the "Now Playing" track.
- The Node extension receives the list of track IDs and uses the Roon API to instantly enqueue them or create a persistent Roon Playlist.

## 5. Conclusion
The Roon Extension pivot solves the latency, maintenance, and UX friction of the legacy web architecture. By pushing Roon to the front and SQLite to the back, Tagslut becomes a hyper-localized, instantaneous AI assistant for audiophile library curation.
