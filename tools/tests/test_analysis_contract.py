from __future__ import annotations

import json
from pathlib import Path

import pytest

from taghag_import.analysis_contract import load_analysis_sidecar


def _write_sidecar(path: Path, *, schema: str = "essentia-lexicon-sidecar/2") -> None:
    path.write_text(
        json.dumps(
            {
                "schema": schema,
                "model_profile": "magikbox-v1",
                "models": {"genre": "discogs-effnet", "mood": "mtg-jamendo"},
                "tracks": {
                    "/music/track.mp3": {
                        "file_key": "sha256:abc",
                        "genres": [{"label": "Electronic - House", "confidence": 0.8}],
                        "attributes": {
                            "happy": 0.4,
                            "aggressive": 0.2,
                            "relaxed": 0.3,
                            "party": 0.9,
                            "danceability": 0.95,
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_load_analysis_sidecar_normalizes_metadata_only_rows(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar)

    artifact = load_analysis_sidecar(sidecar)

    assert artifact.schema == "essentia-lexicon-sidecar/2"
    assert len(artifact.digest_sha256) == 64
    assert artifact.tracks[0].file_key == "sha256:abc"
    assert artifact.tracks[0].attributes["party"] == 0.9
    assert artifact.tracks[0].genres[0]["label"] == "Electronic - House"
    assert "audio" not in artifact.tracks[0].to_row()


def test_load_analysis_sidecar_rejects_wrong_schema(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar, schema="essentia-lexicon-sidecar/1")

    with pytest.raises(ValueError, match="unsupported analysis schema"):
        load_analysis_sidecar(sidecar)


def test_load_analysis_sidecar_rejects_missing_file_key(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    del payload["tracks"]["/music/track.mp3"]["file_key"]
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="file_key"):
        load_analysis_sidecar(sidecar)


def test_load_analysis_sidecar_computes_file_key_for_existing_local_mp3(tmp_path: Path) -> None:
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"local-mp3")
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    track = payload["tracks"].pop("/music/track.mp3")
    del track["file_key"]
    payload["tracks"][str(mp3)] = track
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    artifact = load_analysis_sidecar(sidecar)

    assert artifact.tracks[0].file_key.startswith("sha256:")


def test_load_analysis_sidecar_rejects_out_of_range_attribute(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["tracks"]["/music/track.mp3"]["attributes"]["party"] = 1.1
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="party"):
        load_analysis_sidecar(sidecar)
