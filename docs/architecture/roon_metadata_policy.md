# Roon Metadata Policy

## How to Tag Files So Roon Identifies Releases More Reliably

## 0. Purpose

This policy defines how local audio file metadata should be written to *improve* Roon’s chances of identifying releases correctly and distinguishing between editions, while leaving room for future tooling changes.

It is **policy‑oriented and implementation‑independent**: it does not assume any particular tag editor or pipeline. It is compatible with tagslut‑style external cleanup, but does not depend on specific function names, schemas or CLIs.

This policy covers:

- which metadata fields matter most for Roon identification
- how to separate identification‑critical, edition‑specific, display/enrichment and operational metadata
- how to tag Various Artists releases, compilations, DJ mixes, classical, remixes and reissues
- how to handle incomplete or ambiguous releases, duplicate audio, lossy vs lossless, and corrupt files
- safe behaviour for any automated sanitizer that writes tags
- a concise Roon rescan and **Identify Album** workflow
- practical templates and a final pre‑import checklist

**Core principle**

> Roon reads file tags and uses them as one input for identification, but it does **not** alter your music files or their tags when importing; metadata edits made in Roon are stored in Roon’s database only.[^faq-files]

---

## 1. How Roon Uses Metadata

### 1.1 Roon is not a flat tag reader

Roon models music as an object graph: albums, tracks, performers, performances, compositions, labels, genres and related objects, all linked together.[^metadata-model] File tags are a starting point, not the final truth.

| Layer | Meaning |
| :-- | :-- |
| File tags | Metadata embedded in the audio files |
| Roon metadata | Enrichment from Roon’s providers |
| User edits | Manual corrections made inside Roon |
| Identification state | Whether Roon has matched local media to a known release |
| Local file identity | The specific copy of the release in your library |

### 1.2 File tags matter most before identification

File tags are most critical when Roon first tries to identify an album. Roon’s file‑tag guidance emphasises accurate, specific and complete tagging rather than tricks aimed at a particular on‑screen layout.[^file-tags]

Roon pays particular attention to:

- album title
- track title
- artist
- album artist
- composer
- release date / year
- track and disc numbers and total disc count
- label
- strong identifiers such as barcode/UPC and catalogue number

Credits and genres are important for browsing and discovery, and may assist identification in some edge cases, but they are primarily used as **enrichment** rather than as primary match keys.[^file-tags][^genre-settings]

### 1.3 Roon edits do not repair your files

| Action | Result |
| :-- | :-- |
| Edit metadata inside Roon | Stored in Roon’s database only |
| Import files into Roon | Files and tags are not modified[^faq-files] |
| Change file tags externally | Roon must rescan to see changes[^metadata-updates] |
| Export from Roon | Creates new copies with Roon’s metadata written into the exported files[^export] |

Use Roon edits for display and exceptions, not as a substitute for keeping file tags correct.

---

## 2. Metadata Field Classes

To keep tags durable and predictable, this policy separates metadata into four classes.

### 2.1 Identification‑critical fields

Fields that must be present and accurate for Roon to match the correct release at all:

- `ALBUM`
- `ALBUMARTIST`
- `ARTIST`
- `TITLE`
- `TRACKNUMBER`
- `DISCNUMBER` (for multi‑disc)
- `DATE` (or an equivalent release date field Roon recognises)

These describe **what the release is** and **how its tracks are structured**.

### 2.2 Edition‑specific fields

Fields that help differentiate between **editions of the same album**:

- `LABEL`
- `CATALOGNUMBER`
- `BARCODE` / `UPC`
- `TOTALDISCS` / `DISCTOTAL`
- `TRACKTOTAL` / `TOTALTRACKS` (see §5.3)
- edition release date (`DATE`) when multiple distinct editions exist
- track/disc structure (numbering, presence/absence of bonus tracks)
- track durations

These fields should reflect the **specific edition** represented by your files, not just the first or most famous release.

### 2.3 Recording‑identity and historical fields

Fields that identify *recordings* or original publication history rather than specific packaged editions:

- `ISRC` (identifies a recording; often shared across multiple releases)
- `ORIGINALRELEASEDATE` or similar original‑date tags, where used[^origdate]

These are highly useful for matching and cross‑checking, but they typically do **not** distinguish between later reissues that reuse the same recordings.

### 2.4 Display / enrichment fields

Fields that improve browsing and discovery but should not be used to encode workflow state:

- `GENRE`
- `COMPOSER`
- `WORK`, `PART`, `SECTION`, `WORKID`
- `CONDUCTOR`, `ENSEMBLE`, `SOLOIST`, `PERSONNEL` and other performer credits
- `COUNTRY`, `LANGUAGE`, `PERIOD`, `FORM`
- artwork and embedded images
- review‑like or descriptive text where appropriate

