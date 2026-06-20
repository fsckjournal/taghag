from __future__ import annotations

from taghag_import.apple_butterflow import score_apple_transition
from taghag_import.apple_hybrid_vector import (
    APPLE_HYBRID_DIMENSIONS,
    APPLE_HYBRID_VECTOR_SCHEMA,
    build_apple_hybrid_embedding_row,
)


def test_build_apple_hybrid_embedding_row_is_interpretable_and_pgvector_compatible() -> None:
    row = build_apple_hybrid_embedding_row(
        owner_user_id="owner-1",
        audio_file_id="audio-1",
        source_analysis_id="run-1",
        features={
            "apple_bpm": 124.0,
            "pace_mean": 0.72,
            "pace_volatility": 0.18,
            "vocal_intensity_mean": 0.2,
            "drum_intensity_mean": 0.9,
            "bass_intensity_mean": 0.6,
            "loudness_range_db": 12.0,
        },
    )

    assert row["owner_user_id"] == "owner-1"
    assert row["audio_file_id"] == "audio-1"
    assert row["source_analysis_id"] == "run-1"
    assert row["vector_schema"] == APPLE_HYBRID_VECTOR_SCHEMA
    assert row["producer_vibes_json"] == list(APPLE_HYBRID_DIMENSIONS)
    assert row["dynamic_evolution"] is True
    assert row["evolution_delta"] == 0.18
    assert len(row["embedding"]) == 7
    assert row["embedding"] == [0.62, 0.72, 0.18, 0.2, 0.9, 0.6, 0.4]


def test_score_apple_transition_penalizes_vocals_loudness_pace_and_non_phrase_cuts() -> None:
    good = score_apple_transition(
        {
            "pace_mean": 0.66,
            "pace_volatility": 0.08,
            "vocal_intensity_mean": 0.0,
            "loudness_integrated": -11.0,
            "bpm_agreement_score": 0.96,
            "key_stable": True,
        },
        {
            "pace_mean": 0.68,
            "pace_volatility": 0.09,
            "vocal_intensity_mean": 0.1,
            "loudness_integrated": -10.5,
            "bpm_agreement_score": 0.95,
            "key_stable": True,
        },
        from_segment={"role": "apple_phrase"},
        to_segment={"role": "apple_phrase"},
    )
    risky = score_apple_transition(
        {
            "pace_mean": 0.42,
            "pace_volatility": 0.4,
            "vocal_intensity_mean": 0.9,
            "loudness_integrated": -23.0,
            "bpm_agreement_score": 0.62,
            "key_stable": False,
        },
        {
            "pace_mean": 0.9,
            "pace_volatility": 0.28,
            "vocal_intensity_mean": 0.8,
            "loudness_integrated": -7.0,
            "bpm_agreement_score": 0.7,
            "key_stable": True,
        },
        from_segment={"role": "apple_section"},
        to_segment={"role": "apple_segment"},
    )

    assert good.total_cost < risky.total_cost
    assert good.terms["phrase_boundary_penalty"] == 0.0
    assert risky.terms["phrase_boundary_penalty"] == 1.0
    assert risky.terms["vocal_overlap_risk"] > good.terms["vocal_overlap_risk"]
    assert risky.terms["loudness_handoff"] > good.terms["loudness_handoff"]
    assert risky.terms["pace_delta"] > good.terms["pace_delta"]
