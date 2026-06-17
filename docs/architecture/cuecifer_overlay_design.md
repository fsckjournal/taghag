# Taghag Cuecifer Root Overlay Design

Date: 2026-06-11

## Mission

Produce a ZIP archive that can be unpacked at the root of the Taghag
repository to install the provider, Essentia, Cuecifer, and advanced-cue
surfaces needed to revive Taghag as an AI-powered DJ intelligence system.

The archive must be safe to inspect and apply against the current Taghag
working tree. It must not contain credentials, audio, model binaries, generated
analysis artifacts, Python environments, caches, or database dumps.

## Current Context

Source repository:

`/Users/g/Projects/tagslut`

Target repository:

`/Users/g/Projects/taghag`

External analyzer:

`/Users/g/Projects/Essentia-to-Metadata`

The target Taghag working tree already contains substantial uncommitted and
untracked work, including partial Postman collections, Cuecifer modules,
Supabase migrations, pgvector work, and advanced-cue tools. The delivery must
therefore be a curated overlay with conflict detection, not a blind snapshot of
either repository.

The Tagslut repository remains FLAC-first and authoritative for its own active
workflow. This delivery is an explicitly requested historical Taghag revival
and must remain isolated under the handover/package surface.

## Selected Approach

Use a curated Taghag-root overlay with an installer.

The ZIP root mirrors the intended Taghag paths. Unpacking the archive creates a
delivery control directory and stages the overlay, but the installer performs
the final application after checking the target repository.

The installer:

1. Verifies that it is running from a plausible Taghag repository root.
2. Reads the delivery manifest.
3. Classifies each destination as absent, identical, or conflicting.
4. Installs absent files and skips identical files.
5. Refuses conflicting overwrites unless the operator explicitly selects an
   individual resolution.
6. Never deletes target files.
7. Writes an installation report outside tracked source paths.

This design is preferable to a direct snapshot because the current Taghag
working tree is dirty and divergent. It is preferable to a Git patch because
the package must remain usable without a compatible branch or commit base.

## Package Contents

The archive includes:

- A machine-readable manifest with file paths, SHA-256 hashes, provenance, and
  purpose.
- A conflict-safe installer and preflight command.
- Taghag-owned Postman collection files needed for provider evidence.
- Beatport DJ/account and Beatport v4 catalog authentication adapters.
- Environment templates and local token synchronization wrappers.
- Essentia runner, sidecar validation, and ingestion adapters.
- Cuecifer pgvector-backed analysis, similarity, crate, correction, and mapping
  modules.
- Advanced cue ingestion, segment extraction, and path-planning modules.
- Supabase migrations with owner-scoped RLS and service-role compatibility.
- Focused tests, fixtures without private data, smoke checks, and active
  operator documentation.

The archive excludes:

- Access tokens, refresh tokens, passwords, client secrets, cookies, and local
  Postman secret environments.
- Audio files, playlists containing private absolute paths, database files,
  generated sidecars, and generated crates.
- Essentia models, virtual environments, Node modules, caches, bytecode, and
  build output.
- Tagslut's canonical database or any mounted-library content.

## Shared Authentication

Taghag reuses the operator's existing local credential stores rather than
creating a second set of secrets.

Supported local sources are:

- Tagslut's ignored repository `.env`, when present.
- `~/.config/tagslut/tokens.json`.
- The operator's BeatportDL configuration and credentials.

The checked-in Taghag adapters may read these locations, but they must not copy
secret values into tracked files, logs, manifests, test fixtures, or the ZIP.
They generate or update a Taghag-local ignored Postman environment.

Beatport authentication remains two distinct flows:

1. Beatport DJ/account PKCE uses the account authorization and token endpoints.
2. Beatport v4 catalog/search refresh uses the v4 API token endpoint and the
   BeatportDL-compatible credential material.

The implementation must not silently substitute one token type for the other.
Preflight and smoke output must identify which flow is available without
printing secret values.

## Postman and Beatport

The package promotes a coherent Taghag-owned collection rather than depending
on Postman files remaining in Tagslut.

The Beatport surface includes:

