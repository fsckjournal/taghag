"""Deterministic feature engineering from Apple Music Understanding raw JSON.

Computes derived scalars from the cuecifer JSON output, following the
architecture doc's Phase 4 recommendations. No LLMs, no ML - pure math
on Apple's deterministic MIR outputs.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any


def compute_derived_features(
    raw_json: dict[str, Any],
    filename: str = "",
    reference_bpm: float | None = None,
) -> dict[str, Any]:
    """Compute all derived features from a single cuecifer JSON payload.

    Returns a flat dict of scalar features suitable for database storage.
    """
    features: dict[str, Any] = {}

    # --- Rhythm ---
    rhythm = raw_json.get("rhythm") or {}
    bpm = rhythm.get("beatsPerMinute")
    features["apple_bpm"] = round(float(bpm), 1) if bpm is not None else None
    features["beat_count"] = len(rhythm.get("beats", []))
    features["bar_count"] = len(rhythm.get("bars", []))
    features["bpm_agreement_score"] = _bpm_agreement_score(features["apple_bpm"], reference_bpm)

    # --- Key Stability ---
    key_data = raw_json.get("key") or {}
    key_ranges = key_data.get("ranges", [])
    features["key_change_count"] = max(0, len(key_ranges) - 1)
    features["key_stable"] = len(key_ranges) <= 1

    if key_ranges:
        first_key = key_ranges[0].get("value", {})
        pitch_class = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        mode_class = ["Major", "Minor"]
        tonic = first_key.get("tonic", -1)
        mode = first_key.get("mode", -1)
        try:
            t, m = int(tonic), int(mode)
            if 0 <= t < 12 and 0 <= m < 2:
                features["apple_key"] = f"{pitch_class[t]} {mode_class[m]}"
            else:
                features["apple_key"] = None
        except (ValueError, TypeError):
            features["apple_key"] = None
    else:
        features["apple_key"] = None

    # --- Loudness ---
    loudness = raw_json.get("loudness") or {}
    integrated = loudness.get("integrated", {})
    peak = loudness.get("peak", {})

    integrated_val = _extract_value(integrated)
    peak_val = _extract_value(peak)

    features["loudness_integrated"] = round(integrated_val, 2) if integrated_val is not None else None
    features["loudness_peak"] = round(peak_val, 2) if peak_val is not None else None

    if integrated_val is not None and peak_val is not None:
        features["loudness_range_db"] = round(peak_val - integrated_val, 2)
    else:
        features["loudness_range_db"] = None

    # Short-term loudness statistics
    short_term = loudness.get("shortTerm", [])
    st_values = [_extract_value(v) for v in short_term if _extract_value(v) is not None]
    if st_values:
        features["loudness_mean"] = round(statistics.mean(st_values), 2)
        features["loudness_std"] = round(statistics.stdev(st_values), 2) if len(st_values) > 1 else 0.0
    else:
        features["loudness_mean"] = None
        features["loudness_std"] = None

    # --- Pace Statistics ---
    pace_data = raw_json.get("pace") or {}
    pace_ranges = pace_data.get("ranges", [])
    pace_values = [_extract_ranged_value(r) for r in pace_ranges]
    pace_values = [v for v in pace_values if v is not None]

    if pace_values:
        features["pace_mean"] = round(statistics.mean(pace_values), 2)
        features["pace_median"] = round(statistics.median(pace_values), 2)
        features["pace_volatility"] = round(statistics.stdev(pace_values), 2) if len(pace_values) > 1 else 0.0
        features["pace_max"] = round(max(pace_values), 2)
        features["pace_min"] = round(min(pace_values), 2)
    else:
        features["pace_mean"] = None
        features["pace_median"] = None
        features["pace_volatility"] = None
        features["pace_max"] = None
        features["pace_min"] = None

    # --- Structure ---
    structure = raw_json.get("structure") or {}
    sections = structure.get("sections", [])
    segments = structure.get("segments", [])
    phrases = structure.get("phrases", [])

    features["section_count"] = len(sections)
    features["segment_count"] = len(segments)
    features["phrase_count"] = len(phrases)

    # Intro/outro lengths (first and last section)
    if sections:
        first_section = sections[0]
        last_section = sections[-1]
        features["intro_length_ms"] = _range_duration_ms(first_section)
        features["outro_length_ms"] = _range_duration_ms(last_section)
    else:
        features["intro_length_ms"] = None
        features["outro_length_ms"] = None

    # --- Instrument Activity ---
    instrument_activity = raw_json.get("instrumentActivity") or {}
    activity = instrument_activity.get("activity", {})

    # Vocal presence
    vocal_values = _extract_activity_values(activity, "vocal")
    features["has_vocal_activity"] = _has_significant_activity(vocal_values)
    features["vocal_intensity_mean"] = round(statistics.mean(vocal_values), 3) if vocal_values else 0.0

    # Drum presence
    drum_values = _extract_activity_values(activity, "drum")
    features["has_drum_activity"] = _has_significant_activity(drum_values)
    features["drum_intensity_mean"] = round(statistics.mean(drum_values), 3) if drum_values else 0.0

    # Bass presence
    bass_values = _extract_activity_values(activity, "bass")
    features["bass_intensity_mean"] = round(statistics.mean(bass_values), 3) if bass_values else 0.0

    return features


def extract_structure_boundaries(raw_json: dict[str, Any]) -> list[dict]:
    """Absolute section/phrase boundaries in Apple CMTime milliseconds, role-tagged.

    Unlike ``compute_derived_features`` (which keeps only counts and intro/outro
    durations), this preserves the *absolute* start/end position of every section
    and phrase. Positions are in Apple's CMTime base = the artifact identified by
    ``apple_derived_features.source_artifact_sha256``.

    Apple's structure payload carries no per-section "kind"/type field (the
    analyzer serializes ``MusicUnderstandingSession`` results, and sections are
    bare ``{range:{start,duration}}`` entries). So role is inferred positionally:
    first section -> 'intro', last section -> 'outro', other sections -> 'phrase',
    and every entry under ``phrases`` -> 'phrase'. If a future payload ever does
    carry a section "kind"/"type" string, it is honored verbatim.
    """
    if not isinstance(raw_json, dict):
        return []
    structure = raw_json.get("structure") or {}
    if not isinstance(structure, dict):
        return []

    boundaries: list[dict] = []

    sections = structure.get("sections") or []
    if isinstance(sections, list):
        last_idx = len(sections) - 1
        for idx, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            bounds = _boundary_ms(section)
            if bounds is None:
                continue
            start_ms, end_ms = bounds
            kind = _section_kind(section)
            if kind is not None:
                role = kind
            elif idx == 0:
                role = "intro"
            elif idx == last_idx:
                role = "outro"
            else:
                role = "phrase"
            boundaries.append(
                {"role": role, "level": "section", "start_ms": start_ms, "end_ms": end_ms}
            )

    phrases = structure.get("phrases") or []
    if isinstance(phrases, list):
        for phrase in phrases:
            if not isinstance(phrase, dict):
                continue
            bounds = _boundary_ms(phrase)
            if bounds is None:
                continue
            start_ms, end_ms = bounds
            boundaries.append(
                {"role": "phrase", "level": "phrase", "start_ms": start_ms, "end_ms": end_ms}
            )

    return boundaries


def _section_kind(section: dict) -> str | None:
    """Return a declared section kind/type string if the payload carries one."""
    for field in ("kind", "type", "label"):
        value = section.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def _boundary_ms(entry: dict) -> tuple[int, int] | None:
    """Absolute (start_ms, end_ms) from a CMTimeRange-bearing entry, or None."""
    range_data = entry.get("range", entry)
    if not isinstance(range_data, dict):
        return None
    start_seconds = _cmtime_seconds(range_data.get("start"))
    if start_seconds is None:
        return None
    start_ms = int(start_seconds * 1000)
    duration_ms = _range_duration_ms(entry)
    if duration_ms is None:
        return None
    return start_ms, start_ms + duration_ms


# --- Helpers ---

def _extract_value(timed_value: Any) -> float | None:
    """Extract float value from Apple TimedValue/RangedValue-like dicts."""
    if isinstance(timed_value, dict):
        v = timed_value.get("value")
        if v is not None:
            try:
                f = float(v)
                return f if math.isfinite(f) else None
            except (ValueError, TypeError):
                return None
    return None


def _extract_ranged_value(ranged: Any) -> float | None:
    """Extract float value from a RangedValue dict."""
    return _extract_value(ranged)


def _range_duration_ms(section: dict) -> int | None:
    """Extract duration in ms from a section's CMTimeRange."""
    range_data = section.get("range", section)
    if not isinstance(range_data, dict):
        return None
    dur = range_data.get("duration", {})
    seconds = _cmtime_seconds(dur)
    if seconds is not None and seconds > 0:
        return int(seconds * 1000)
    return None


