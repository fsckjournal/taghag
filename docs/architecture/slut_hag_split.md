# How the slut and the hag split the tag

The division of responsibility between the two layers, and the invariants that keep
the data layer from sprawling. Pairs with [GLOSSARY.md](../GLOSSARY.md). One page on
purpose — rules, not a framework.

This doc concerns **two separate Supabase projects** (confirmed 2026-06-29):

| Project | ref | Role |
| --- | --- | --- |
| **tagslut** | (in the `slut` repo) | Backbone — system of record |
| **taghag** | `rnscghanqopewyfxqjhp` | Brain — understanding & mixing |

(There was a stale empty duplicate `hqirwdvflxnfeagejnjg`, mislabeled "taglsut",
older schema, no data — paused 2026-06-29, pending deletion. Not a real backbone.)

## The split (decided)

**Tagslut owns identity. Taghag owns understanding.**

| | **Tagslut (Backbone)** | **Taghag (Brain)** |
| --- | --- | --- |
| Owns | Identity, provenance, acquisition, safety | Audio analysis, similarity, mixing |
| System of record for | ISRC/UPC, provider IDs, `content_sha256`, fingerprint, file location | MIR, embeddings, cues, crates, transitions |
| Writes to the other? | — | **Never.** Taghag is read-only on Tagslut. |
| Join keys | (authoritative) | references `content_sha256`, ISRC |

If a fact answers *"which release/file is this and where did it come from"* → Tagslut.
If it answers *"what does it sound like / how does it mix"* → Taghag.

## Invariants (do not break)

1. **FLAC is the only analysis input.** Every analysis pipeline reads FLAC masters.
   MP3 is never an analysis *subject*. (Code already enforces this — `extract_dj_slice`,
   `stage` filter to `.flac`.)
2. **MP3 exists only as a derived export**, never ingested back for analysis. (See Open
   decision #1 on who owns producing it.)
3. **Metadata-only.** No binary audio in either DB. Audio stays on local disk.
4. **Local files stay local.** Taghag does not move, rename, retag, or delete masters.
5. **Migrations-only.** All schema changes are numbered SQL migrations in
   `supabase/migrations/`. No hand-editing schema, no drift, no ORM auto-sync.
6. **Manual batch intake only.** Files enter via an explicit CLI run (`import-batch`,
   `stage`, `analyze`, `cue import`) — all dry-run-capable. **No daemon, no watcher.**
   The DB never grows unsupervised. Keep it this way.
7. **One analysis lineage.** The current lineage is Apple-analyzer → `apple_track_analysis`
   → `apple_derived_features` (+ `track_embedding`). Don't add a parallel lineage; extend
   this one. Raw tables + `*_canonical` **views** is the allowed pattern (views, not copies).

## Anti-monster rules

- New table? It must not overlap an existing one. Prefer a **view** over a redundant table.
- Retire legacy on sight: the `track_analysis` table (Essentia/Magikbox/MP3 era) is the one
  legacy artifact — see Open decision #3.
- RLS on every table (already true). Secret key server-side only; web uses `VITE_*`/publishable.
- Run `get_advisors` (security + performance) after any DDL.

## Known residue — cleaned

- ~~`track_analysis` comment stale ("Essentia/Magikbox analysis for local MP3 files")~~ —
  **fixed** by migration `20260629000000_recomment_track_analysis_flac.sql` (FLAC, no dead
  names). The table is **kept** (Open decision #3 resolved): it's the live store the
  similarity engine reads `sonic7_v1` from — `db_client.upsert_track_analysis` writes it,
  `similarity/sonic_discovery.py` + `human_correction.py` read it. NOT superseded by the
  Apple lineage; the two coexist (sonic7 vectors vs Apple MIR).

## Open decisions (for Georges — not legislated here)

1. **Who produces MP3 DJ-derivatives?** Taghag currently ships `transcode.py` +
   `DEFAULT_MP3_OUTPUT_ROOT=/Volumes/LOSSY/taghag` — it *creates* lossy exports. That sits
   awkwardly against "Taghag = understanding, read-only, FLAC-only." Is producing
   derivatives a **slut** job (acquisition/derivative management) or a **hag** job
   (mix-prep)? Decide and move `transcode` accordingly.
2. **Who ingests DJ-app evidence** (Rekordbox `rbx-re.xml`, MIK cues, Beatport)? Currently
   read in Taghag. Is that identity/provenance (slut) or understanding input (hag)?
3. ~~**Fate of legacy `track_analysis`**~~ — **RESOLVED: keep.** It's live (similarity reads
   `sonic7_v1` from it); not legacy. Comment fixed via migration. See above.

## Scope note

This split spans both repos and is recorded on both sides:
- **slut** `docs/decisions/0010-tagslut-taghag-analysis-boundary.md` — semantic ownership
  (provider BPM/key vs measured values; exchange via neutral JSON keyed by identity).
- **slut** `docs/decisions/0011-data-layer-invariants.md` — the data-hygiene invariants
  mirrored from this doc (FLAC-only, metadata-only, migrations-only, manual intake).
- **hag** (this doc) — the structural split + anti-monster rules. Authoritative for the
  data-layer invariants; keep the two repos in sync.