Roon can use both file and Roon genres and credits depending on Import Settings.[^genre-settings][^file-tags]

### 2.5 Operational metadata (must not pollute identity)

Fields, flags and notes that describe workflow or technical state, **not** the musical work itself. These must never be written into identification‑critical or edition‑specific fields:

- rip status, download source, shop name
- codec and container (FLAC, AAC, ALAC, WEB, Lossless, 24‑96)
- quality ratings like "Needs Review", "Duplicate", "Corrupt"
- internal queue or reacquire flags
- tool names or pipeline stages

Operational metadata belongs in:

- sidecar files or databases
- non‑identity fields such as `COMMENT`
- Roon’s own tags feature via `ROONALBUMTAG` / `ROONTRACKTAG`, which Roon imports as user tags without changing identity fields.[^tags][^roon-tag-import]

---

## 3. Field Requirements

### 3.1 Album‑level checklist

Every release should have these written cleanly:

| Field | Content | Class |
| :-- | :-- | :-- |
| `ALBUM` | Exact official release title | Identification‑critical |
| `ALBUMARTIST` | Main artist or `Various Artists` only where appropriate | Identification‑critical |
| `DATE` | Release date or at minimum release year for **this edition** | Identification‑critical / edition‑specific |
| `ORIGINALRELEASEDATE` | Original issue date, if used | Recording‑identity / historical |
| `LABEL` | Label name | Edition‑specific |
| `CATALOGNUMBER` | Catalogue number | Edition‑specific |
| `BARCODE` / `UPC` | Barcode / UPC if known | Edition‑specific |
| `GENRE` | Controlled genre vocabulary | Enrichment |
| `DISCNUMBER` | Disc number for multi‑disc sets | Identification‑critical |
| `DISCTOTAL` / `TOTALDISCS` | Total number of discs for this edition | Edition‑specific |
| `TRACKTOTAL` / `TOTALTRACKS` | Canonical number of tracks (see §5.3) | Edition‑specific |

### 3.2 Track‑level checklist

| Field | Content | Class |
| :-- | :-- | :-- |
| `TITLE` | Exact track title, including official mix/version | Identification‑critical |
| `TRACKNUMBER` | Track position on its disc | Identification‑critical |
| `DISCNUMBER` | Disc position for multi‑disc releases | Identification‑critical |
| `ARTIST` | Track artist | Identification‑critical |
| `COMPOSER` | Composer where relevant | Enrichment (critical for classical) |
| `ISRC` | Track ISRC if known | Recording‑identity |
| `WORK` / `PART` / `SECTION` / `WORKID` | For multi‑part classical works | Enrichment (important for grouping) |
| `ENSEMBLE`, `SOLOIST`, `PERSONNEL` | Detailed performance credits | Enrichment |

Where your tagger offers additional Roon‑mapped fields (for example via user‑defined text frames for `WORK`, `PART`, `ENSEMBLE`, `SOLOIST`, `WORKID`), use those mappings consistently.[^file-tags]

---

## 4. Album and Artist Rules

### 4.1 Album title (`ALBUM`)

Do:

| Rule | Example |
| :-- | :-- |
| Use the official release title | `Watergate 24` |
| Keep subtitle if part of release | `Fabric 99: Sasha` |
| Keep edition text only when it identifies a distinct release | `Selected Ambient Works 85–92` |
| Keep titles free of folder‑year prefixes | `Watergate 24`, not `(2018) Watergate 24` |

Do **not**:

| Bad value | Problem |
| :-- | :-- |
| `(2018) Watergate 24` | Folder naming leaked into `ALBUM` |
| `Watergate 24 [FLAC]` | Format is not part of the title |
| `Watergate 24 WEB` | Source is not part of the title |
| `Watergate 24 (Fixed)` | Workflow state in an identity field |

### 4.2 Album artist (`ALBUMARTIST`)

| Release type | `ALBUMARTIST` policy |
| :-- | :-- |
| Single‑artist album | Main artist |
| Duo / shared credit | Official joint credit (e.g. `Artist A & Artist B`) |
| DJ mix credited to one DJ | The DJ/compiler if the release is officially credited that way |
| Label compilation | `Various Artists` |
| Multi‑artist compilation | `Various Artists` |
| Soundtrack with many artists | Usually `Various Artists` unless officially credited otherwise |
| Classical album | Main performer/ensemble/conductor; put composer in `COMPOSER` |

Use `Various Artists` only for genuine compilations, not as a fallback when tagging is uncertain.

### 4.3 Track artist (`ARTIST`)

