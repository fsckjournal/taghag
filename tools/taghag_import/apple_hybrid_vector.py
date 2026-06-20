from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

APPLE_HYBRID_VECTOR_SCHEMA = "apple_hybrid_v1"

APPLE_HYBRID_DIMENSIONS = (
    "apple_bpm_norm",
    "pace_mean",
    "pace_volatility",
    "vocal_intensity_mean",
    "drum_intensity_mean",
    "bass_intensity_mean",
    "loudness_range_norm",
)


def build_apple_hybrid_vector(features: Mapping[str, Any]) -> list[float]:
    """Build the interpretable 7D Apple vector that fits the existing pgvector column."""

    return [
        _round(_clip(_number(features.get("apple_bpm")) / 200.0)),
        _round(_clip(_number(features.get("pace_mean")))),
        _round(_clip(_number(features.get("pace_volatility")))),
        _round(_clip(_number(features.get("vocal_intensity_mean")))),
        _round(_clip(_number(features.get("drum_intensity_mean")))),
        _round(_clip(_number(features.get("bass_intensity_mean")))),
        _round(_clip(_number(features.get("loudness_range_db")) / 30.0)),
    ]


def build_apple_hybrid_embedding_row(
    *,
    owner_user_id: str,
    audio_file_id: str,
    features: Mapping[str, Any],
    source_analysis_id: str | None = None,
    computed_at: str | None = None,
) -> dict[str, object]:
    pace_volatility = _round(_clip(_number(features.get("pace_volatility"))))
    return {
        "owner_user_id": owner_user_id,
        "audio_file_id": audio_file_id,
        "vector_schema": APPLE_HYBRID_VECTOR_SCHEMA,
        "embedding": build_apple_hybrid_vector(features),
        "producer_vibes_json": list(APPLE_HYBRID_DIMENSIONS),
        "dynamic_evolution": pace_volatility >= 0.12,
        "evolution_delta": pace_volatility,
        "source_analysis_id": source_analysis_id,
        "computed_at": computed_at or datetime.now(UTC).isoformat(),
    }


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


def _round(value: float) -> float:
    return round(value, 4)
