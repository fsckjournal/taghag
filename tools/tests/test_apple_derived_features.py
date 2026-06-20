from __future__ import annotations

from taghag_import.apple_derived_features import compute_derived_features

# Trimmed to the real shape Apple's Music Understanding JSON actually uses --
# tonic/mode are strings ("e"/"minor"), not the integer indices the old code
# assumed. See apple_derived_features.py:_format_key.
REAL_SHAPE_RAW_JSON = {
    "rhythm": {
        "beatsPerMinute": 135.0,
        "beats": [{"time": {"value": i, "timescale": 2}} for i in range(4)],
        "bars": [{"time": {"value": 0, "timescale": 1}}],
    },
    "key": {
        "ranges": [
            {"value": {"tonic": "e", "mode": "minor"}},
        ]
    },
    "loudness": {
        "integrated": {"value": -5.67},
        "peak": {"value": -0.0},
        "shortTerm": [{"value": -6.0}, {"value": -5.5}, {"value": -5.8}],
    },
    "pace": {
        "ranges": [{"value": 21.0}, {"value": 22.0}, {"value": 20.5}],
    },
    "structure": {
        "sections": [
            {"range": {"start": {"value": 0, "timescale": 1}, "duration": {"value": 14, "timescale": 1}}},
            {"range": {"start": {"value": 14, "timescale": 1}, "duration": {"value": 60, "timescale": 1}}},
        ],
        "segments": [],
        "phrases": [],
    },
    "instrumentActivity": {
        "activity": {
            "vocal": [{"value": 0.01}],
            "drum": [{"value": 0.8}, {"value": 0.9}],
            "bass": [{"value": 0.3}],
        }
    },
}


def test_apple_key_parses_real_string_encoded_tonic_and_mode() -> None:
    features = compute_derived_features(REAL_SHAPE_RAW_JSON)
    assert features["apple_key"] == "E Minor"
    assert features["key_stable"] is True
    assert features["key_change_count"] == 0


def test_apple_key_is_none_for_unrecognized_tonic_encoding() -> None:
    raw = {"key": {"ranges": [{"value": {"tonic": "h", "mode": "minor"}}]}}
    features = compute_derived_features(raw)
    assert features["apple_key"] is None


def test_apple_key_is_none_for_missing_key_data() -> None:
    features = compute_derived_features({})
    assert features["apple_key"] is None
    assert features["key_stable"] is True
    assert features["key_change_count"] == 0


def test_bpm_agreement_score_uses_reference_bpm() -> None:
    features = compute_derived_features(REAL_SHAPE_RAW_JSON, reference_bpm=134.0)
    assert features["apple_bpm"] == 135.0
    assert features["bpm_agreement_score"] is not None
    assert features["bpm_agreement_score"] > 0.9


def test_bpm_agreement_score_is_none_without_reference_bpm() -> None:
    features = compute_derived_features(REAL_SHAPE_RAW_JSON)
    assert features["bpm_agreement_score"] is None


# Real pace curve (start_s, duration_s, value) pulled from an actual cuecifer
# run on a real track -- re-expressed with timescale=1 for readability. Apple's
# pace is piecewise-constant over these intervals, not a continuous sample.
_REAL_PACE_CURVE = [
    (0.11, 14.22, 16.87),
    (14.33, 71.11, 16.88),
    (85.44, 14.22, 33.75),
    (99.66, 28.44, 16.88),
    (128.11, 14.22, 16.87),
    (142.33, 42.67, 33.75),
    (185.00, 14.22, 8.44),
    (199.22, 28.44, 16.87),
    (227.66, 42.67, 33.75),
    (270.33, 14.22, 16.87),
    (284.55, 42.67, 33.75),
    (327.22, 14.22, 16.87),
]


def _pace_range(start_s: float, duration_s: float, value: float) -> dict:
    return {
        "value": value,
        "range": {
            "start": {"value": start_s, "timescale": 1},
            "duration": {"value": duration_s, "timescale": 1},
        },
    }


def _raw_json_with_pace(pace_ranges: list[dict]) -> dict:
    return {"pace": {"ranges": pace_ranges}}


