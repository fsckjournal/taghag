# Cue-heuristic kit — `predict_cues()` training & eval

Supervised set + scorer for the Cuecifer mix-point heuristic. The goal: a deterministic
`predict_cues(payload)` that consumes an Echo Nest payload and reproduces the Mixonset
ground-truth cue timestamps.

## Files
| File | What |
|---|---|
| `eval.py` | Loads payloads, runs `predict_cues`, scores vs ground truth (precision/recall/F1 + onset MAE). **The `predict_cues` stub is the spot to write the heuristic.** `--baseline` scores raw section boundaries as the floor. |
| `ground_truth.json` | The verified `(feature → label)` pairs. Currently **2** (Wildfires 17 cues, Smoothin' Groovin' 30 cues) — the only cue-bearing tracks that also have a local payload. |
| `scrape_targets.json` | The **4 missing** cue-bearing tracks to scrape, with Spotify IDs + duration hints. Scraping these grows the eval set 2 → up to 6. |

## Run
```bash
python3 eval.py                # score predict_cues (0 until implemented)
python3 eval.py --baseline     # the floor to beat: F1 0.07 (Wildfires) / 0.36 (Smoothin')
```
Payloads are read from `../../automix_payloads/<spotify_id>.json` (override with `$AUTOMIX_PAYLOADS`).

## The signal
Mixonset cues fall **inside** Echo Nest `sections` (Wildfires cues at 1.89/9.27/16.66 s vs the
first section spanning 0–15.5 s) — so `sections` alone can't reproduce them. The target lives in
the high-res `segments` array: `loudness_start`, `loudness_max`, `loudness_max_time` (and
`pitches[12]`/`timbre[12]` for spectral-flux at drops). `Mixability` in the ground truth is the
energy gradient ΔE at each cue, spiking at breakdowns (Smoothin' Groovin' +1.12 at 7:25).

## Division of labor
- **Gemini:** write `predict_cues`; scrape the 4 in `scrape_targets.json`; if possible, dump the
  full per-segment `Local Energy`/`Local BPM` time-series from the decrypted Mixonset `.dat`
  cache (richer target than cue rows alone).
- **Hag:** fold new payloads into `ground_truth.json`, keep the scorer honest, wire the winning
  `predict_cues` into the taghag pipeline + the payload↔library join once v4's `spotify_id` lands.

Full context: `hag:docs/reports/opus_training_dossier.md`.
