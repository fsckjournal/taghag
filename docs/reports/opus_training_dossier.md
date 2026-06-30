# The Cuecifer Engine — Supervised Mix-Point Heuristic (Revision 2)

> **Builds directly on the Gemini work.** Gemini ran the whole heist — the Mixonset TFLite decryption, the 22,808 Echo Nest payloads, and the curated 143-track `mixonset_analysis_report.md` — and caught the core problem itself: the original title-keyed pairing was unsafe, and label/feature coverage barely overlap. That diagnosis was right and is what made this revision quick. The one piece it left open was an exhaustive identity check against the payload dump. This revision does that check and lands a happier answer than "impossible": **2 tracks line up on both sides**, so a small but real supervised set exists.

## The pairing problem Gemini flagged
Pairing ground truth to features by track *title* isn't safe: the Spotify "Lebanese Blonde" payload is Thievery Corporation's original, while the Mixonset "Lebanese Blonde" is an unrelated house remix (*Extended Mix — Kevin McKay & Nog*) with **0 cues** — same name, different recordings. That title collision is why the first set of target tables came out empty. The fix is to pair by identity (Spotify ID) and confirm both sides exist for the same recording.

## Closing the overlap question (identity, not title)
1. Scanned the full `mixonset_analysis_report.md` (143 tracks) → **7** carry non-zero curated cue tables: Wildfires, Smoothin' Groovin', The Moodymann, Something Better, Driving Me Crazy, Steady Drummer, Drifting.
2. Resolved each `title + artist` → Spotify track ID (Spotify search), then checked for a matching `automix_payloads/<spotify_id>.json` in the local corpus — duration-sanity-checked to confirm same recording/mix.
3. Kept only tracks where **both** label and feature exist for the *same* recording.

**Result: 2 verified (feature → label) pairs — Wildfires (17 cues) and Smoothin' Groovin' (30 cues).** Gemini's coverage instinct holds for the rest: the other 5 resolve to Spotify IDs absent from the scraped subset (The Moodymann, Something Better, Driving Me Crazy, Steady Drummer) or have no Spotify release under that artist (Drifting — Proviant Audio). To grow the set, scrape automix payloads for those specific IDs (resolver is reproducible: title+artist → Spotify search → payload file).