- On single‑artist albums, `ARTIST` usually matches `ALBUMARTIST`.
- On compilations and DJ mixes, `ALBUMARTIST` is the compiler or `Various Artists`, and `ARTIST` is the track‑level performer.
- Never set both `ALBUMARTIST` and `ARTIST` to `Various Artists` on compilations; doing so erases valuable information.

### 4.4 Featured artists

Pick one consistent convention for features and keep it aligned with the official release:

- Put the feature in `TITLE` as `Track Title (feat. Name)` **only** if the official title uses it.
- Keep `ARTIST` focused on the main performing artist rather than turning every feature into a new artist‑string variant.
- Use structured credits (`PERSONNEL`, `SOLOIST` or equivalent) for detailed roles where your tools support them.[^file-tags]

---

## 5. Dates, Years and Release Structure

### 5.1 Date fields

Roon’s metadata model distinguishes **Release Date** and **Original Release Date**, both of which can come from file tags or from Roon’s own metadata.[^metadata-model] Many taggers and Roon users successfully use `DATE` for the edition release date and `ORIGINALRELEASEDATE` (or similar) for the original issue date, but mappings vary by software.[^origdate]

Policy:

| Field | Meaning |
| :-- | :-- |
| `DATE` | Release date (or year) of **this specific edition** represented by the files |
| `ORIGINALRELEASEDATE` | First‑issue date for the album/recordings, if used |

Prefer full dates (`YYYY‑MM‑DD`) where reliable; otherwise use a four‑digit year.

### 5.2 What not to write

Avoid:

| Value | Problem |
| :-- | :-- |
| `0000` | Invalid; weakens identification and confuses sort order |
| Empty date where a reliable year is known | Avoidable ambiguity |
| Rip or download year as `DATE` | Process data, not release data |
| Original year in `DATE` for a later remaster/reissue | Can point Roon to the wrong edition |

When original and reissue dates differ, set `DATE` to the edition you actually own and use `ORIGINALRELEASEDATE` only if you need to surface original‑issue history.

### 5.3 Canonical structure and `TOTALTRACKS`

The **canonical release’s track/disc structure is authoritative**:

- `TRACKNUMBER` and `DISCNUMBER` must reflect the published structure, not arbitrary local ordering.
- `TOTALDISCS` and `TRACKTOTAL` / `TOTALTRACKS` must reflect the canonical number of discs/tracks for the edition, **not** simply `count(files present)` when files are missing.

Policy on `TOTALTRACKS`:

- When written at track level, `TOTALTRACKS` (or `TRACKTOTAL`) should represent the total number of tracks on the **disc referenced by `DISCNUMBER`**.
- If you choose to represent whole‑release totals instead (e.g. a single disc containing all tracks of a box set), keep that convention consistent across your library and avoid mixing per‑disc and whole‑release semantics.
- Do **not** use different meanings for the same field name in different parts of the collection.

If your local copy is incomplete (e.g. missing bonus tracks), you may either:

- keep the canonical totals and accept local gaps; or
- leave totals unset and let Roon rely on `TRACKNUMBER`/`DISCNUMBER`.

Do **not** renumber tracks to form a fake contiguous sequence or shrink totals to match an incomplete rip unless you have consciously chosen to represent a different edition.

### 5.4 Single‑disc and multi‑disc numbering

Single‑disc:

| Field | Example |
| :-- | :-- |
| `TRACKNUMBER` | `1`, `2`, `3` |
| `TOTALTRACKS` | `10` |
| `DISCNUMBER` | `1` or omitted |
| `DISCTOTAL` | `1` or omitted |

Multi‑disc (per‑disc numbering is preferred unless the release officially uses continuous numbering):

| Disc | Recommended `TRACKNUMBER` |
| :-- | :-- |
| Disc 1 | `1–12` |
| Disc 2 | `1–12` (not `13–24`) |

Roon’s Identify Album workflow aligns local disc/track structure with the release structure; inconsistent numbering increases the need for manual alignment.[^identify-albums]

---

## 6. Compilations and Various Artists

### 6.1 Correct VA structure

For genuine compilations:

| Field | Value |
| :-- | :-- |
| `ALBUM` | Official compilation title |
| `ALBUMARTIST` | `Various Artists` |
| `ARTIST` | Actual track artist |
| `DATE` | Compilation release date |
| `LABEL` | Compilation label |
| `CATALOGNUMBER` | Compilation catalogue number |
| `TRACKNUMBER` | Track order within the compilation |

### 6.2 `COMPILATION=1`

Some software writes a `COMPILATION` flag (for example `COMPILATION=1` or an equivalent MP3/iTunes flag) to group compilation tracks. This can be useful for cross‑player compatibility.

