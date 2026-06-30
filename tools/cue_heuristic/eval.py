#!/usr/bin/env python3
"""Eval harness for the Cuecifer mix-point heuristic.

Pair-programming scaffold: this loads the verified (feature -> label) pairs from
``ground_truth.json``, exposes the Echo Nest payload (sections + the high-res
``segments`` array) to a predictor, and scores predicted cue times against the
Mixonset ground truth. The math itself — ``predict_cues`` — is deliberately left
as a stub for whoever takes the baton on the heuristic.

Run:
    python3 eval.py                 # score the current predict_cues against both tracks
    python3 eval.py --baseline      # score the trivial section-boundary floor instead

The scorer is greedy nearest-match within a beat-scaled tolerance window and
reports precision / recall / F1 and mean absolute onset error (MAE) on matches.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent  # tools/cue_heuristic -> tools -> repo root
PAYLOAD_DIR = Path(os.environ.get("AUTOMIX_PAYLOADS", REPO_ROOT / "automix_payloads"))
GROUND_TRUTH = HERE / "ground_truth.json"


def load_payload(spotify_id: str) -> dict:
    """Full Echo Nest payload: keys meta/track/bars/beats/sections/segments/tatums.

    ``segments`` is the high-resolution array (every ~0.2 s) carrying
    ``loudness_start``, ``loudness_max``, ``loudness_max_time``, ``pitches`` (12),
    and ``timbre`` (12). That is the signal the heuristic needs — section
    boundaries alone do not coincide with the Mixonset cues.
    """
    return json.loads((PAYLOAD_DIR / f"{spotify_id}.json").read_text())


# --------------------------------------------------------------------------- #
# THE HEURISTIC — take the baton here.
# --------------------------------------------------------------------------- #
def predict_cues(payload: dict) -> list[float]:
    """Return candidate mix-point timestamps (seconds) for one track.

    Input is a full Echo Nest payload (see load_payload). The target is the
    Mixonset ``cues`` time column. Thesis from the dossier: cues land on large
    positive energy gradients (ΔE) — drops/breakdowns — computed from the
    segment-level loudness envelope, NOT from the coarse ``sections`` array.

    Currently unimplemented (returns []), so the score is an honest 0/floor until
    the real math lands. Replace this body.
    """
    return []


def baseline_section_boundaries(payload: dict) -> list[float]:
    """Reference floor: just the Echo Nest section start times.

    This is the naive approach the dossier calls out as insufficient — it exists
    only to give the heuristic a number to beat.
    """
    return [round(s["start"], 3) for s in payload.get("sections", [])]


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def score(predicted: list[float], truth: list[float], tol_s: float) -> dict:
    """Greedy nearest-match within +/- tol_s. Each truth cue matches >=1 prediction."""
    preds = sorted(predicted)
    used = [False] * len(preds)
    errors = []
    hits = 0
    for t in sorted(truth):
        best_i, best_d = None, None
        for i, p in enumerate(preds):
            if used[i]:
                continue
            d = abs(p - t)
            if d <= tol_s and (best_d is None or d < best_d):
                best_i, best_d = i, d
        if best_i is not None:
            used[best_i] = True
            errors.append(best_d)
            hits += 1
    n_pred, n_true = len(preds), len(truth)
    precision = hits / n_pred if n_pred else 0.0
    recall = hits / n_true if n_true else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    mae = sum(errors) / len(errors) if errors else None
    return {
        "n_pred": n_pred, "n_true": n_true, "matched": hits,
        "precision": round(precision, 3), "recall": round(recall, 3),
        "f1": round(f1, 3),
        "mae_s": round(mae, 3) if mae is not None else None,
    }


def tolerance_for(payload: dict, beats: float = 2.0) -> float:
    """Match window scaled to the track's tempo: ``beats`` beats wide."""
    tempo = payload.get("track", {}).get("tempo") or 120.0
    return beats * 60.0 / tempo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", action="store_true",
                    help="score baseline_section_boundaries instead of predict_cues")
    ap.add_argument("--beats", type=float, default=2.0,
                    help="match tolerance in beats (default 2.0)")
    args = ap.parse_args()

    gt = json.loads(GROUND_TRUTH.read_text())
    predictor = baseline_section_boundaries if args.baseline else predict_cues
    label = "baseline(section_boundaries)" if args.baseline else "predict_cues"
    print(f"Scoring `{label}` @ {args.beats}-beat tolerance\n")

    for pair in gt["verified_pairs"]:
        payload = load_payload(pair["spotify_id"])
        truth = [c["t"] for c in pair["cues"]]
        pred = predictor(payload)
        tol = tolerance_for(payload, args.beats)
        s = score(pred, truth, tol)
        print(f"{pair['title']}")
        print(f"  tol=±{tol:.2f}s  segments={len(payload.get('segments', []))}  "
              f"sections={len(payload.get('sections', []))}")
        print(f"  {s}\n")


if __name__ == "__main__":
    main()
