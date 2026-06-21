from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

APPLE_TRANSITION_WEIGHTS = {
    "pace_delta": 2.0,
    "pace_volatility": 0.8,
    "vocal_overlap_risk": 2.5,
    "loudness_handoff": 1.5,
    "bpm_disagreement": 1.0,
    "key_instability": 0.75,
    "phrase_boundary_penalty": 1.0,
}


@dataclass(frozen=True)
class AppleTransitionScore:
    total_cost: float
    terms: dict[str, float]


def score_apple_transition(
    from_features: Mapping[str, Any] | None,
    to_features: Mapping[str, Any] | None,
    *,
    from_segment: Mapping[str, Any] | None = None,
    to_segment: Mapping[str, Any] | None = None,
    weights: Mapping[str, float] | None = None,
) -> AppleTransitionScore:
    """Score Apple-derived risk terms for handing off from one track to the next."""

    if not from_features or not to_features:
        return AppleTransitionScore(total_cost=0.0, terms={})

    terms = {
        "pace_delta": _clip(abs(_number(from_features.get("pace_mean")) - _number(to_features.get("pace_mean")))),
        "pace_volatility": _clip(
            (_number(from_features.get("pace_volatility")) + _number(to_features.get("pace_volatility"))) / 2.0
        ),
        "vocal_overlap_risk": _clip(
            _number(from_features.get("vocal_intensity_mean"))
            * _number(to_features.get("vocal_intensity_mean"))
        ),
        "loudness_handoff": _loudness_handoff(from_features, to_features),
        "bpm_disagreement": _bpm_disagreement(from_features, to_features),
        "key_instability": _key_instability(from_features, to_features),
        "phrase_boundary_penalty": _phrase_boundary_penalty(from_segment, to_segment),
    }
    active_weights = dict(APPLE_TRANSITION_WEIGHTS)
    if weights:
        active_weights.update(weights)
    total = sum(terms[name] * active_weights.get(name, 1.0) for name in terms)
    return AppleTransitionScore(
        total_cost=round(total, 6),
        terms={name: round(value, 6) for name, value in terms.items()},
    )


def _loudness_handoff(
    from_features: Mapping[str, Any],
    to_features: Mapping[str, Any],
) -> float:
    from_loudness = from_features.get("loudness_integrated")
    to_loudness = to_features.get("loudness_integrated")
    if from_loudness is None or to_loudness is None:
        return 0.0
    return _clip(abs(_number(from_loudness) - _number(to_loudness)) / 18.0)


def _bpm_disagreement(
    from_features: Mapping[str, Any],
    to_features: Mapping[str, Any],
) -> float:
    scores = [
        _number(value)
        for value in (
            from_features.get("bpm_agreement_score"),
            to_features.get("bpm_agreement_score"),
        )
        if value is not None
    ]
    if not scores:
        return 0.0
    return _clip(1.0 - (sum(scores) / len(scores)))


def _key_instability(
    from_features: Mapping[str, Any],
    to_features: Mapping[str, Any],
) -> float:
    if from_features.get("key_stable") is False or to_features.get("key_stable") is False:
        return 1.0
    return 0.0


def _phrase_boundary_penalty(
    from_segment: Mapping[str, Any] | None,
    to_segment: Mapping[str, Any] | None,
) -> float:
    from_phrase = _is_phrase_segment(from_segment)
    to_phrase = _is_phrase_segment(to_segment)
    if from_phrase and to_phrase:
        return 0.0
    if from_phrase or to_phrase:
        return 0.5
    return 1.0


def _is_phrase_segment(segment: Mapping[str, Any] | None) -> bool:
    if not segment:
        return False
    return "phrase" in str(segment.get("role") or "").lower()


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number:
        return 0.0
    return number


def _clip(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))
