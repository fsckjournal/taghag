# Taghag DJ Intelligence and Cuecifer Integration

## Experimental Handover and Validation Report

## 1. Executive Summary

In an hour or two, an exploratory Gemini session moved from intercepted
Beatport DJ browser traffic to a working experimental decoder, a database
integration, and an initial audio-empirical validation packet.

The session did not begin with a decoder specification. The operator opened
Beatport DJ in Chromium, enabled automix and shuffle, played tracks, captured
the resulting requests, and asked what was happening under the hood. Gemini
inspected the available API traffic and repeatedly revised its interpretation
of an undocumented `iwebdj` payload while comparing server fields, catalog
metadata, interface behavior, and local audio.

The result is a substantial prototype in the separate `taghag` repository:

- retrieval of private Beatport DJ metadata from
  `dj.beatport.com/api/metadata.php`;
- provisional decoding of BPM, phase, beat-level energy, and structural data;
- Beatport catalog resolution by ISRC and search;
- Postgres storage for cues, segments, embeddings, and human curation;
- Cuecifer-style sonic discovery using seven-dimensional vectors;
- Pioneer ANLZ ingestion and beam-search transition planning;
- a 481-track validation manifest derived from the canonical Tagslut library;
- a 12-track live validation packet using Beatport responses and local FLAC
  audio;
- a dedicated decoder test module, written and executed during validation.

The validation materially advances two claims:

1. For the tested Format 2 payloads, `a1` deterministically encodes BPM through
   a linear relation.
2. The decoded `bm0`/`bm1` character streams are strongly correlated with
   beat-centered audio energy.

The work does not yet establish exact full-track beatgrid recovery, the
semantics of `km0`/`km1`, correct intro/outro cues, or Beatport DJ's complete
automix decision process.

## 2. Why This Investigation Happened

The original Taghag/Cuecifer plan treated Beatport primarily as a catalog
metadata provider. That framing accounted for identity, BPM, key, release
metadata, and duration, but not for the behavior of Beatport DJ itself.

The operator challenged that limitation:

> The DJ app endpoints should tell us more about the automix and how it decides
> what to cue.

The decisive evidence was not an official API document. It was an intercepted
request collection produced while Beatport DJ was actively playing in automix
and shuffle mode. The collection exposed endpoint families including:

- `api/metadata.php`
- `api/metadata2.php`
- `api/xcueget.php`
- `api/xupdate.php`
- Beatport catalog and stream endpoints
- Needledrop media requests

The `metadata.php` response contained an opaque delimited payload:

```text
iwebdj=0.13!error=000!length=448.795!bpm=126.0!gain=-9.01!
peak=1.000!br=12!a0=1180.590698242!a1=-888.137573242!
a2=3268.588378906!a3=6433.327148437!a4=259.071406163!
a5=1261.631169865!db0=0!db1=0!bm0=...!bm1=...!km0=...!km1=...
```

That response changed the investigation. Instead of asking only what Beatport
could say about a track, the session began asking what Beatport DJ had already
computed in order to play and mix it.

## 3. Discovery Process

The process was iterative rather than linear.

### 3.1 Initial inspection

Gemini first examined the conventional Beatport collection: OAuth clients,
catalog lookup, ISRC search, response normalization, duration authority, and
evidence records. Those endpoints did not provide the desired audio structure.

### 3.2 Scope correction

After the operator clarified that the target was Beatport DJ automix behavior,
Gemini moved into the captured `dj.beatport.com` request collection and found
the iWebDJ metadata payload.

### 3.3 Hypothesis formation

The first interpretations were speculative. Fields `a0`-`a5` were initially
described as cue anchors, `bm*` as beat markers, and `km*` as phrase or
harmonic maps. Those descriptions were useful search hypotheses but were not
yet evidence.

### 3.4 Executable reconstruction

Rather than ending with a prose interpretation, Gemini implemented the
hypotheses in `beatport_resolver.py`. This made every assumption inspectable
and falsifiable.

### 3.5 Challenge and validation

When asked to substantiate the reverse engineering, Gemini used the 481-track
manifest supplied from Tagslut, selected tracks with Beatport IDs and mounted
FLAC masters, fetched live payloads, processed local audio with FFmpeg, ran
regressions and correlations, examined phase alignment, and wrote a dedicated
test module.

The session repeatedly moved between response inspection, formulas, code,
audio, and revised interpretation. That trial-and-error loop is material to the
result: the decoder was not copied from documentation; it emerged from active
correlation against observable behavior.

## 4. Implementation Delivered

