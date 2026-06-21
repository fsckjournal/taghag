from __future__ import annotations

import json
from pathlib import Path

from taghag_import import cli
from taghag_import.postman_evidence import parse_tag_evidence
from taghag_import.provider_runner import (
    RESOLVE_ITEMS,
    ProviderRunnerConfig,
    build_postman_command,
    display_command,
    run_provider_batch,
)


def _config(tmp_path: Path) -> ProviderRunnerConfig:
    collection = tmp_path / "collection.json"
    environment = tmp_path / "environment.json"
    collection.write_text("{}", encoding="utf-8")
    environment.write_text("{}", encoding="utf-8")
    return ProviderRunnerConfig(
        postman_bin="postman",
        collection_path=collection,
        environment_path=environment,
        output_dir=tmp_path / "out",
        verify_binary=False,
    )


def test_build_postman_command_targets_exact_isrc_items_and_redacts_secrets(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    config = ProviderRunnerConfig(
        postman_bin=config.postman_bin,
        collection_path=config.collection_path,
        environment_path=config.environment_path,
        output_dir=config.output_dir,
        extra_env_vars={"beatport_access_token": "secret-token"},
        secret_keys={"beatport_access_token"},
        verify_binary=False,
    )

    command = build_postman_command("USABC2400001", config)
    joined = " ".join(command)
    displayed = display_command(command, config.secret_keys)

    for item in RESOLVE_ITEMS:
        assert item in command
    assert " -i Spotify " not in f" {joined} "
    assert " -i TIDAL " not in f" {joined} "
    assert " -i Beatport " not in f" {joined} "
    assert " -i Qobuz " not in f" {joined} "
    assert "lookup_isrc=USABC2400001" in command
    assert "beatport_access_token=secret-token" in command
    assert "secret-token" not in displayed
    assert "beatport_access_token=<redacted>" in displayed


def test_run_provider_batch_records_subprocess_failure_and_malformed_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    config = _config(tmp_path)

    class FailedRun:
        returncode = 1
        stdout = "[Tag Evidence JSON] not-json\n"
        stderr = "postman failed"

    monkeypatch.setattr("taghag_import.provider_runner.subprocess.run", lambda *args, **kwargs: FailedRun())

    result = run_provider_batch(["USABC2400001"], config)

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    evidence = result.evidence_log.read_text(encoding="utf-8")
    parsed = parse_tag_evidence(evidence)

    assert summary["failed"] == 1
    assert summary["results"][0]["status"] == "failed"
    assert parsed[0]["status"] == "malformed"
    assert parsed[1]["provider"] == "postman"
    assert parsed[1]["status"] == "error"
    assert parsed[1]["lookup_isrc"] == "USABC2400001"
    assert "postman failed" in parsed[1]["error"]


def test_run_provider_batch_treats_malformed_evidence_as_failure(
    tmp_path: Path, monkeypatch
) -> None:
    config = _config(tmp_path)

    class MalformedRun:
        returncode = 0
        stdout = "[Tag Evidence JSON] not-json\n"
        stderr = ""

    monkeypatch.setattr(
        "taghag_import.provider_runner.subprocess.run",
        lambda *args, **kwargs: MalformedRun(),
    )

    result = run_provider_batch(["USABC2400001"], config)
    parsed = parse_tag_evidence(result.evidence_log.read_text(encoding="utf-8"))

    assert result.summary["failed"] == 1
    assert result.summary["results"][0]["status"] == "failed"
    assert parsed[0]["status"] == "malformed"
    assert parsed[1]["status"] == "error"


def test_run_provider_batch_prepare_only_does_not_launch_subprocess(
    tmp_path: Path, monkeypatch
) -> None:
    base = _config(tmp_path)
    config = ProviderRunnerConfig(
        postman_bin=base.postman_bin,
        collection_path=base.collection_path,
        environment_path=base.environment_path,
        output_dir=base.output_dir,
        verify_binary=False,
        prepare_only=True,
    )

    def explode(*args, **kwargs):
        raise AssertionError("prepare-only must not run Postman")

    monkeypatch.setattr("taghag_import.provider_runner.subprocess.run", explode)

    result = run_provider_batch(["USABC2400001"], config)

    assert result.summary["prepared"] == 1
    assert result.summary["failed"] == 0
    assert result.evidence_log.read_text(encoding="utf-8") == ""


def test_provider_evidence_log_can_feed_import_batch(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "music"
    root.mkdir()
    (root / "track.flac").write_bytes(b"fake mp3")
    config = _config(tmp_path)
    marker = {
        "schema": "tagslut.postman.tag_evidence.v1",
        "provider": "beatport",
        "status": "matched",
        "lookup_isrc": "USABC2400001",
        "candidates": [
            {
                "field_candidates": [
                    {
                        "field_name": "canonical_label",
                        "normalized_value": "Provider Label",
                        "confidence": 0.9,
                    }
                ]
            }
        ],
    }

    class SuccessfulRun:
        returncode = 0
        stdout = "[Tag Evidence JSON] " + json.dumps(marker) + "\n"
        stderr = ""

    monkeypatch.setattr("taghag_import.provider_runner.subprocess.run", lambda *args, **kwargs: SuccessfulRun())
    monkeypatch.setattr(
        cli,
        "extract_flac_tags",
        lambda path: {
            "artist": "Artist",
            "title": "Title",
            "album": "Album",
            "label": "",
            "catalog_number": "",
            "release_date": "",
            "genre": "House",
            "subgenre": "",
            "bpm": "124",
            "musical_key": "Am",
            "year": "2024",
            "isrc": "USABC2400001",
            "compilation": "",
            "rating": "",
            "energy": "",
            "raw_id3": {},
        },
    )
    monkeypatch.setattr(
        cli,
        "probe_flac",
        lambda path: {
            "duration_s": 1.0,
            "bitrate_kbps": 320,
            "codec": "mp3",
            "decode_ok": True,
            "duration_ok": True,
            "bitrate_ok": True,
            "issue_codes": [],
        },
    )

    result = run_provider_batch(["USABC2400001"], config)
    records = cli._build_import_batch_records(
        str(root),
        postman_evidence=str(result.evidence_log),
    )
    evidence_records = [record for record in records if record["event_type"] == "tag_evidence"]

    assert len(evidence_records) == 1
    assert evidence_records[0]["tag_evidence"]["provider"] == "beatport"
    assert evidence_records[0]["tag_evidence"]["winning_fields_json"] == {
        "canonical_label": "Provider Label"
    }

    audio_observed = next(record for record in records if record["event_type"] == "audio_observed")
    dj_tag = audio_observed["dj_tag"]
    # Resolved provider evidence overlays the untrusted raw-ID3 label...
    assert dj_tag["label"] == "Provider Label"
    assert dj_tag["tag_source"] == "local_id3+postman_evidence"
    # ...but bpm/musical_key stay sourced from the measured/local tags --
    # provider catalog values must never silently overwrite them.
    assert dj_tag["bpm"] == 124.0
    assert dj_tag["musical_key"] == "Am"