## The modelling signal (why this is non-trivial)
The Mixonset cue timestamps **do not coincide with Echo Nest `sections` boundaries** — they fall *inside* sections (Wildfires labels at 1.89/9.27/16.66 s vs the first Echo Nest section spanning 0–15.5 s). The target cannot be read off `sections` alone; the heuristic must descend to **`segments`** (the high-resolution loudness/pitch/timbre array, omitted below for size) to find the sub-section energy inflections Mixonset fires on. `Mixability` here is the **energy gradient (ΔE)** at each cue — note the positive spikes at drops/breakdowns (Smoothin' Groovin' cue #28: ΔE **+1.12** at 7:25, the main breakdown).

## Your task
Write a deterministic `predict_cues(payload) -> list[float]` consuming Echo Nest `sections` + `segments` that reproduces the Mixonset ground-truth timestamps below (score = mean absolute onset error against matched cues), then explain the acoustic rule placing each cue.

---

## TRACK: Wildfires (Original Mix) — Mindchatter

**Identity:** Spotify `65HVJYKTgBtU0DtK69XEhM` · `automix_payloads/65HVJYKTgBtU0DtK69XEhM.json` · Echo Nest analyzer `4.0.0`
**Track-level:** tempo 129.997 · key 1/1 · duration 211.04617s · loudness -8.085 dB · 10 sections · 1165 segments (segments omitted below for size)

### 🎯 Ground Truth Targets (decrypted Mixonset TFLite cache — `mixonset_analysis_report.md`)
`Mixability` is the per-cue energy gradient (ΔE) Mixonset emits at each candidate boundary.

```text
| # | Time (s) | Time (m:s) | Local BPM | Local Energy | Mixability (ΔE) |
|---|----------|------------|-----------|--------------|-----------------|
| 1 | 0.00 | 0:00.00 | 130.00 | 0.2915 | +0.0000 |
| 2 | 1.89 | 0:01.89 | 130.00 | 0.2971 | -0.0056 |
| 3 | 9.27 | 0:09.27 | 130.00 | 0.3112 | -0.0142 |
| 4 | 16.66 | 0:16.66 | 130.00 | 0.3112 | -0.0000 |
| 5 | 24.04 | 0:24.04 | 130.00 | 0.3171 | -0.0059 |
| 6 | 31.43 | 0:31.43 | 130.00 | 0.3127 | +0.0044 |
| 7 | 38.81 | 0:38.81 | 130.00 | 0.3445 | -0.0320 |
| 8 | 46.20 | 0:46.20 | 130.00 | 0.3365 | +0.0080 |
| 9 | 48.04 | 0:48.04 | 130.00 | 0.3475 | -0.0109 |
| 10 | 62.81 | 1:02.81 | 130.00 | 0.3923 | -0.0899 |
| 11 | 84.97 | 1:24.97 | 130.00 | 0.3751 | +0.0518 |
| 12 | 114.50 | 1:54.50 | 130.00 | 0.3397 | +0.1415 |
| 13 | 121.89 | 2:01.89 | 130.00 | 0.3819 | -0.0425 |
| 14 | 144.04 | 2:24.04 | 130.00 | 0.3933 | -0.0343 |
| 15 | 188.35 | 3:08.35 | 130.00 | 0.3689 | +0.1467 |
| 16 | 203.12 | 3:23.12 | 130.00 | 0.1854 | +0.3682 |
| 17 | 210.50 | 3:30.50 | 130.00 | 0.0000 | +0.1866 |
```

### 🧠 Feature Input (Spotify Echo Nest `sections`)
```text
| # | start (s) | dur (s) | loudness (dB) | tempo | key | mode | time_sig | confidence |
|---|-----------|---------|---------------|-------|-----|------|----------|------------|
| 1 | 0.00 | 15.50 | -22.36 | 130.0 | 1 | 1 | 4 | 1.000 |
| 2 | 15.50 | 21.23 | -9.86 | 130.1 | 10 | 0 | 4 | 1.000 |
| 3 | 36.73 | 20.77 | -8.52 | 129.9 | 10 | 0 | 3 | 0.158 |
| 4 | 57.50 | 22.52 | -6.40 | 130.2 | 7 | 1 | 4 | 0.657 |
| 5 | 80.01 | 43.02 | -7.46 | 129.9 | 7 | 1 | 4 | 0.491 |
| 6 | 123.03 | 10.15 | -8.33 | 130.5 | 1 | 1 | 4 | 0.686 |
| 7 | 133.19 | 41.89 | -6.81 | 130.1 | 1 | 1 | 4 | 0.367 |
| 8 | 175.08 | 17.09 | -4.86 | 130.1 | 10 | 0 | 4 | 0.304 |
| 9 | 192.17 | 14.86 | -8.00 | 129.9 | 7 | 1 | 4 | 0.348 |
| 10 | 207.03 | 4.02 | -44.75 | 0.0 | 4 | 1 | 4 | 1.000 |
```

---

## TRACK: Smoothin' Groovin' (Original Mix) — Crazy P

**Identity:** Spotify `6w0RXOpQYDCjnIQBETYURK` · `automix_payloads/6w0RXOpQYDCjnIQBETYURK.json` · Echo Nest analyzer `4.0.0`
**Track-level:** tempo 120.84 · key 10/0 · duration 537.2653s · loudness -9.374 dB · 15 sections · 2980 segments (segments omitted below for size)

### 🎯 Ground Truth Targets (decrypted Mixonset TFLite cache — `mixonset_analysis_report.md`)
`Mixability` is the per-cue energy gradient (ΔE) Mixonset emits at each candidate boundary.

```text
| # | Time (s) | Time (m:s) | Local BPM | Local Energy | Mixability (ΔE) |
|---|----------|------------|-----------|--------------|-----------------|
| 1 | 0.00 | 0:00.00 | 120.87 | 0.1871 | +0.0000 |
| 2 | 0.56 | 0:00.56 | 120.87 | 0.1767 | +0.0104 |
| 3 | 32.33 | 0:32.33 | 120.87 | 0.1780 | -0.0050 |
| 4 | 48.21 | 0:48.21 | 120.87 | 0.2111 | -0.0665 |
| 5 | 79.98 | 1:19.98 | 120.87 | 0.2208 | -0.0390 |
| 6 | 111.75 | 1:51.75 | 120.87 | 0.1899 | +0.1240 |
| 7 | 127.63 | 2:07.63 | 120.87 | 0.2204 | -0.0611 |
| 8 | 143.52 | 2:23.52 | 120.87 | 0.2404 | -0.0402 |
| 9 | 151.46 | 2:31.46 | 120.87 | 0.2343 | +0.0061 |
| 10 | 167.34 | 2:47.34 | 120.87 | 0.2558 | -0.0431 |
| 11 | 175.29 | 2:55.29 | 120.87 | 0.1806 | +0.0756 |
| 12 | 183.23 | 3:03.23 | 120.87 | 0.1970 | -0.0165 |
| 13 | 191.17 | 3:11.17 | 120.87 | 0.2474 | -0.0506 |
| 14 | 191.66 | 3:11.66 | 120.87 | 0.1617 | +0.0857 |
| 15 | 207.54 | 3:27.54 | 120.87 | 0.1606 | +0.0021 |
| 16 | 223.43 | 3:43.43 | 120.87 | 0.2384 | -0.1560 |
| 17 | 239.31 | 3:59.31 | 120.87 | 0.2695 | -0.0624 |
| 18 | 247.26 | 4:07.26 | 120.87 | 0.2541 | +0.0155 |
| 19 | 279.03 | 4:39.03 | 120.87 | 0.2715 | -0.0696 |
| 20 | 286.97 | 4:46.97 | 120.87 | 0.0859 | +0.1867 |
| 21 | 294.91 | 4:54.91 | 120.87 | 0.0794 | +0.0066 |
| 22 | 302.85 | 5:02.85 | 120.87 | 0.1281 | -0.0490 |
| 23 | 310.79 | 5:10.79 | 120.87 | 0.1326 | -0.0046 |
| 24 | 318.73 | 5:18.73 | 120.87 | 0.1701 | -0.0377 |
| 25 | 326.67 | 5:26.67 | 120.87 | 0.1825 | -0.0125 |
| 26 | 334.62 | 5:34.62 | 120.87 | 0.2717 | -0.0897 |
| 27 | 398.15 | 6:38.15 | 120.87 | 0.2427 | +0.2318 |
| 28 | 445.81 | 7:25.81 | 120.87 | 0.0558 | +1.1226 |
| 29 | 461.69 | 7:41.69 | 120.87 | 0.1118 | -0.1124 |
| 30 | 477.58 | 7:57.58 | 120.87 | 0.1549 | -0.0864 |
```

### 🧠 Feature Input (Spotify Echo Nest `sections`)
```text
| # | start (s) | dur (s) | loudness (dB) | tempo | key | mode | time_sig | confidence |
|---|-----------|---------|---------------|-------|-----|------|----------|------------|
| 1 | 0.00 | 32.31 | -12.29 | 120.9 | 7 | 1 | 4 | 1.000 |
| 2 | 32.31 | 95.80 | -9.35 | 120.9 | 7 | 1 | 4 | 0.508 |
| 3 | 128.12 | 47.55 | -8.36 | 120.9 | 5 | 1 | 4 | 0.351 |
| 4 | 175.67 | 16.87 | -9.55 | 121.0 | 5 | 1 | 4 | 0.131 |
| 5 | 192.54 | 8.93 | -12.13 | 121.1 | 0 | 0 | 4 | 0.217 |
| 6 | 201.46 | 24.68 | -8.51 | 121.1 | 0 | 0 | 4 | 0.189 |
| 7 | 226.14 | 40.65 | -7.62 | 120.9 | 1 | 1 | 4 | 0.261 |
| 8 | 266.79 | 28.88 | -7.63 | 120.9 | 0 | 1 | 4 | 0.461 |
| 9 | 295.67 | 21.08 | -14.52 | 120.6 | 0 | 0 | 4 | 1.000 |
| 10 | 316.75 | 17.32 | -10.14 | 121.7 | 0 | 0 | 4 | 0.030 |
| 11 | 334.08 | 127.57 | -8.32 | 120.9 | 5 | 1 | 4 | 0.617 |
| 12 | 461.64 | 28.87 | -27.21 | 120.7 | 10 | 0 | 4 | 1.000 |
| 13 | 490.51 | 13.51 | -16.52 | 119.9 | 10 | 0 | 1 | 0.695 |
| 14 | 504.02 | 25.54 | -15.93 | 119.9 | 10 | 0 | 1 | 0.504 |
| 15 | 529.55 | 7.71 | -33.28 | 121.8 | 1 | 1 | 4 | 0.971 |
```