def _extract_activity_values(activity: dict, instrument: str) -> list[float]:
    """Extract the intensity float array for a given instrument."""
    entries = activity.get(instrument, [])
    if not entries and instrument == "vocal":
        entries = activity.get("vocals", [])
    elif not entries and instrument == "drum":
        entries = activity.get("drums", [])
    values = []
    for entry in entries:
        v = _extract_value(entry)
        if v is not None:
            values.append(v)
    return values


def _has_significant_activity(values: list[float], threshold: float = 0.05, min_ratio: float = 0.1) -> bool:
    """True if the instrument is active above threshold for at least min_ratio of samples."""
    if not values:
        return False
    active = sum(1 for v in values if v > threshold)
    return (active / len(values)) > min_ratio


def _cmtime_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    if not isinstance(value, dict):
        return None
    raw_value = value.get("value")
    raw_timescale = value.get("timescale", 1)
    try:
        numerator = float(raw_value)
        timescale = float(raw_timescale)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numerator) or not math.isfinite(timescale) or timescale <= 0:
        return None
    return numerator / timescale


def _bpm_agreement_score(apple_bpm: float | None, reference_bpm: float | None) -> float | None:
    if apple_bpm is None or reference_bpm is None:
        return None
    try:
        apple = float(apple_bpm)
        reference = float(reference_bpm)
    except (TypeError, ValueError):
        return None
    if apple <= 0 or reference <= 0:
        return None
    relative_error = abs(apple - reference) / max(apple, reference)
    return round(max(0.0, 1.0 - (relative_error / 0.10)), 3)


def compute_features_from_file(json_path: Path, filename: str = "") -> dict[str, Any] | None:
    """Load a cuecifer JSON file and compute derived features."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return compute_derived_features(raw, filename=filename)
    except Exception as e:
        print(f"Error computing features from {json_path}: {e}")
        return None
