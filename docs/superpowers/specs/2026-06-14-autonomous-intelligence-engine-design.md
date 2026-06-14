# Autonomous Intelligence Engine Export Design

## 1. Consolidated Report: A to Z of the "Magikbox" Sprint

### 1.1 The Theoretical Beginning
The "Magikbox" initiative started in `taghag` as an experimental framework to generate autonomous, superhuman DJ transitions. The core thesis was that if we could merge structural data (intro/outro markers), harmonic energy mapping, and acoustic "vibe" analysis, we could computationally sequence a setlist better than human intuition. 

### 1.2 The "Trinity" of Reverse-Engineering
During Phase 2, we moved from theory to hard production by reverse-engineering three disparate intelligence layers:
- **Structural (Mixonset Sandbox):** We decrypted the proprietary local `.dat` files from the Offtrack/Mixonset application. We built translation engines to map their integer key codes to standard Camelot formats and extracted precise physical beat grids and segment boundaries (intros, drops, outros).
- **Acoustic (Essentia 7D):** We orchestrated local Python scripts utilizing the Essentia audio analysis library. By running this against our physical audio segments, we computed 7-dimensional `control_vec` embeddings (danceability, mood, energy) to map the acoustic "vibe" of tracks mathematically.
- **Harmonic Energy (Beatport iWebDJ):** By intercepting raw `.har` network traffic during live Beatport DJ sessions, we decoded the undocumented `metadata.php` `iwebdj` payload. We extracted mathematical energy envelopes (`a0`-`a5`), dynamic beat markers (`bm0`), and structural timelines.

### 1.3 The Flaw & The Pivot
While the intelligence extraction was a monumental success, the surrounding infrastructure became a liability. The `taghag` repository was heavily coupled to:
1. **Supabase/Vercel:** Cloud-based postgres and React frontends that drastically increased latency and development friction.
2. **MP3s & Rekordbox:** Legacy paradigms that constrained audio fidelity and forced us to rely on the DJ software sandbox.

Since we have now pivoted to a pure **FLAC/Roon/Local SQLite** architecture in `tagslut`, the cloud dependencies are dead weight, and the "Magikbox" codename (referencing Rekordbox) is absurd. 

This document serves as the clean-room export design to port the raw intelligence engine out of `taghag` and back into `tagslut` under a new naming convention.

---

## 2. Export Purpose & Scope

The purpose of this export is to isolate the useful Python intelligence logic (Mixonset, Essentia, Beatport decoders, and Beam Search Pathfinder) and wire them directly into the `tagslut` SQLite/FLAC architecture. 

The exported tools must run natively inside the `tagslut` backend. They must reuse the existing local SQLite `music_v3.db` and drop all runtime dependencies on Supabase schemas, REST clients, Vercel infrastructure, and DJ Beatport `.har` network trace scratching.

## 3. Existing Module Reuse & MP3 Portability

While the goal is to support FLAC, any generic extraction or tagging tool built in `taghag` that can safely operate on FLAC or general audio files must be preserved. 

**Modules to directly reuse/port to `tagslut`:**
- `tools/taghag_import/advanced_cue_planner.py`: The core Beam Search routing logic for generating setlists.
- `tools/taghag_import/beatport_resolver.py`: The iWebDJ decoding matrix and catalog search.
- `tools/taghag_import/essentia_adapter.py` & `sonic_discovery.py`: Vibe extraction.
- `tools/taghag_import/mixonset.py`: The `.dat` decryption and mapping.
- `tools/taghag_import/tags.py`: Binary-safe tag dumping and writing. *This module was initially designed for MP3 ID3 tags, but its structural safety and dry-run boundaries make it an excellent template for Vorbis comment manipulation in FLAC.*
- `tools/taghag_import/genre.py` & `genre_rules.json`: General purpose case-insensitive genre normalization.

## 4. The Clean-Room Boundary

Codex must execute this port strictly observing these boundaries. The target implementation must **NOT** include:

- Any code importing or wrapping `db_client.py`. All Supabase REST interactions are strictly forbidden and must be rewritten by Opus to execute native `sqlite3` queries against `music_v3.db`.
- The name "Magikbox" in active code, configuration, or new documentation.
- The `web/` and `supabase/` folders.
- The root-level scratch files (`dj.beatport.com*.har`, `.csv`, `.txt`, `.m3u`, `.m3u8`).
- Dependencies on legacy Taghag environment variables (`TAGHAG_SUPABASE_URL`, etc.).

## 5. Re-Architecting Database Interactions

Opus is tasked with refactoring the data flow. 

In `taghag`, vectors, cues, and segments were written via `TaghagDbClient._postgrest_request()`. In `tagslut`, Opus must design a new `sqlite3` data-access layer that maps these entities to the local schema. 
- The `track_embedding` 7D vectors must be serialized safely into SQLite.
- The `track_segment` and `dj_tag` data must be merged natively into the `tagslut` track models.

## 6. Testing & Validation

The exported engine must pass the following validation in `tagslut`:
1. **No Cloud Calls:** The system must run end-to-end (Essentia extraction -> Beam Search) without any internet connection, proving the Supabase decoupling.
2. **Audio Agnosticism:** The intelligence engine must successfully process a directory of FLAC files, verifying that legacy MP3 coupling has been removed.
3. **Decoder Reliability:** The `test_beatport_resolver.py` module must pass against a local, sanitized set of fixture payloads, proving the iWebDJ logic works independently of live Beatport API scraping.