Roon’s published metadata model documents `Is Compilation?` as a property whose source is **Roon or Edit**, not File.[^metadata-model] Roon’s official File Tag Best Practice article does not describe `COMPILATION` as a general identification control either.[^file-tags]

**Policy:**

- You may write `COMPILATION=1` (or similar) for the benefit of other players.
- This policy makes **no claim** that Roon will use that flag for identification; do not rely on it as a primary control.
- Always set `ALBUMARTIST` and `ARTIST` correctly as above; these remain the primary controls for compilations.

### 6.3 VA versus artist‑folder duplicates

When the same audio appears under both a VA compilation and an artist‑centric release, do not assume one is wrong. Legitimate scenarios include:

- a track appears on an artist album and on a label compilation
- the same recording appears on a DJ mix and an unmixed EP
- the same track appears on a single, EP and album
- anthology/greatest‑hits releases overlapping with original albums

Policy:

- Keep distinct releases that represent different real‑world contexts.
- Collapse only clearly misfiled duplicates (for example, the same compilation mis‑tagged once as VA and once as a single‑artist album).
- Use release‑level evidence (title, label, catalogue number, barcode, structure) rather than audio identity alone.

---

## 7. Remixes, Versions, DJ Mixes and Unmixed Editions

### 7.1 Track titles and versions

For dance and electronic music in particular, the mix or version name is part of the identity:

| Case | `TITLE` |
| :-- | :-- |
| Original mix | `Track Title` or `Track Title (Original Mix)` if official |
| Remix | `Track Title (Remixer Remix)` |
| Dub | `Track Title (Dub Mix)` |
| Radio edit | `Track Title (Radio Edit)` |
| Extended mix | `Track Title (Extended Mix)` |
| Instrumental | `Track Title (Instrumental)` |

Do **not** move version information into filenames or comments while leaving tags generic.

### 7.2 Remix and mix artists

- Keep `ARTIST` as the official main artist.
- Encode the mix/remix credit in `TITLE` as above.
- Where your tools support explicit remixer/personnel fields, use them instead of overloading `ARTIST`.

### 7.3 DJ mixes vs unmixed editions

Treat DJ mixes and unmixed releases as distinct releases when both exist:

- DJ mix: `ALBUM` is the official mix title, `ALBUMARTIST` is the DJ/compiler (if credited), `ARTIST` holds track‑level artists.
- Unmixed EP/album: tagged as its own release, with its own `ALBUM`, `CATALOGNUMBER`, `DATE`, etc.

Do **not** merge them or rewrite one into the other even if some tracks are identical.

---

## 8. Classical Metadata

### 8.1 Roon’s classical model

Roon has a specialised classical model with compositions, works, parts, periods, forms, conductors, ensembles and soloists.[^metadata-model][^file-tags] Classical releases therefore require more structure than artist/album/track alone.

### 8.2 Recommended classical fields

| Field | Use |
| :-- | :-- |
| `COMPOSER` | Composer of the work |
| `WORK` | Composition or work title |
| `PART` | Movement or part title |
| `SECTION` | Higher‑level grouping where needed (e.g. acts) |
| `WORKID` | Stable identifier that distinguishes one composition from another and keeps recordings of the same `WORK` together |
| `CONDUCTOR` | Conductor |
| `ENSEMBLE` | Orchestra or ensemble |
| `SOLOIST` | Named soloists |
| `PERSONNEL` | Additional performer credits |
| `ALBUMARTIST` | Main performer/ensemble/conductor depending on release |

Where you add multi‑part file tags to an identified album, set the album’s multi‑part composition grouping to **Prefer File** so Roon honours your WORK/PART structure.[^file-tags][^work-part-prefer-file]

### 8.3 Classical safeguards

- Do not collapse multi‑movement works as duplicates based only on similar titles or durations.
- Do not strip movement numbers or part identifiers from titles where they help distinguish movements.
- Do not treat short movements as corrupt merely because they are brief or differ in duration from another recording.
- Do not apply VA compilation logic to classical box sets without checking the intended work and disc structure.

---

## 9. Genres and Other Enrichment

### 9.1 Genre policy

Roon can use genres from file tags, from its own metadata, or both, controlled in **Settings → Library → Import Settings**.[^genre-settings] Roon also supports post‑import genre editing and mapping.[^editing-grooming]

Policy:

- Use a controlled genre vocabulary in file tags.
- Decide whether you want file genres only, Roon genres only, or a combination, and configure Import Settings accordingly.
- Keep genres focused on musical style, not process data.

### 9.2 Keep workflow out of `GENRE`

Do **not** write into `GENRE`:

- formats (`FLAC`, `AAC`, `ALAC`, `WEB`, `Lossless`)
- workflow states (`Needs Review`, `Duplicate`)
- tool names or DJ software labels
- download stores or sites

Use tags, comments or external systems for those concerns.

---

## 10. Operational vs Release Metadata

### 10.1 Clean separation

Identity and edition fields (`ALBUM`, `TITLE`, artists, dates, label, catalogue number, barcode, structure) must describe the real‑world release, not maintenance history.

Examples of what **not** to do:

| Bad metadata | Problem |
| :-- | :-- |
| `Album [24‑96]` | Encoding parameters in `ALBUM` |
| `Track Title - checked` | Workflow marker in `TITLE` |
| `Genre=Needs Dedupe` | Workflow state in `GENRE` |
| `Album (2024 remaster maybe)` | Uncertainty embedded in identity |

### 10.2 Where to put operational state safely

Use:

- `COMMENT` or other non‑identity tags for provenance or light technical notes.
- Roon tags via `ROONALBUMTAG` / `ROONTRACKTAG` to reflect rating, queues or worklists inside Roon without affecting identification.[^tags][^roon-tag-import]
- External databases, sheets or reports for detailed dedupe status, reacquire lists, corruption status and codec provenance.

---

## 11. Strong Safeguards

### 11.1 Ambiguous release matches

When available evidence does not clearly point to a single release or edition, **do not guess**:

- Prefer leaving identification unresolved over forcing a likely‑wrong match.
- When using Roon’s **Identify Album** dialogue, choose the conservative option (or "None of these"), then improve tags and try again.[^identify-albums]

### 11.2 Incomplete releases

When a rip or download is incomplete:

- Keep canonical `TRACKNUMBER` and `DISCNUMBER` where known.
- Do **not** renumber remaining tracks to close gaps.
- Do **not** set `TOTALTRACKS` equal to the number of files unless that matches a real edition.
- Consider marking such folders outside your identity tags so they can be reacquired later.

### 11.3 Various Artists releases

- Use `ALBUMARTIST=Various Artists` only when the release genuinely is a compilation.
- Keep track‑level `ARTIST` values accurate; never flatten all track artists to `Various Artists`.
- Beware of spurious compilation flags from other software; verify with the actual packaging or reliable release data.

### 11.4 DJ mixes and unmixed editions

- Treat DJ mixes, unmixed EPs, singles and album releases as separate releases when they exist separately.
- Do not collapse them simply because their audio files are identical or closely related.

### 11.5 Remixes and versions

- Preserve official mix/version names exactly.
- Do not re‑label different mixes as if they were the same track to force deduplication.

### 11.6 Reissues and original release dates

- Ensure `DATE` refers to the specific edition owned, not always the first historical release.
- Use `ORIGINALRELEASEDATE` (or equivalent) cautiously to carry original issue history; verify how your tagger and Roon map it before relying on it.[^origdate][^file-tags]

### 11.7 Multi‑disc releases

- Preserve official disc boundaries and disc titles where available.
- Use per‑disc numbering unless the official release clearly uses continuous numbering.
- Ensure disc folders and tags are aligned before importing; this simplifies Roon’s disc grouping and reduces the need for manual fix‑ups.[^multi-disc-forum]

### 11.8 Classical work/part structure

- Only write `WORK`, `PART`, `SECTION` and `WORKID` where you can do so accurately.
- Once written, set the album’s multi‑part composition grouping to **Prefer File** to make Roon honour your grouping.[^file-tags][^work-part-prefer-file]

### 11.9 Duplicate audio in different release contexts

- Do not collapse distinct releases based solely on byte‑identical audio.
- Respect singles, EPs, albums, box sets, anthologies and compilations as separate objects; Roon’s metadata model naturally supports multiple releases of the same recordings.[^metadata-model]

### 11.10 Lossy AAC vs ALAC and other formats

- `.m4a` containers can hold either ALAC (lossless) or AAC (lossy); they must not be treated as lossless by default.
- Never transcode lossy AAC to FLAC or ALAC and then tag it as archival lossless; doing so misrepresents the true source quality.
- Roon reads technical format information from the files and reports it in **File Info**, but you remain responsible for honest tagging.[^faq-files-view-info]

### 11.11 Corrupt or truncated files

- Do not "fix" corruption by altering tags to hide it.
- Investigate corruption externally; re‑rip, re‑download or remove files as appropriate.
- Use Roon’s "Skipped Files" and "Corrupt" indicators as signals to repair the underlying files, not as a reason to weaken your tagging rules.[^skipped-files]

### 11.12 Destructive deletion through Roon

