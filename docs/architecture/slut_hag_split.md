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

## Known residue to clean (both projects empty → free to fix)

- `track_analysis` table comment is stale: *"Essentia/Magikbox analysis for local MP3 files"*
  → MP3 + the dead name "Magikbox". Fix or drop the table (Open decision #3). Propose as a
  migration; do not hand-edit.

## Open decisions (for Georges — not legislated here)

1. **Who produces MP3 DJ-derivatives?** Taghag currently ships `transcode.py` +
   `DEFAULT_MP3_OUTPUT_ROOT=/Volumes/LOSSY/taghag` — it *creates* lossy exports. That sits
   awkwardly against "Taghag = understanding, read-only, FLAC-only." Is producing
   derivatives a **slut** job (acquisition/derivative management) or a **hag** job
   (mix-prep)? Decide and move `transcode` accordingly.
2. **Who ingests DJ-app evidence** (Rekordbox `rbx-re.xml`, MIK cues, Beatport)? Currently
   read in Taghag. Is that identity/provenance (slut) or understanding input (hag)?
3. **Fate of legacy `track_analysis`** — drop it (Apple lineage supersedes it), or repurpose
   + re-comment it as a non-Apple/Essentia path you still want?

## Scope note

This split spans both repos. Consider mirroring this doc into the `slut` repo so the
backbone side records the same boundary.
