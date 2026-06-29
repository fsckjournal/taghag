# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Taghag is the **audio intelligence and mixing brain** of a two-layer home music library system. It provides deterministic audio analysis (Apple Music Understanding), feature engineering, sonic similarity discovery, and harmonic transition planning for FLAC files.

**Two-layer architecture** (per Opus product assessment):
- **Backbone (Tagslut)**: Identity, provenance, acquisition, and safety layer. FLAC masters anchored to durable identity (ISRC/UPC + provider IDs + content hash + fingerprint). Read-only for Taghag; Tagslut is the system of record.
- **Brain (Taghag)**: Audio understanding and mixing. Apple Music-Understanding analysis → interpretable embeddings → sonic similarity → harmonic transition planning → generative crates.

The product north star is **a library that earns trust through provenance and spends it on understanding**: understand → interlink → harmonically mix → playlist → listen.

## Repository Structure

```bash
taghag/
├── tools/
│   ├── taghag_import/        # CLI package and core analysis modules
│   │   ├── cli.py            # Main CLI entry point (taghag-import command)
│   │   ├── apple_*.py        # Apple Music Understanding integration (MIR analysis)
│   │   ├── beatport_*.py     # Provider resolver & auth
│   │   ├── audio_*.py        # Audio probing and auditing
│   │   └── tests/            # pytest test suite
│   ├── similarity/           # Sonic similarity & crate generation (pgvector); was "cuecifer"
│   ├── apple-analyzer/       # Swift Apple-MIR analyzer (MusicUnderstanding.framework); was "cuecifer-analyzer"
│   ├── mixslice/             # Beatmatched-mix renderer (grid_mix, chain_mix)
│   └── pyproject.toml        # Python package definition
├── web/                       # React/Vite frontend (read-only view, minimal)
│   ├── src/
│   │   ├── components/
│   │   ├── routes/
│   │   └── lib/              # Supabase client, types
│   └── package.json
├── supabase/
│   └── migrations/           # Source-controlled SQL schemas (pgvector for embeddings)
├── roon-extension/           # (Stub; actual extension in tagslut repo)
└── docs/
    ├── architecture/         # System design & integration specs
    ├── audit/                # Assessment reports (Opus product audit)
    └── README.md            # Documentation index
```

## Core Concepts

### Audio Analysis Pipeline

1. **Apple-analyzer** (Swift, wraps Apple Music Understanding): produces deterministic MIR:
   - BPM, key, key-change ranges
   - Beats, bars, segments
   - Instrument and vocal-intensity activity
   - No LLM, no cloud, no audio upload

2. **Feature Engineering** (`apple_derived_features.py`):
   - Raw MIR → interpretable scalars (pace mean/volatility, key stability, vocal intensity, BPM agreement)
   - `apple_hybrid_v1` vector for pgvector storage

3. **Sonic Similarity & Generative Crates** (`similarity/`):
   - Similarity search over `sonic7_v1` + `apple_hybrid_v1` vectors
   - Harmonic transition scoring (pace delta, vocal overlap, loudness, BPM disagreement, key instability)
   - Seed track → neighborhood → crate

4. **Identity Resolution**:
   - Read-only integration with Tagslut's `track_identity` (ISRC, content SHA-256)
   - Join keys already defined: `content_sha256`, ISRC
   - Playlists are identity-anchored (survive retagging and file moves)

### Database Model (Supabase/PostgreSQL)

- **Metadata only** — no binary audio assets
- **pgvector columns** for Apple-derived embeddings (`apple_hybrid_v1`, `sonic7_v1`)
- **RLS (Row Level Security)** for multi-tenant safety
- **Migrations** source-controlled in `supabase/migrations/`
- No schema drift; all changes via numbered migrations

### Clean-Room Constraints

- **No legacy Tagslut imports**: `audit_cleanroom.py` forbids `tagslut` in Taghag code
- **FLAC-native**: Audio analysis assumes FLAC; metadata extraction via Vorbis comments
- **Local files stay local**: No deletion, upload, or movement
- **Server keys secure**: Database credentials in environment only; frontend uses `VITE_*` vars only

## Commands

### Setup

```bash
# Python importer setup
cd tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Apply Supabase migrations
# Option 1: Local Supabase CLI (requires Docker)
supabase db reset

# Option 2: Hosted Supabase (free tier)
# Copy .env.example to .env, fill in TAGHAG_SUPABASE_URL and service role key
# Apply migrations manually from supabase/migrations/ SQL files

# Frontend setup
cd ../web
npm install
```

### Testing

```bash
# Python tests (from tools/)
cd tools
pytest                    # All tests
pytest tests/test_*.py   # Specific file
pytest -k audio_audit    # By keyword
pytest -v                # Verbose

# Before committing: clean-room audit
python audit_cleanroom.py
```

### Building & Running

```bash
# Web frontend
cd web
npm run build     # Production build → dist/
npm run dev       # Dev server (Vite)

# Analysis commands (from tools/)
taghag-import analyze --target /path/to/flac-or-directory --dry-run
taghag-import analyze --target /path/to/flac-or-directory         # Write to Supabase (requires env)
```

### Audio Analysis

