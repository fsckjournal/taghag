from __future__ import annotations

from pathlib import Path

from taghag_import import apple_music_adapter
from taghag_import.apple_hybrid_vector import APPLE_HYBRID_VECTOR_SCHEMA


def _time(value: int, timescale: int = 1_000) -> dict[str, int]:
    return {"value": value, "timescale": timescale}


def _range(start_ms: int, duration_ms: int) -> dict[str, object]:
    return {"range": {"start": _time(start_ms), "duration": _time(duration_ms)}}


def _apple_payload() -> dict[str, object]:
    return {
        "rhythm": {
            "beatsPerMinute": 124.0,
            "beats": [_time(0), _time(500)],
            "bars": [_time(0)],
        },
        "key": {"ranges": [{"value": {"tonic": 0, "mode": 0}}]},
        "loudness": {
            "integrated": {"value": -10.0},
            "peak": {"value": -1.0},
            "momentary": [{"value": -11.0}],
            "shortTerm": [{"value": -12.0}, {"value": -8.0}],
        },
        "pace": {"ranges": [{"value": 0.4}, {"value": 0.8}]},
        "structure": {
            "sections": [_range(0, 16_000)],
            "segments": [_range(0, 8_000)],
            "phrases": [_range(0, 32_000)],
        },
        "instrumentActivity": {
            "activity": {
                "drum": [{"value": 0.9}, {"value": 0.8}],
                "bass": [{"value": 0.3}],
                "vocal": [{"value": 0.0}, {"value": 0.2}],
            }
        },
    }


class FakeClient:
    def __init__(self) -> None:
        self.analysis_runs: list[dict[str, object]] = []
        self.apple_analysis: list[dict[str, object]] = []
        self.derived_features: list[dict[str, object]] = []
        self.embeddings: list[dict[str, object]] = []
        self.segments: list[dict[str, object]] = []
        self.cues: list[dict[str, object]] = []

    def _audio_file_ids_for_file_keys(self, file_keys: set[str]) -> dict[str, str]:
        assert file_keys == {"sha256:filehash"}
        return {"sha256:filehash": "audio-1"}

    def upsert_apple_analysis_runs(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        self.analysis_runs.extend(rows)
        return [{"id": "run-1", **rows[0]}]

    def upsert_apple_track_analysis(self, rows: list[dict[str, object]]) -> None:
        self.apple_analysis.extend(rows)

    def upsert_apple_derived_features(self, rows: list[dict[str, object]]) -> None:
        self.derived_features.extend(rows)

    def upsert_track_embedding(self, rows: list[dict[str, object]]) -> None:
        self.embeddings.extend(rows)

    def insert_track_segments(self, rows: list[dict[str, object]]) -> None:
        self.segments.extend(rows)

    def insert_track_cues(self, rows: list[dict[str, object]]) -> None:
        self.cues.extend(rows)


def test_apple_ingestion_uploads_raw_runs_derived_features_segments_and_cues(
    tmp_path: Path,
    monkeypatch,
) -> None:
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"fake")
    client = FakeClient()

    monkeypatch.setattr(apple_music_adapter, "probe_flac", lambda path: {"duration_s": 300})
    monkeypatch.setattr(apple_music_adapter, "sha256_file", lambda path: "filehash")
    monkeypatch.setattr(apple_music_adapter, "analyze_flac", lambda path: _apple_payload())
    monkeypatch.setattr(apple_music_adapter, "get_mik_bpm", lambda filename: 125.0)

    summary = apple_music_adapter.run_apple_music_ingestion(client, "owner-1", [flac])

    assert summary["eligible"] == 1
    assert summary["analysis_runs"] == 1
    assert summary["derived_features"] == 1
    assert summary["apple_vectors"] == 1
    assert summary["segments"] == 3
    assert summary["cues"] == 3
    assert client.analysis_runs[0]["raw_result_json"] == _apple_payload()
    assert client.apple_analysis[0]["analysis_run_id"] == "run-1"
    assert client.apple_analysis[0]["source_artifact_sha256"] != "filehash"
    assert client.apple_analysis[0]["loudness_short_term"] == [{"value": -12.0}, {"value": -8.0}]
    assert client.derived_features[0]["phrase_count"] == 1
    assert client.derived_features[0]["bpm_agreement_score"] > 0.9
    assert client.embeddings[0]["source_analysis_id"] == "run-1"
    assert client.embeddings[0]["vector_schema"] == APPLE_HYBRID_VECTOR_SCHEMA
    assert len(client.embeddings[0]["embedding"]) == 7
    assert {segment["role"] for segment in client.segments} == {
        "apple_section",
        "apple_segment",
        "apple_phrase",
    }
    assert {cue["cue_type"] for cue in client.cues} == {"beat", "bar"}
    assert all("time_ms" in cue for cue in client.cues)
    assert all("ms_position" not in cue for cue in client.cues)
