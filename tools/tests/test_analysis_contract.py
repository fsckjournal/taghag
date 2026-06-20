from __future__ import annotations

from taghag_import.apple_derived_features import compute_derived_features


def _time(value: int, timescale: int = 1_000) -> dict[str, int]:
    return {"value": value, "timescale": timescale}


def _range(start_ms: int, duration_ms: int) -> dict[str, dict[str, dict[str, int]]]:
    return {"range": {"start": _time(start_ms), "duration": _time(duration_ms)}}


def test_compute_derived_features_preserves_apple_phase_four_scalars() -> None:
    raw = {
        "rhythm": {
            "beatsPerMinute": 124.0,
            "beats": [_time(0), _time(500)],
            "bars": [_time(0)],
        },
        "key": {
            "ranges": [
                {"value": {"tonic": "c", "mode": "major"}},
                {"value": {"tonic": "g", "mode": "major"}},
            ]
        },
        "loudness": {
            "integrated": {"value": -10.0},
            "peak": {"value": -1.0},
            "shortTerm": [{"value": -12.0}, {"value": -8.0}],
        },
        "pace": {"ranges": [{"value": 0.4}, {"value": 0.8}, {"value": 1.0}]},
        "structure": {
            "sections": [_range(0, 16_000), _range(240_000, 32_000)],
            "segments": [_range(0, 8_000)],
            "phrases": [_range(0, 32_000), _range(32_000, 32_000)],
        },
        "instrumentActivity": {
            "activity": {
                "vocal": [{"value": 0.0}, {"value": 0.2}],
                "drum": [{"value": 0.9}, {"value": 0.8}],
                "bass": [{"value": 0.3}, {"value": 0.5}],
            }
        },
    }

    features = compute_derived_features(raw, reference_bpm=125.0)

    assert features["apple_bpm"] == 124.0
    assert features["beat_count"] == 2
    assert features["bar_count"] == 1
    assert features["apple_key"] == "C Major"
    assert features["key_stable"] is False
    assert features["key_change_count"] == 1
    assert features["pace_mean"] == 0.73
    assert features["pace_volatility"] > 0
    assert features["intro_length_ms"] == 16_000
    assert features["outro_length_ms"] == 32_000
    assert features["section_count"] == 2
    assert features["segment_count"] == 1
    assert features["phrase_count"] == 2
    assert features["has_vocal_activity"] is True
    assert features["has_drum_activity"] is True
    assert features["loudness_range_db"] == 9.0
    assert features["bpm_agreement_score"] > 0.9