Commit `62cbbbc` in `taghag` added approximately 2,000 lines across sixteen
files. Principal components include:

| Component | Purpose |
| --- | --- |
| `beatport_resolver.py` | Catalog resolution, iWebDJ retrieval and decoding |
| `beatport_auth.py` | Beatport token retrieval |
| `advanced_cue_planner.py` | ANLZ ingestion, segment features, beam search |
| `sonic_discovery.py` | Seven-dimensional sonic vectors and vibe rules |
| `generate_neighborhood_crate.py` | Similarity crate generation |
| `essentia_adapter.py` | Essentia-derived analysis integration |
| `apply_human_correction.py` | Persistent human curation |
| `sync_vibes_to_id3.py` | Tag interoperability |
| `20260611000000_cuecifer_cue_revival.sql` | Unified analysis view |

Supporting migrations define `track_embedding`, `track_curation`, `track_cue`,
`track_segment`, and `transition_edge`.

## 5. Beatport DJ Request and Authentication

The resolver reproduces the observed metadata request:

```python
def generate_iwebdj_token(user_id: int) -> str:
    b64 = base64.b64encode(str(user_id).encode("utf-8")).decode("utf-8")
    return b64.replace("=", "")[::-1]
```

```python
url = "https://dj.beatport.com/api/metadata.php?bp"
body = urllib.parse.urlencode({
    "action": "retrieve",
    "debug": "v29.92",
    "songid": clean_id,
    "token": token,
}).encode("utf-8")
```

The response is parsed as `!`-delimited key/value pairs and passed to
`decode_iwebdj_payload()`.

This is an undocumented private endpoint. Its observed availability does not
imply stability, support, or permission for unrestricted operational use.

## 6. Decoder Reconstruction

### 6.1 BPM branches

The implementation derives two candidate tempos:

```python
bpm_a0 = (a0 - 818.254) / 5.75
bpm_a1 = (25.5811 - a1) / 7.25

format_selector = 2 if bpm_a1 < 145 else 1
```

Format 1 uses `a0`, `a2`, `db0`, and `bm0`. Format 2 uses `a1`, `a3`, `db1`,
and `bm1`.

```python
if format_selector == 1:
    beat_period = 60000.0 / bpm_a0
    a2_ms = 1000.0 * (a2 - 1894.123) / 2307.2383
    beat_offset = a2_ms + db0 * beat_period
    encoded_string = parsed_dict.get("bm0", "")
else:
    beat_period = 60000.0 / bpm_a1
    a3_ms = 1000.0 * (6770.2211 - a3) / 2814.255
    beat_offset = a3_ms + db1 * beat_period
    encoded_string = parsed_dict.get("bm1", "")
```

The validation packet supports the Format 2 `a1` BPM relation. The purpose of
the 145 BPM branch and the Format 1 behavior still require a dedicated cohort.

### 6.2 Base52 decoding

The `bm*` stream uses uppercase and lowercase ASCII characters:

```python
for c in sliced:
    code = ord(c)
    value = (code - 65) if code <= 90 else (code - 71)
    char_array.append(value)
```

This maps:

- `A`-`Z` to `0`-`25`;
- `a`-`z` to `26`-`51`.

The validation results strongly support interpreting these values as a
beat-level energy envelope.

### 6.3 Beat projection

The current implementation projects a constant-tempo grid:

```python
for i in range(expected_beats_count):
    t = beat_offset + i * beat_period
    if t <= duration_ms:
        beat_times_ms.append(t)
```

This is a projection from decoded tempo and phase. It is not evidence of a
variable-tempo map.

### 6.4 Outro heuristic

The current outro estimate scans backward for a value at or above `20`, then
aligns the result to a 32-beat phrase:

```python
counter = 1
while counter < len(char_array) and char_array[-counter] < 20:
    counter += 1

last_beat_index = max(0, len(char_array) - counter)
outro_raw_ms = last_beat_index * beat_period + (beat_offset % beat_period)
```

This remains a heuristic. The current validation does not establish that
threshold `20` identifies an outro or that 32-beat rounding reproduces
Beatport DJ's chosen transition.

## 7. Validation Cohort

Tagslut exported:

`artifacts/benchmarks/dam_swindle_20260608/essentia_481_beatport_validation_manifest.csv`

The manifest contains:

- 481 unique ISRCs;
- 448 existing Beatport IDs;
- 480 canonical identity links;
- canonical artist, title, album, asset ID, and FLAC master path.

Gemini selected 12 live validation tracks:

| Beatport ID | Track | Catalog BPM | `a0` | `a1` | `db0` | `db1` |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 9256293 | Christian Löffler - York | 118 | 1157.503 | -829.918 | 0 | 0 |
| 1707587 | The Chemical Brothers - Block Rockin' Beats | 109 | 1132.721 | -767.424 | 2 | 2 |
| 13211962 | Giles Smith, Two Armadillos - Tropics | 125 | 1177.615 | -880.633 | 0 | 0 |
| 690995 | Lovelock - Don't Turn Away (Radio Edit) | 95 | 1364.512 | -1351.939 | 0 | 0 |
| 954649 | Premier Rang - Zoe Et Heine | 110 | 1134.583 | -772.119 | 0 | 0 |
| 15334256 | Jamie Anderson, Owain K - Keep It Pumping | 118 | 1157.504 | -829.919 | 0 | 0 |
| 8991184 | Flash Atkins - Drug Empire | 116 | 1151.754 | -815.418 | 0 | 0 |
| 16885615 | Rina, Eliezer - San Sebastian (Remix) | 118 | 1157.505 | -829.920 | 0 | 0 |
| 16885613 | Ost & Kjex, Trulz & Robin - Find My Love (Remix) | 118 | 1157.499 | -829.906 | 0 | 2 |
| 18709873 | Nora, Sommerfeldt - You & I | 120 | 1163.254 | -844.419 | 0 | 2 |
| 18709873 | Nora, Sommerfeldt - You & I | 120 | 1163.254 | -844.419 | 0 | 2 |
| 22235435 | Oliver Dollar - John's Church (Remix) | 120 | 1163.256 | -844.425 | 0 | 0 |
| 20546746 | Kevin McKay, KÖNI, Lou - Sun On The Sea | 122 | 1169.007 | -858.925 | 3 | 3 |

## 8. BPM Validation

For the tested Format 2 payloads, the packet reports:

```text
a1 = -7.250000000000003 * BPM + 25.581100000000106
R² = 1.000000
standard error = 0.000000
maximum residual = 2.27e-13
```

Observed catalog and decoded tempos:

| Track | Catalog BPM | Decoded BPM | Result |
| --- | ---: | ---: | --- |
| York | 118.0 | 118.00 | agreement |
| Block Rockin' Beats | 109.0 | 109.38 | near agreement |
| Tropics | 125.0 | 125.00 | agreement |
| Don't Turn Away | 95.0 | 190.00 | exact double tempo |
| Zoe Et Heine | 110.0 | 110.03 | near agreement |
| Keep It Pumping | 118.0 | 118.00 | agreement |
| Drug Empire | 116.0 | 116.00 | agreement |
| San Sebastian | 118.0 | 118.00 | agreement |
| Find My Love | 118.0 | 118.00 | agreement |
| You & I | 120.0 | 120.00 | agreement |
| John's Church | 120.0 | 120.00 | agreement |
| Sun On The Sea | 122.0 | 122.00 | agreement |

The 95/190 result shows that decoded tempo can represent a double-tempo grid.
Consumers must normalize tempo policy rather than assuming catalog equivalence.

## 9. Audio-Energy Validation

Local FLAC files were downsampled to 1000 Hz mono PCM with FFmpeg. Beat-centered
RMS windows were compared with decoded `bm*` values using Pearson correlation.

| Track | Pearson `R` | Reported `p` value |
| --- | ---: | ---: |
| John's Church | 0.989 | `1.29e-68` |
| Sun On The Sea | 0.962 | `7.26e-53` |
| You & I | 0.961 | `7.49e-20` |
| Drug Empire | 0.939 | `5.24e-25` |
| York | 0.893 | `2.25e-41` |
| Tropics | 0.890 | `1.03e-10` |

Mean reported correlation: `0.939`.

These measurements are strong evidence that the `bm*` values encode a temporal
audio-energy representation. They do not, by themselves, prove that every
symbol is raw amplitude, that the mapping is identical across both formats, or
that the stream directly determines transition points.

## 10. Phase and Beat Alignment

The packet compared projected grids with local transients near the beginning of
each track.

Some zero-shift examples produced small reported lags:

- York: `+5 ms`;
- Drug Empire: `+70 ms`;
- John's Church: `-90 ms`.

Other tracks showed offsets near integer beat counts, particularly where
`db1` was nonzero. This supports treating `db*` as an index or phase adjustment,
but the current results do not prove the exact semantics.

The packet did not measure accumulated drift at the middle and end of each
track. Exact full-track beatgrid recovery therefore remains unproven.

## 11. `km0` and `km1`

The validation established structural facts:

