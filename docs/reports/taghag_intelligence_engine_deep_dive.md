# Taghag Autonomous Intelligence Engine: Technical Deep Dive

Date: 2026-06-15

## 1. Executive Summary

This report details the architectural and algorithmic foundation of the Taghag Autonomous Intelligence Engine (codenamed "Cuecifer"). The system is designed to programmatically construct superhuman DJ transitions by fusing structural track data, harmonic energy mapping, and acoustic "vibe" analysis into a cohesive, vector-searchable database. 

This document strictly covers the intelligence and data-ingestion layers, detailing how raw audio and network payloads are converted into durable semantic vectors.

## 2. The Intelligence Triad

The core intelligence of Taghag is built upon three distinct reverse-engineered pillars. 

### 2.1 Structural Intelligence (Mixonset / Advanced Cue)
To sequence tracks without human intervention, the system requires precise physical boundaries. 
- **Decryption:** The engine decrypts proprietary local `.dat` files from the Offtrack/Mixonset application.
- **Mapping:** It translates proprietary integer key codes to the standard Camelot format.
- **Segmentation:** It extracts exact physical beat grids and segment boundaries, classifying regions into `intro`, `drop`, `breakdown`, and `outro`.
- **Durable Storage:** These markers are persisted into the `track_cue` and `track_segment` tables, directly linked to the authoritative `audio_file` record.

### 2.2 Acoustic Intelligence (Essentia 7D Vectors)
To understand the subjective "feel" or "vibe" of a track, we rely on the Essentia audio analysis library.
- **Feature Extraction:** A localized Python adapter (`essentia_adapter.py`) runs offline analysis on the raw audio files.
- **The 7D Model:** The adapter computes a 7-dimensional `control_vec` embedding. The standard dimensions are: Normalized Energy, Normalized BPM, Danceability, Party Confidence, Happiness Confidence, Aggression Confidence, and Relaxed Confidence.
- **Vector Storage:** These vectors are serialized and stored durably, allowing the system to understand tracks purely by their mathematical acoustic footprint.

### 2.3 Harmonic Energy (Beatport iWebDJ / Postman Evidence)
To map the dynamic energy changes throughout a track's lifecycle, the system taps into Beatport's hidden DJ metadata.
- **Network Interception:** By intercepting raw `.har` network traffic during live Beatport DJ sessions, the engine decodes the undocumented `metadata.php` `iwebdj` payload.
- **Envelope Extraction:** We extract microscopic mathematical energy envelopes (`a0`-`a5`) and dynamic beat markers (`bm0`).
- **Provider Evidence:** This data is validated using the `postman_evidence.py` importer, ensuring strict ISRC matches before the energy envelopes are bound to the local track.

## 3. The Durable Cuecifer Model & Vector Similarity

The raw intelligence gathered from the triad above is aggregated into the "Cuecifer" model, relying on a robust Postgres/Supabase schema equipped with the `pgvector` extension.

### 3.1 `pgvector` Integration
Instead of relying on fragile local NumPy arrays, the 7D sonic vectors are persisted to the `sonic_analysis` (or equivalent) table utilizing Postgres's native vector type.
- **Native Similarity:** This enables hyper-fast, scalable neighborhood generation directly at the database level using cosine distance (`ORDER BY sonic_vector <=> target_vector`).
- **Human-in-the-loop (HITL):** The system supports explicit human overrides (e.g., pinning a track's vibe or correcting a misclassification). These manual corrections (`pinned = 1`) are durable and survive algorithmic re-computations.

## 4. Advanced Cue Intelligence: The Butter Flow Planner

With the database populated with structural boundaries, Camelot keys, and 7D acoustic vectors, the system can autonomously sequence sets using the `advanced_cue_planner.py` module.

### 4.1 Beam-Search Pathfinding
The "Butter Flow" planner utilizes a beam-search routing algorithm to generate flawless setlists.
- **Multi-variable Scoring:** When evaluating a potential transition from Track A to Track B, the planner calculates a composite penalty score.
- **Distance Metrics:** The score is a weighted combination of:
  1. **BPM Delta:** Strict penalties for massive tempo jumps unless a physical breakdown segment allows for it.
  2. **Harmonic Distance:** Rewards for perfect Camelot wheel proximity (e.g., 8A -> 8B, or 8A -> 9A).
  3. **Vector Distance:** Uses the `pgvector` cosine distance to ensure the acoustic "vibe" (energy, danceability) remains cohesive across the transition.
  4. **Cue Alignment:** Ensures the `outro` segment of Track A aligns mathematically with the `intro` segment of Track B.

## 5. Execution Surface

The intelligence engine is operated via the unified `taghag-intel` CLI overlay, which provides strict boundaries and validation:
- `taghag-intel essentia analyze / ingest`: Manages the external acoustic extraction and sidecar validation.
- `taghag-intel cuecifer recompute / similar`: Interfaces with `pgvector` to build neighborhoods.
- `taghag-intel cue extract / plan`: Operates the beam-search pathfinder to produce the final autonomous setlist.

## 6. Conclusion
By fusing structural, acoustic, and harmonic data into a unified vector schema, the Taghag Intelligence Engine transcends traditional metadata tagging. It treats a music library not as a list of strings, but as a multi-dimensional topological map that can be mathematically navigated to produce perfect musical sequences.
