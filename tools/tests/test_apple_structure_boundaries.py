from __future__ import annotations

from taghag_import.apple_derived_features import extract_structure_boundaries


def _time(value: int, timescale: int = 1_000) -> dict[str, int]:
    """Apple CMTime dict; default timescale 1000 => value is milliseconds."""
    return {"value": value, "timescale": timescale}


def _range(start_ms: int, duration_ms: int) -> dict[str, dict[str, dict[str, int]]]:
    return {"range": {"start": _time(start_ms), "duration": _time(duration_ms)}}


def test_extract_structure_boundaries_absolute_ms_and_positional_roles() -> None:
    raw = {
        "structure": {
            "sections": [
                _range(0, 16_000),
                _range(16_000, 200_000),
                _range(216_000, 32_000),
            ],
            "phrases": [
                _range(0, 32_000),
                _range(32_000, 32_000),
            ],
        }
    }

    boundaries = extract_structure_boundaries(raw)

    section_boundaries = [b for b in boundaries if b["level"] == "section"]
    phrase_boundaries = [b for b in boundaries if b["level"] == "phrase"]

    # Absolute CMTime ms: start from range.start, end = start + duration.
    assert section_boundaries == [
        {"role": "intro", "level": "section", "start_ms": 0, "end_ms": 16_000},
        {"role": "phrase", "level": "section", "start_ms": 16_000, "end_ms": 216_000},
        {"role": "outro", "level": "section", "start_ms": 216_000, "end_ms": 248_000},
    ]
    assert phrase_boundaries == [
        {"role": "phrase", "level": "phrase", "start_ms": 0, "end_ms": 32_000},
        {"role": "phrase", "level": "phrase", "start_ms": 32_000, "end_ms": 64_000},
    ]


def test_extract_structure_boundaries_honors_declared_kind() -> None:
    raw = {
        "structure": {
            "sections": [
                {"kind": "breakdown", "range": {"start": _time(48_000), "duration": _time(8_000)}},
            ]
        }
    }
    assert extract_structure_boundaries(raw) == [
        {"role": "breakdown", "level": "section", "start_ms": 48_000, "end_ms": 56_000},
    ]


def test_extract_structure_boundaries_is_defensive() -> None:
    assert extract_structure_boundaries({}) == []
    assert extract_structure_boundaries({"structure": None}) == []
    assert extract_structure_boundaries(None) == []  # type: ignore[arg-type]
    # Malformed entries are skipped, valid ones kept.
    raw = {
        "structure": {
            "sections": [
                "not-a-dict",
                {"range": {"start": _time(0)}},  # missing duration -> skipped
                _range(10_000, 5_000),
            ]
        }
    }
    out = extract_structure_boundaries(raw)
    assert out == [
        {"role": "outro", "level": "section", "start_ms": 10_000, "end_ms": 15_000},
    ]