- `km1` length matched `bm1` length in examined tracks;
- `km0` length matched `bm0` length;
- `.` occupied large portions of several streams;
- symbols therefore align with the same beat-level timeline.

For example, `York` contained:

- `936` `km1` characters and `936` `bm1` characters;
- `468` `km0` characters and `468` `bm0` characters;
- `55.7%` `.` characters in `km1`.

This does not prove that `km*` encodes musical key, pitch class, phrase role, or
silence. The field should remain neutrally named until correlation with known
tonal analysis establishes its semantics.

## 12. Tests and Reproducibility

During validation Gemini created:

- `run_cohort_validation.py`;
- `calculate_alignment_errors.py`;
- `analyze_key_mapping.py`;
- `cohort_raw_data.json`;
- `validation_packet.md`;
- `tools/tests/test_beatport_resolver.py`.

The test module covers token generation, both format branches, boundaries,
malformed strings, and outro behavior. It was run during the session.

At the time of this report:

- `validation_packet.md` is preserved beside this report in Tagslut;
- the validation scripts and raw result JSON remain under Gemini's application
  scratch directory;
- `test_beatport_resolver.py` remains untracked in `taghag`;

The remaining scratch files and tests must be moved into a repository with
sanitized fixtures before the experiment is independently reproducible.

## 13. Database and DJ Architecture

The broader prototype connects the decoded metadata to:

- `track_cue` for cue candidates;
- `track_segment` for structural segments and local embeddings;
- `track_embedding` for sonic similarity;
- `track_curation` for operator corrections;
- `transition_edge` for transition candidates;
- `sonic_analysis` as a combined machine/human view.

The transition planner uses a weighted cost:

```text
edge_cost =
    w1 * vibe_distance
  + w2 * bpm_delta
  + w3 * camelot_distance
  + w4 * (1 - confidence)
```

The existence of these components does not establish transition quality.
Listening tests and benchmark comparisons are still required.

Taghag remains a parallel experimental system. Tagslut's canonical store
remains `music_v3.db`, and the validated Cuecifer golden playlist remains the
behavioral reference.

## 14. Confirmed Findings

The current evidence supports the following statements:

1. Beatport DJ exposes an undocumented per-track iWebDJ metadata payload.
2. The payload contains deterministic tempo-related fields.
3. The tested Format 2 `a1` relation reconstructs the encoded grid tempo.
4. Slow material may use double-tempo representation.
5. `bm0`/`bm1` are beat-aligned character streams.
6. Decoded `bm*` values correlate strongly with local audio energy.
7. `km0`/`km1` are structurally aligned to the same beat timeline.
8. The payload is sufficiently rich to justify continued investigation as a
   source of DJ-analysis evidence.

## 15. Unresolved Claims

The current evidence does not yet support:

1. exact interpretation of every `a0`-`a5` field;
2. the purpose of the 145 BPM branch;
3. exact full-track beatgrid recovery;
4. variable-tempo support;
5. the semantic alphabet of `km0`/`km1`;
6. threshold `20` as a valid outro detector;
7. 32-beat rounding as Beatport's actual transition rule;
8. reconstructed Beatport automix decisions;
9. “perfect transitions”;
10. production readiness or endpoint stability.

## 16. Next Validation Work

1. Check in sanitized raw payload fixtures, scripts, results, and decoder tests.
2. Add a Format 1 cohort above the branch threshold.
3. Add variable-tempo, non-house, malformed, and boundary cases.
4. Measure grid phase and drift at the beginning, middle, and end.
5. Record Beatport DJ automix decisions from controlled track pairs.
6. Compare predicted intro/outro anchors with observed crossfades and audible
   phrase boundaries.
7. Correlate `km*` symbols with independent chroma and key estimates.
8. Preserve raw provider evidence separately from every derived interpretation.
9. Keep cue writes disabled or dry-run-only until field semantics are stable.

## 17. Conclusion

This sprint produced more than a speculative API note. It produced an
inspectable decoder, a live validation cohort, measurable audio correlations,
and a concrete path toward reconstructing part of Beatport DJ's analysis
surface.

The important result is not that every initial hypothesis was correct. Several
were not established and remain explicitly unresolved. The important result is
that the session kept returning to evidence: captured requests, response
fields, code, catalog values, local audio, statistics, and tests.

The defensible conclusion is:

> The tested iWebDJ payloads contain deterministically encoded grid tempo and
> beat-level symbols strongly correlated with local audio energy. The endpoint
> exposes materially useful DJ-analysis data. Transition, tonal, and automix
> semantics remain under active validation.