- Roon will not modify your audio files except when you explicitly request deletion, which removes files from storage.[^faq-files]
- Always maintain a filesystem‑level backup independent of Roon.
- Avoid performing bulk destructive deletions from within Roon until you have validated that tags and release identities are correct.

### 11.13 Ambiguity refusal

For any automated sanitizer or workflow:

- When evidence from tags and providers conflicts or is insufficient, prefer **refusing to change tags** over guessing.
- Surface such cases for manual review instead of applying speculative "fixes".

---

## 12. External Providers as Evidence

External providers can help you gather evidence about releases, but no provider is trusted blindly.

### 12.1 Edition‑first principle

To avoid constructing nonexistent "Frankenstein" editions:

- First, choose a single, coherent target edition based on the best available evidence (track list, structure, label, catalogue number, barcode, dates, packaging, etc.).
- Only once that edition has been selected should you fill in fields from that edition.
- Provider data from different sources must **corroborate** the chosen edition, not be mixed per‑field to assemble a hybrid that does not correspond to any real release.

When no candidate edition matches your files cleanly, prefer ambiguity refusal (§11.13) over forced alignment.

### 12.2 Provider roles

- **Qobuz, TIDAL and similar services**: useful for seeing likely matches in their catalogues, including track structures and dates. Roon maintains its own enriched metadata database and does not simply reflect streaming service APIs, so treat these as **evidence**, not as a direct view of what Roon "recognises".[^metadata-model]
- **Spotify and similar services**: can corroborate UPCs, ISRCs, dates and track structures but may contain localised or simplified variants.
- **Beatport and similar DJ stores**: especially valuable for electronic music, official mix names, labels, catalogue numbers, track orders and release dates.

Policy:

- Use providers as evidence sources *for selecting a real edition*.
- Once an edition is chosen, treat provider data as corroboration for filling specific fields.
- When nothing lines up cleanly, fall back to ambiguity refusal (§11.13).

---

## 13. Safe Sanitizer Behaviour

Any automated sanitizer or tag‑writer that implements this policy must behave conservatively.

### 13.1 Execution safety

- Run in **dry‑run mode** by default: calculate proposed changes and report them without touching files.
- Require explicit opt‑in for writing tags (for example, a dedicated "apply" or "commit" step).
- Preserve audio data and embedded artwork; never alter or recompress them.
- Preserve unrelated valid tags: only change fields that are explicitly in scope for the operation.

### 13.2 Transparency and verification

- Generate a human‑readable report or log of every proposed and applied change at the field level.
- Include enough context (file path, key tags before/after) for later auditing.
- After writing, re‑read the tags and verify that written values match what was intended.
- Avoid rewriting tags unnecessarily (idempotent behaviour where possible).

### 13.3 Ambiguity and safeguards

- Apply strict ambiguity refusal: if the sanitizer cannot identify a single, well‑supported target edition (§12.1) and corresponding tag values, it must leave fields unchanged and flag items for manual review.
- Never silently drop tracks, albums or discs because they are "unexpected"; surface them instead.

This behaviour keeps the policy stable even as specific toolchains evolve.

---

## 14. Roon Import Settings and Rescan Workflow

### 14.1 Import Settings overview

Roon’s Import Settings, under **Settings → Library → Import Settings**, control how Roon balances data from file tags versus its own metadata.[^import-settings]

Key points:

- "Prefer File" means "prefer file tags when they exist", not "ignore Roon entirely".[^import-settings]
- Changing Import Settings causes Roon to re‑evaluate metadata for existing files based on stored tags; it does not require moving files.[^import-settings-forum]

### 14.2 Suggested settings once tags follow this policy

For a well‑tagged local library:

- Prefer **File** for identification‑critical fields (`ALBUM`, `ALBUMARTIST`, `ARTIST`, `TITLE`, release date) when you have curated them.
- Prefer **File** for classical multi‑part composition grouping where you maintain `WORK`/`PART` tags.[^file-tags][^work-part-prefer-file]
- Use a combination of File and Roon genres depending on whether you value your own taxonomy, Roon’s, or both.[^genre-settings]
- Prefer Roon for extended credits, reviews and biographies unless you curate them yourself.

### 14.3 Rescan and Identify Album workflow

When tags change externally:

1. Ensure your tag edits are saved.
2. In Roon, navigate to the album or the relevant storage location.
3. Use **Rescan** (album or storage) to have Roon re‑read tags and re‑evaluate metadata.[^metadata-updates]
4. Inspect whether the album is now correctly identified.
5. If not, open **Album → … → Edit → Identify Album** and search for the best match.[^identify-albums]
6. Align your tracks with the proposed track list, paying attention to disc/track numbering.
7. Save the identification.
8. Apply manual Roon edits only for remaining display issues, understanding that such edits "freeze" those fields against some future metadata updates.[^editing-grooming]