- PKCE setup and token introspection.
- Search by ISRC.
- Catalog search.
- Track hydration by ID.
- Release lookup by ID.
- Genre-track browsing derived from the Beatport DJ application behavior.
- Personalized recommendation lookup where the authenticated account permits
  it.
- Beatport URL resolution.
- Stable evidence markers consumed by Taghag's provider evidence importer.

Collection and environment paths are configurable. The operator-facing runner
validates the real checked-in collection, requested folders/items, executable,
and environment before presenting or running a command.

Provider failures are recorded as explicit matched, no-match, ambiguous,
unauthorized, rate-limited, or error evidence. They do not fabricate metadata
or block unrelated local ingestion.

## Essentia Integration

Taghag consumes the existing analyzer at:

`/Users/g/Projects/Essentia-to-Metadata`

The path is configurable through `TAGHAG_ESSENTIA_REPO`.

The default analysis invocation uses the analyzer's existing environment and
non-mutating candidate flow:

```bash
tag_music.py <input> \
  --auto \
  --model-profile candidate \
  --dry-run \
  --sidecar-on-dry-run
```

The adapter must discover the correct Python executable from the analyzer
project, verify the CLI contract, verify model availability, and capture the
generated sidecar and run log into a Taghag artifact directory.

The accepted input contract is `essentia-lexicon-sidecar/2`. Validation checks:

- Top-level schema and track mapping.
- Absolute or explicitly rebased source paths.
- Ranked genre payloads.
- Raw `happy`, `aggressive`, `relaxed`, `party`, and `danceability` values.
- Numeric ranges and missing-value handling.
- Analyzer model profile and model manifest provenance.

Sidecar ingestion stores:

- Source artifact SHA-256.
- Analyzer repository path and Git revision when available.
- Model profile and manifest.
- Analysis timestamp.
- Raw source payload.
- Normalized features used by Cuecifer.
- Match evidence linking the result to `audio_file`.

Repeated ingestion of the same source artifact is idempotent.

Batch analysis is resumable. Completed chunks with valid sidecars are reused,
and the final stitched sidecar is validated before database ingestion. Taghag
does not bundle, fork, or modify the Essentia analyzer.

## Durable Cuecifer Model

Supabase/Postgres is the durable authority for Cuecifer state. Local SQLite may
be used only for disposable reports or tests and must not become authoritative.

The model links analysis to Taghag's owner-scoped `audio_file` rows and stores:

- Versioned normalized sonic vectors.
- Producer-facing vibes and their evidence.
- Raw analysis provenance.
- Explicit human corrections.
- Pin/anchor state.
- Vector policy version.
- Computation timestamp.

Human corrections are durable database records with provenance. Recomputing
model-derived vectors must not erase explicit corrections or pins.

The initial vector remains compatible with the established seven dimensions:

1. Normalized energy.
2. Normalized BPM.
3. Danceability.
4. Party confidence.
5. Happiness confidence.
6. Aggression confidence.
7. Relaxed confidence.

The vector schema is versioned so later dimensions can be introduced without
silently mixing incompatible vectors.

Similarity uses pgvector cosine distance with owner isolation and a matching
vector schema. Operator commands support:

- Recompute one track or all eligible tracks.
- Find similar tracks.
- Generate a neighborhood crate.
- Summarize a crate.
- Produce map/export data.
- Apply or remove an explicit human correction.

Missing evidence omits a track from that run; it does not create a permanent
review or exclusion queue.

## Advanced Cue Intelligence

The advanced-cue layer shares the same `audio_file` identities and owner
boundary as Cuecifer.

It includes:

- Rekordbox/ANLZ cue import.
- Segment extraction and segment-level vector storage.
- Transition-edge persistence.
- Beam-search path planning that combines vector distance, BPM compatibility,
  Camelot compatibility, and cue confidence.

The implementation must align column names and foreign keys with the actual
Taghag migrations. It must not assume that prototype SQL from the handover is
correct merely because a similarly named table exists.

Rekordbox remains an input/interchange system. The package does not directly
write Rekordbox `master.db`.

## Database and Security

Migrations are additive and idempotent at the migration-history level. They
must:

- Enable required extensions in the established Taghag extension schema.
- Use owner-scoped compound foreign keys where the base schema requires them.
- Enable RLS on every user-owned table.
- Restrict authenticated access to `owner_user_id = auth.uid()`.
- Grant service-role access for trusted import tools.
- Add vector and lookup indexes only after their referenced columns exist.
- Avoid duplicate competing tables for the same Cuecifer concept.

The package preflight statically checks migration ordering and expected base
schema names before application. Database migrations are never applied merely
by unzipping the archive.

## Commands

The overlay exposes one documented `taghag-intel` operator surface:

- `taghag-intel preflight`: inspect dependencies, paths, credentials, Postman assets,
  Essentia contract, and migration compatibility.
- `taghag-intel auth-sync`: generate the ignored Taghag Postman environment
  from existing local stores.
- `taghag-intel provider-smoke`: run non-destructive provider checks.
- `taghag-intel essentia analyze`: invoke the external analyzer.
- `taghag-intel essentia ingest`: validate and ingest a sidecar.
- `taghag-intel cuecifer recompute`: derive durable vectors.
- `taghag-intel cuecifer similar`: query nearest tracks.
- `taghag-intel cuecifer crate`: render a neighborhood playlist.
- `taghag-intel cuecifer correct`: persist explicit human feedback.
- `taghag-intel cue import`, `taghag-intel cue extract`, and
  `taghag-intel cue plan`: operate the advanced-cue layer.

All mutation commands support dry-run or an explicit execute/apply flag where
practical. Help text identifies external writes and required credentials.

## Conflict-Safe Installation

The delivery must be buildable and testable without modifying the target
Taghag repository.

Installation behavior:

- Absent destination: install.
- Byte-identical destination: skip and record.
- Different destination: stop and report a conflict.
- Existing untracked target file: treat exactly like any other destination;
  never assume it is disposable.
- Existing secret environment: preserve it and update only through the
  dedicated auth synchronization command.

The installer does not use `rm`, `git reset`, or broad directory replacement.
It never stages, commits, or pushes the target repository automatically.

## Testing and Verification

The delivery includes focused tests for:

- Manifest completeness and hash verification.
- Installer absent/identical/conflict behavior.
- Secret and private-path exclusion.
- Postman request and environment variable contracts.
- Beatport token-flow separation.
- Provider marker parsing.
- Essentia preflight, command construction, sidecar validation, chunk resume,
  and idempotent ingestion.
- Cuecifer policy, vector normalization, correction preservation, pgvector
  query construction, and crate generation.
- Migration schema, RLS, indexes, and base-schema compatibility.
- Advanced-cue import and planner scoring.

The final verification sequence:

1. Build the overlay in a temporary directory.
2. Verify its manifest and scan it for secrets, caches, and private artifacts.
3. Apply it to an empty Taghag-shaped fixture.
4. Reapply it and verify idempotent skips.
5. Add a conflicting fixture and verify refusal.
6. Run the focused Python tests.
7. Run static Postman validation.
8. Run Essentia preflight against the installed external project without
   analyzing operator audio.
9. List ZIP contents and verify root-relative paths.

Live provider calls, Supabase migrations, and audio analysis remain explicit
operator actions and are not required to build the ZIP.

## Documentation

The package includes:

- `README` with unzip, preflight, installation, and rollback guidance.
- Auth guide describing shared local stores and both Beatport flows.
- Postman guide with checked-in item names and smoke commands.
- Essentia guide documenting the external project contract.
- Cuecifer guide explaining vectors, provenance, corrections, and crates.
- Advanced-cue guide explaining inputs and planner behavior.
- Troubleshooting guide for conflicts, expired tokens, schema mismatch, and
  missing analyzer dependencies.

Documentation must distinguish verified commands from historical notes and
must not claim that a live service or migration has been tested when only
static validation was performed.

## Deliverables

The work produces:

1. A versioned ZIP archive under the Tagslut handover area.
2. The expanded overlay source used to build it.
3. A manifest and build report.
4. Focused tests and a reproducible package builder.
5. Updated Tagslut handover documentation pointing to the package and its
   verified installation workflow.

The archive is ready when it can be unpacked at a Taghag root, preflighted,
installed without overwriting conflicts, and used to connect the existing
Postman credentials and Essentia analyzer to durable Cuecifer and advanced-cue
components.
