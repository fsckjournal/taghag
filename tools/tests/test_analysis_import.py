from __future__ import annotations

import json
from pathlib import Path

from taghag_import import cli
from taghag_import.receipt import read_receipt


def test_import_analysis_writes_metadata_only_receipt_without_db(tmp_path: Path, monkeypatch) -> None:
    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema": "essentia-lexicon-sidecar/2",
                "model_profile": "magikbox-v1",
                "models": {"mood": "model-v1"},
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

    class ExplodingClient:
        def __init__(self, config) -> None:
            raise AssertionError("DB client should not be constructed with --no-upload")

    monkeypatch.setattr(cli, "TaghagDbClient", ExplodingClient)
    receipt_dir = tmp_path / "receipts"
    args = cli.build_parser().parse_args(
        [
            "import-analysis",
            "--input",
            str(sidecar),
            "--receipt-dir",
            str(receipt_dir),
            "--no-upload",
        ]
    )

    assert args.func(args) == 0
    receipt = next(receipt_dir.glob("*/receipt.jsonl"))
    records = read_receipt(receipt)
    analysis = next(record for record in records if record["event_type"] == "track_analysis")
    assert analysis["file_key"] == "sha256:abc"
    assert analysis["track_analysis"]["party"] == 0.9
    assert "audio" not in json.dumps(records).lower()