def test_energy_agreement_score_full_agreement_on_real_pace_shape() -> None:
    raw = _raw_json_with_pace([_pace_range(*entry) for entry in _REAL_PACE_CURVE])
    # t=5 (pace 16.87) -> t=90 (pace 33.75): energy and pace both rise.
    # t=90 (pace 33.75) -> t=110 (pace 16.88): energy and pace both fall.
    shifts = [
        {"time_s": 5.0, "energy": 3},
        {"time_s": 90.0, "energy": 6},
        {"time_s": 110.0, "energy": 3},
    ]
    features = compute_derived_features(raw, mik_energy_shifts=shifts)
    assert features["energy_agreement_score"] == 1.0


def test_energy_agreement_score_full_disagreement_on_real_pace_shape() -> None:
    raw = _raw_json_with_pace([_pace_range(*entry) for entry in _REAL_PACE_CURVE])
    # t=5 (pace 16.87) -> t=90 (pace 33.75): energy falls while pace rises.
    # t=90 (pace 33.75) -> t=110 (pace 16.88): energy rises while pace falls.
    shifts = [
        {"time_s": 5.0, "energy": 3},
        {"time_s": 90.0, "energy": 2},
        {"time_s": 110.0, "energy": 6},
    ]
    features = compute_derived_features(raw, mik_energy_shifts=shifts)
    assert features["energy_agreement_score"] == 0.0


def test_energy_agreement_score_partial_agreement_on_real_pace_shape() -> None:
    raw = _raw_json_with_pace([_pace_range(*entry) for entry in _REAL_PACE_CURVE])
    # t=5 (16.87) -> t=90 (33.75): pace rises, energy rises (3 -> 6): agree.
    # t=90 (33.75) -> t=110 (16.88): pace falls, energy falls (6 -> 3): agree.
    # t=110 (16.88) -> t=150 (33.75): pace rises, energy falls (3 -> 1): disagree.
    shifts = [
        {"time_s": 5.0, "energy": 3},
        {"time_s": 90.0, "energy": 6},
        {"time_s": 110.0, "energy": 3},
        {"time_s": 150.0, "energy": 1},
    ]
    features = compute_derived_features(raw, mik_energy_shifts=shifts)
    assert features["energy_agreement_score"] == 0.667


def test_energy_agreement_score_skips_tied_energy_transitions() -> None:
    raw = _raw_json_with_pace([_pace_range(*entry) for entry in _REAL_PACE_CURVE])
    # t=5 -> t=90: energy is flat (3 -> 3), so this transition isn't compared at all.
    # t=90 -> t=110: pace falls (33.75 -> 16.88) while energy rises (3 -> 6): disagree.
    shifts = [
        {"time_s": 5.0, "energy": 3},
        {"time_s": 90.0, "energy": 3},
        {"time_s": 110.0, "energy": 6},
    ]
    features = compute_derived_features(raw, mik_energy_shifts=shifts)
    assert features["energy_agreement_score"] == 0.0


def test_energy_agreement_score_is_none_when_only_transition_has_tied_pace() -> None:
    raw = _raw_json_with_pace([_pace_range(*entry) for entry in _REAL_PACE_CURVE])
    # t=5 and t=130 both fall in pace-16.87 intervals, so pace_delta is 0 and the
    # only transition available is skipped, leaving nothing to compare.
    shifts = [{"time_s": 5.0, "energy": 3}, {"time_s": 130.0, "energy": 6}]
    features = compute_derived_features(raw, mik_energy_shifts=shifts)
    assert features["energy_agreement_score"] is None


def test_energy_agreement_score_is_none_with_fewer_than_two_shifts() -> None:
    raw = _raw_json_with_pace([_pace_range(*entry) for entry in _REAL_PACE_CURVE])
    features = compute_derived_features(raw, mik_energy_shifts=[{"time_s": 5.0, "energy": 3}])
    assert features["energy_agreement_score"] is None


def test_energy_agreement_score_is_none_without_pace_data() -> None:
    shifts = [{"time_s": 5.0, "energy": 3}, {"time_s": 90.0, "energy": 6}]
    features = compute_derived_features({}, mik_energy_shifts=shifts)
    assert features["energy_agreement_score"] is None


def test_energy_agreement_score_is_none_when_no_mik_shifts_given() -> None:
    raw = _raw_json_with_pace([_pace_range(*entry) for entry in _REAL_PACE_CURVE])
    features = compute_derived_features(raw)
    assert features["energy_agreement_score"] is None
