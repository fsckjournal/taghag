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

## Product direction (decided 2026-06-29)

Georges is **no longer DJing**. Taghag is now a **FLAC playlist generator with automix**
— not a DJ tool. DJ-workflow and MP3 features are dropped *as a product goal*.

**This drops near-zero code.** The "keep the wheels" principle governs: never delete
reverse-engineered decoders/importers just because a feature is dropped — they are
hard-won and we'd hate to rebuild them. **Keepers:** DJ-app cue/grid decoders (mixonset
AES, ANLZ, `extract_dj_slice`); the Beatport/provider decoder; `transcode`/`stage`
(FLAC→FLAC staging, never was MP3); both `sync_vibes` files. The only change is cosmetic
(stale "MP3"/"ID3" names). Verify coupling before claiming anything droppable.

**Roadmap (sandbox → production), dependency order:** ① identity first (slut: anchor FLAC
masters to ISRC/`content_sha256`; provider wheels live here) → ② repeatable **manual**
intake (hag: stage → `audio_file` → apple-analyzer → derived features → `track_analysis`
sonic7 → embeddings; no daemon) → ③ unify sequencing into one `render_plan.json` contract
(similarity + harmonic; Spotify-order import becomes one strategy) → ④ render → Roon
(`render_plan.json` → `mixslice` → FLAC+CUE → watched folder).

## Render plans must be identity-keyed (cross-session decision, 2026-06-29)

Sync from the slut-side session. Two findings that change the contract:

- **`render_plan.json` is path-keyed today — must move to content identity.** The builder
  (`mixslice/build_render_plan.py`) resolves each row to an absolute FLAC `path` by fuzzy
  title/artist match against an m3u8, and `grid_mix`/`chain_mix` read `t["path"]` directly.
  No `content_sha256`, no ISRC, no track id. The slut v3 census found **51% of rows point to
  dead paths**; the v4 re-layout would break every existing plan. **Decision:** render plans
  must reference **stable content identity** (`track id` / `content_sha256`); resolve
  identity→path **only at render time**. This makes plans survive the re-layout and portable
  across any player. (Slut already has the schema: Alembic `0001_library_foundation` —
  `track` + `track_file(path UNIQUE, sha256, acoustic_fingerprint, role)`.)

- **Automix is LIVE, over the actual files — not a baked continuous FLAC.** (Operator
  decision 2026-06-29.) The model is **offtrack in local mode**: a live engine plays the
  individual FLAC files, selects each track's best segment, and executes the transition
  (crossfade / beatmatch) in **real time**. A pre-rendered continuous FLAC is explicitly **not
  viable**. This means the player-automix capability **is** the crux (my earlier "baked
  sidesteps it" was wrong): Roon **cannot** automix (closed API blocks the live stream → out);
  an **open** target is required — Jellyfin (open REST) candidate, or hag's own live engine.
  Operator decision deferred ("explore Jellyfin feasibility first").
- **What this does to mixslice.** mixslice becomes the **DSP brain for the live engine**, not
  a render-to-file tool. The transition math (grid-based wobble-free beatmatch, crossfade
  curves, loudness matching, cue/phase detection) is the reusable core; `chain_mix`/`grid_mix`
  writing `out.flac` is now only an **offline preview / test harness**, not the deliverable.
  The live engine reads the individual files and streams the mix. Concrete design:
  [live_automix_engine.md](live_automix_engine.md).
- **`render_plan.json` becomes the live mix instruction set:** identity-keyed ordered tracks +
  per-track in/out segment points + per-transition spec (type, duration, beatmatch params).
  The live engine resolves identity→file and executes — so identity-keying (above) is doubly
  required. Standard FLAC/Vorbis tags + relative paths keep it portable across any live target.

Slut refs (committed on `slut` dev): `docs/audit/2026-06-29-db-library-audit-and-v4-plan.md`
§5b, `docs/RELEASE_TAXONOMY_AND_TAGGING_RULES_RESEARCH_PROMPT.md`, ADRs 0010/0011.

## Open decisions (for Georges — not legislated here)

1. **Who produces MP3 DJ-derivatives?** Taghag currently ships `transcode.py` +
   `DEFAULT_MP3_OUTPUT_ROOT=/Volumes/LOSSY/taghag`. NOTE: `transcode` is actually FLAC→FLAC
   staging (`shutil.copy2`), not MP3 production — the name is the misleading part. Keep the
   code; rename `DEFAULT_MP3_OUTPUT_ROOT`. If true lossy export is ever wanted, decide then
   whether it's a **slut** job (derivative management) or **hag** job (mix-prep).
2. **Who ingests DJ-app evidence** (Rekordbox `rbx-re.xml`, MIK cues, Beatport)? Currently
   read in Taghag, and **kept regardless** (the wheels). Open question is only *placement*:
   provider/acquisition → slut eventually; DJ-app grid decoders → hag (grid source).
3. ~~**Fate of legacy `track_analysis`**~~ — **RESOLVED: keep.** It's live (similarity reads
   `sonic7_v1` from it); not legacy. Comment fixed via migration. See above.
4. **Grid ownership (strategic fork).** Keep *consuming* DJ-app grids (Rekordbox/MIK — the
   wheel we borrow) vs *compute our own* rigid grids from the Apple analyzer's beats. Keeping
   the wheels means we're not blocked either way. Undecided.
5. ~~**Do `sync_vibes` actually work / auto-write?**~~ — **RESOLVED.** Both
   `taghag_import/sync_vibes_to_id3.py` and `similarity/sync_vibes.py` write `[TS: …]` into
   FLAC Vorbis `comment` tags, **default to dry-run**, require explicit `--execute`. Nothing
   auto-writes. Near-duplicates (dedupe later); misnamed ("ID3"/"MP3" → they write FLAC).

## Scope note

This split spans both repos and is recorded on both sides:
- **slut** `docs/decisions/0010-tagslut-taghag-analysis-boundary.md` — semantic ownership
  (provider BPM/key vs measured values; exchange via neutral JSON keyed by identity).
- **slut** `docs/decisions/0011-data-layer-invariants.md` — the data-hygiene invariants
  mirrored from this doc (FLAC-only, metadata-only, migrations-only, manual intake).
- **hag** (this doc) — the structural split + anti-monster rules. Authoritative for the
  data-layer invariants; keep the two repos in sync.