To see what Roon reads from your files, use **View File Info → File Tags** on a track.[^faq-files-view-info]

---

## 15. Practical Tagging Templates

These templates show typical combinations that follow this policy. Adjust fields as necessary for your tagger and file format.

### 15.1 Single‑artist album

```text
ALBUM=Album Title
ALBUMARTIST=Artist Name
ARTIST=Artist Name
DATE=2024
ORIGINALRELEASEDATE=
LABEL=Label Name
CATALOGNUMBER=CAT123
BARCODE=1234567890123
DISCNUMBER=1
DISCTOTAL=1
TRACKNUMBER=1
TOTALTRACKS=10
TITLE=Track Title
GENRE=House
ISRC=
```

### 15.2 Various Artists compilation

```text
ALBUM=Compilation Title
ALBUMARTIST=Various Artists
ARTIST=Actual Track Artist
DATE=2024
LABEL=Label Name
CATALOGNUMBER=COMP123
BARCODE=1234567890123
DISCNUMBER=1
DISCTOTAL=1
TRACKNUMBER=1
TOTALTRACKS=20
TITLE=Track Title (Official Mix Name)
GENRE=House
ISRC=
```

### 15.3 DJ mix

```text
ALBUM=DJ-Kicks: Artist Name
ALBUMARTIST=Artist Name
ARTIST=Actual Track Artist
DATE=2024
LABEL=!K7 Records
CATALOGNUMBER=K7424CD
DISCNUMBER=1
DISCTOTAL=1
TRACKNUMBER=1
TITLE=Track Title (Mix/Version)
GENRE=House
ISRC=
```

Use the DJ as `ALBUMARTIST` only when the release is credited that way. Track artists remain the underlying performers.

### 15.4 Remix EP

```text
ALBUM=Release Title
ALBUMARTIST=Main Artist
ARTIST=Main Artist
DATE=2024
LABEL=Label Name
CATALOGNUMBER=CAT123
DISCNUMBER=1
DISCTOTAL=1
TRACKNUMBER=2
TOTALTRACKS=4
TITLE=Track Title (Remixer Remix)
GENRE=Deep House
ISRC=
```

### 15.5 Classical album

```text
ALBUM=Symphonies Nos. 5 & 7
ALBUMARTIST=Conductor Name; Orchestra Name
ARTIST=Orchestra Name
COMPOSER=Ludwig van Beethoven
WORK=Symphony No. 5 in C minor, Op. 67
PART=I. Allegro con brio
SECTION=
WORKID=
CONDUCTOR=Conductor Name
ENSEMBLE=Orchestra Name
SOLOIST=
DATE=2018
ORIGINALRELEASEDATE=
LABEL=Label Name
CATALOGNUMBER=CAT123
DISCNUMBER=1
DISCTOTAL=1
TRACKNUMBER=1
TOTALTRACKS=8
TITLE=I. Allegro con brio
GENRE=Classical
ISRC=
```

---

## 16. Pre‑Import Checklist

Before importing or rescanning in Roon, confirm:

### 16.1 Album‑level

- [ ] `ALBUM` matches the official title; no folder prefixes or format flags.
- [ ] `ALBUMARTIST` is correct; `Various Artists` used only when appropriate.
- [ ] `DATE` is valid and not `0000`.
- [ ] `ORIGINALRELEASEDATE` (where used) correctly reflects original issue history.
- [ ] `LABEL` present if known.
- [ ] `CATALOGNUMBER` present if known.
- [ ] `BARCODE` / `UPC` present if known.
- [ ] `DISCTOTAL` / `TOTALDISCS` matches the canonical disc count.
- [ ] `TOTALTRACKS` reflects canonical structure, not just file count.
- [ ] No workflow or format labels in identity fields.

### 16.2 Track‑level

- [ ] `TITLE` is exact, including official mix/version text.
- [ ] `TRACKNUMBER` and `DISCNUMBER` are correct for the release structure.
- [ ] `ARTIST` is the true track artist; compilations are not flattened.
- [ ] `COMPOSER` present where relevant.
- [ ] `ISRC` present where known.
- [ ] No quality or workflow markers in `TITLE`.

### 16.3 File/format and safety

- [ ] AAC is not misrepresented as lossless; `.m4a` ALAC vs AAC is correctly distinguished.
- [ ] Duplicate audio in distinct release contexts is handled consciously, not collapsed blindly.
- [ ] Incomplete releases are identified and not silently renumbered.
- [ ] Corrupt or truncated files are flagged for repair, not masked with tags.
- [ ] Filesystem and Roon database backups exist before major changes or deletions.