```bash
# Run Apple Music Understanding analyzer (dry-run: no DB writes)
taghag-import analyze --target /path/to/flacs --dry-run

# Audit local FLAC metadata and quality
taghag-import audit-flac --root /path/to/audio-library --output-dir ../artifacts/audio_audit

# Dump FLAC tags to JSON
taghag-import dump-tags --root /path/to/audio-library --out ../artifacts/flac_tags.jsonl

# Dry-run tag updates
taghag-import write-tags --plan /path/to/updates.csv
taghag-import write-tags --plan /path/to/updates.csv --execute --force
```

### Database & Import

```bash
# Stage FLACs with metadata-only receipt (no Supabase upload)
taghag-import stage --source /path/to/flacs --output /path/to/batch --dry-run
taghag-import stage --source /path/to/flacs --output /path/to/batch

# Provider evidence collection (Postman ISRC lookups)
taghag-import provider-evidence \
  --isrc USABC2400001 \
  --collection /path/to/provider-evidence-collection \
  --environment /path/to/provider-environment.json
```

## Development Guidelines

### Before Committing

1. **Run tests**:

   ```bash
   cd tools && pytest tests -q
   ```

2. **Clean-room audit** (forbids "tagslut" in code):

   ```bash
   python audit_cleanroom.py
   ```

3. **Web build**:

   ```bash
   cd web && npm run build
   ```

4. **Stage and commit**:

   ```bash
   git add <specific files>
   git commit -m "..."
   ```

### Code Patterns

- **Python imports**: Use `taghag_import.X` (e.g., `from taghag_import.cli import main`)
- **SQL migrations**: Add numbered migrations to `supabase/migrations/`; never hand-edit schema
- **Tests**: Use pytest; fixtures in `tools/tests/fixtures/`; parametrize for multiple scenarios
- **Audio analysis**: Assume FLAC input; use `ffprobe` for technical metadata; `mutagen` for Vorbis tags
- **Feature vectors**: Use pgvector; store interpretable embeddings (not opaque tensors)

### Key Modules

| Module | Purpose | Key Files |
| --- | --- | --- |
| **CLI** | Command-line interface | `cli.py` (main entry) |
| **Apple Analysis** | MIR extraction & feature engineering | `apple-analyzer/` (Swift), `apple_*.py` |
| **Similarity** | Sonic similarity, crates & transition scoring | `similarity/`, `advanced_cue_planner.py`, `apple_handoff.py` |
| **Mixslice** | Beatmatched-mix renderer (grid-based, wobble-free) | `mixslice/grid_mix.py`, `mixslice/chain_mix.py` |
| **Audio Audit** | Metadata extraction & quality checking | `audio_audit.py`, `audio_probe.py` |
| **Provider Evidence** | ISRC lookups via Postman | `beatport_*.py`, `provider_evidence.py` |
| **Tests** | pytest suite | `tools/tests/test_*.py` |

## Important Files & Docs

- **[docs/GLOSSARY.md](docs/GLOSSARY.md)** — Canonical vocabulary: every term/tool/stage. Read first; it overrides older docs.
- **[docs/architecture/slut_hag_split.md](docs/architecture/slut_hag_split.md)** — How Tagslut/Taghag split responsibility + data-layer invariants (FLAC-only, metadata-only, migrations-only, manual intake). Read before schema/pipeline changes.
- **[README.md](README.md)** — High-level overview (update this if scope changes)
- **[AGENT.md](AGENT.md)** — Agent workspace rules (clean-room, FLAC-native)
- **[docs/architecture/roon_extension_architecture.md](docs/architecture/roon_extension_architecture.md)** — System philosophy, two-layer design
- **[docs/audit/2026-06-21-tagslut-taghag-opus-product-assessment.md](../tagslut/docs/audit/)** — Definitive product assessment (read before major changes)
- **[.github/prompts/](../.github/prompts/)** — Reusable prompts (`taghag-00-master-implementation-plan.prompt.md` etc.)
- **[.env.example](.env.example)** — Configuration template (server keys must not appear in frontend)

## Notes

- **Taghag is read-only on Tagslut**: Taghag's join keys (ISRC, content_sha256) reference Tagslut's authoritative identity, but Taghag never writes to Tagslut.
- **Apple MusicUnderstanding is closed-source**: The analyzer requires a built Swift binary and macOS 26/27+; reproducibility and portability are known risks.
- **Product shape still crystallizing**: Backend (Taghag's analysis engine) is mature; frontend (React web UI) and Roon integration are minimal. Per Opus, the smallest next outcome is one identity-anchored, harmonically ordered playlist that plays in Roon.
- **Memory index**: Check `/Users/g/.claude/projects/-Users-g-Projects-tag-hag/memory/MEMORY.md` for ongoing feature context (time-base anchor, Beatport HAR secrets, etc.).
- **Repo location moved**: this repo lives at `~/Projects/tag/hag` (was `~/Projects/taghag`). The sibling identity repo `tagslut` now lives at `~/Projects/tag/slut` (was `~/Projects/tagslut`), and its database directory is `~/Projects/tag/slut_db` (was `~/Projects/tagslut_db`).
