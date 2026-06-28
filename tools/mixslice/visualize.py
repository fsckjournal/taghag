#!/usr/bin/env python3
"""Visualize a FLAC waveform with its FLAC-native pulse grid and DJ mix cues.

A diagnostic view for picking mix-in / mix-out points and spotting clipping.
No ML, no scoring, no speculative diagnostics: it draws the audio, the
analyzer's detected pulse (downbeats + 32-beat sections), and the
auto-generated cue points that MIK / Rekordbox already wrote (Energy cues,
grid anchor). Phrasing and brickwalling are then obvious by eye.

  - waveform   peak-preserving min/max envelope (true peaks, so limiting shows)
  - clipping   red carets over any column touching +/-`--clip` full scale
  - bars       faint grey verticals (analyzer downbeats)
  - sections   labeled verticals (analyzer 32-beat phrasing) -- count these to cue
  - cues       orange verticals from MIK/Rekordbox XML POSITION_MARK
  - --mark     dashed green candidate mix point(s)

Usage:
    visualize.py AUDIO.flac ANALYZER.json [--cues XML ...]
                 [--start S] [--end S] [--mark S ...] [--out PNG]
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402


def _ct(ct: dict) -> float:
    """CMTime dict -> seconds."""
    return ct["value"] / ct["timescale"]


def load_pulse(json_path: str) -> tuple[float, np.ndarray, np.ndarray]:
    """Return (bpm, bar_starts_s, section_starts_s) from analyzer JSON."""
    d = json.load(open(json_path))
    rhythm = d["rhythm"]
    bars = np.array([_ct(b) for b in rhythm.get("bars", [])], dtype=np.float64)
    sections = np.array(
        [_ct(s["start"]) for s in d["structure"]["sections"]], dtype=np.float64
    )
    return float(rhythm["beatsPerMinute"]), bars, sections


def _stem(p: str) -> str:
    return os.path.splitext(os.path.basename(p))[0].lower()


def load_cues(xml_paths: list[str], audio_path: str) -> list[tuple[float, str]]:
    """[(time_s, label)] from Rekordbox/MIK XML POSITION_MARK, matched by filename."""
    want = _stem(audio_path)
    cues: list[tuple[float, str]] = []
    for xp in xml_paths:
        try:
            root = ET.parse(xp).getroot()
        except (OSError, ET.ParseError):
            continue
        for tr in root.findall(".//TRACK"):
            path = urllib.parse.unquote(tr.get("Location") or "").replace(
                "file://localhost", ""
            )
            if want != _stem(path) and want not in _stem(path):
                continue
            for m in tr.findall("POSITION_MARK"):
                if m.get("Num") not in (None, "-1"):  # memory cues only
                    continue
                try:
                    cues.append((float(m.get("Start")), m.get("Name") or "cue"))
                except (TypeError, ValueError):
                    continue
    seen: set[tuple[float, str]] = set()
    out: list[tuple[float, str]] = []
    for t, n in sorted(cues):
        key = (round(t, 2), n)
        if key not in seen:
            seen.add(key)
            out.append((t, n))
    return out


def reduce_env(
    mono: np.ndarray, sr: int, cols: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    bins = np.array_split(mono, max(1, min(cols, mono.size)))
    starts = np.cumsum([0, *(len(b) for b in bins[:-1])], dtype=np.float64)
    return (
        starts / sr,
        np.array([b.min() for b in bins]),
        np.array([b.max() for b in bins]),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("audio")
    ap.add_argument("analyzer_json")
    ap.add_argument("--cues", nargs="*", default=[], help="Rekordbox/MIK XML cue files")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--mark", type=float, nargs="*", default=[],
                    help="candidate mix point(s), seconds (dashed green)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--cols", type=int, default=3000)
    ap.add_argument("--clip", type=float, default=0.99,
                    help="|amp| at/above this is flagged as clipping")
    args = ap.parse_args(argv)

    audio, sr = sf.read(args.audio, dtype="float64", always_2d=True)
    mono = audio.mean(axis=1)
    dur = len(mono) / sr
    s0 = max(0.0, args.start)
    s1 = min(dur, args.end if args.end is not None else dur)
    seg = mono[int(s0 * sr): int(s1 * sr)]
    t, lo, hi = reduce_env(seg, sr, args.cols)
    t = t + s0

    bpm, bars, sections = load_pulse(args.analyzer_json)
    cues = load_cues(args.cues, args.audio)

    fig, ax = plt.subplots(figsize=(18, 6), facecolor="#111318")
    ax.set_facecolor("#181b22")

    ax.add_collection(
        LineCollection(
            np.stack((np.column_stack((t, lo)), np.column_stack((t, hi))), axis=1),
            colors="#6f76ff",
            linewidths=1.0,
        )
    )

    clipped = np.maximum(np.abs(lo), np.abs(hi)) >= args.clip
    if clipped.any():
        ax.scatter(t[clipped], np.full(int(clipped.sum()), 1.02),
                   s=10, color="#ff3b3b", marker="v", zorder=6)

    ax.axhline(0.0, color="#aeb2ff", lw=0.4, alpha=0.4)
    for y in (1.0, -1.0):
        ax.axhline(y, color="#ff3b3b", lw=0.5, alpha=0.25)

    for b in bars[(bars >= s0) & (bars <= s1)]:
        ax.axvline(b, color="#363b48", lw=0.5, zorder=1)
    for i, sx in enumerate(sections):
        if s0 <= sx <= s1:
            ax.axvline(sx, color="#8089a6", lw=1.0, alpha=0.85, zorder=2)
            ax.text(sx, -1.18, str(i), color="#9aa6c2", fontsize=7, ha="center")

    for tt, name in cues:
        if s0 <= tt <= s1:
            ax.axvline(tt, color="#ffb02e", lw=1.2, zorder=4)
            ax.text(tt, 1.06, name, color="#ffb02e", fontsize=7,
                    rotation=90, va="bottom", ha="center")

    for mk in args.mark:
        if s0 <= mk <= s1:
            ax.axvline(mk, color="#2ee6a6", lw=1.8, ls="--", zorder=5)

    ax.set_xlim(s0, s1)
    ax.set_ylim(-1.3, 1.3)
    ax.set_xlabel("seconds")
    ax.set_ylabel("amplitude")
    ax.set_title(
        f"{Path(args.audio).name}   bpm={bpm:g}   dur={dur:0.1f}s   "
        f"section #(blue) / bars(grey) / cues(orange) / mark(green)",
        color="#f2f3f5",
    )
    ax.tick_params(colors="#c9ccd3")
    for sp in ax.spines.values():
        sp.set_color("#3b3f48")

    out = args.out or str(
        Path.home() / "Desktop" / f"{Path(args.audio).stem}.viz.png"
    )
    fig.tight_layout()
    fig.savefig(out, dpi=130, facecolor=fig.get_facecolor())
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