---

## 17. Synthesis Notes

This policy synthesises and simplifies earlier internal guides while correcting over‑strong or contradictory claims.

Retained:

- The structural emphasis on field classes, strong safeguards, and ambiguity refusal.
- Incomplete‑release handling, multi‑disc and classical work/part guidance.
- Sanitizer safety rules (dry‑run by default, explicit execution, preservation of audio/artwork, detailed reporting, and post‑write verification).
- Practical tagging templates and the pre‑import checklist.

Adjusted or removed:

- Over‑promising language about "making" Roon reliably identify releases has been softened to "improve Roon’s chances"; Roon’s matching remains proprietary and under Roon’s control.
- Credits and genres are no longer described as primary identification inputs, in line with Roon’s own guidance that focuses on album/track titles, artists, dates and structural fields.[^file-tags]
- `COMPILATION=1` is now treated purely as cross‑player compatibility metadata; the policy no longer claims that Roon sources compilation status from file tags, consistent with the documented "Is Compilation? (Roon or Edit)" field.[^metadata-model]
- `ISRC` and `ORIGINALRELEASEDATE` have been reclassified as recording‑identity and historical fields instead of pure edition discriminators, since they commonly apply across multiple releases.
- Provider usage has been constrained by an explicit edition‑first principle: tools must select a coherent real‑world edition before filling fields, and may not mix evidence per field to create hybrid "Frankenstein" releases.
- `TOTALTRACKS` semantics have been clarified: by default, it should represent per‑disc track counts at track level, and any decision to use whole‑release totals must be consistent across the library.
- `WORKID` is now described as a composition‑level identifier that keeps recordings of the same work together, matching Roon‑oriented community guidance.
- The citation appendix has been reduced to directly used sources; unused and irrelevant links, nested footnotes and hidden spans have been removed.

Overall, the document aims to be stable as implementation details evolve: tools and pipelines should conform to this policy, rather than the policy mirroring current code.

---

[^file-tags]: Roon Labs, "File Tag Best Practice" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/file-tag-best-practice

[^metadata-model]: Roon Labs, "Metadata Model" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/metadata-model

[^import-settings]: Roon Labs, "Import Settings" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/import-settings

[^editing-grooming]: Roon Labs, "Editing and Grooming Your Collection" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/editing-and-grooming-your-collection

[^metadata-updates]: Roon Labs, "Metadata Updates" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/metadata-updates

[^identify-albums]: Roon Labs, "Identifying Albums" (Roon Help Center).

[^genre-settings]: Roon Labs, "Genre Settings" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/genre-setting

[^faq-files]: Roon Labs, "FAQ: Will Roon alter my audio files or tags in any way when I import them?" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/faq-will-roon-alter-my-audio-files-or-tags-in-any-way-when-i-import-them

[^faq-files-view-info]: Roon Labs, "FAQ: Where can I find additional information about my audio files, like tags, file quality and storage location?" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/faq-where-can-i-find-additional-information-about-my-audio-files-like-tags-file-quality-and-storage-location

[^export]: Roon Labs, "Export" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/export

[^tags]: Roon Labs, "Tags" (Roon Help Center). https://help.roonlabs.com/portal/en/kb/articles/tags

[^roon-tag-import]: Roon Labs Community, "Roon File Tag processing" and related topics on importing file tags into Roon tags. https://community.roonlabs.com/t/roon-file-tag-processing/111994

[^origdate]: Roon Labs Community, discussions of original release date tags and their mapping into Roon. For example: https://community.roonlabs.com/t/originally-released-vs-released-problems/28119 and https://community.roonlabs.com/t/originalyear-field-mp3tag-not-the-same-as-in-roon/155601

[^work-part-prefer-file]: Roon Labs Community, guidance on using `WORK`/`PART` tags with "Prefer File" multi‑part grouping, e.g. https://community.roonlabs.com/t/how-to-edit-work-part/125615

[^multi-disc-forum]: Roon Labs Community, multi‑disc and track‑numbering discussions, e.g. https://community.mp3tag.de/t/autonumbering-tracknumber-reset-counter-for-each-album/58132?page=2

[^skipped-files]: Roon Labs Community, "Skipped Files" and import troubleshooting threads, e.g. https://community.roonlabs.com/t/roon-fails-to-import-all-album-tracks-ref-aovn1e/294912

[^import-settings-forum]: Roon Labs Community, discussions confirming that Import Settings affect existing albums as Roon re‑evaluates stored tags, e.g. https://community.roonlabs.com/t/have-roon-use-tag-data-for-all-existing-albums/23751
