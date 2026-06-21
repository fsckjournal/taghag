from __future__ import annotations

import csv
import json
from pathlib import Path

from taghag_import import audio_audit


def test_run_audio_audit_writes_metadata_only_reports(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "music"
    root.mkdir()
    mp3 = root / "track.flac"
    mp3.write_bytes(b"local-audio-bytes")
    (root / "source.flac").write_bytes(b"flac-audio-bytes")

    monkeypatch.setattr(
        audio_audit,
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
            "energy": "7",
            "track_number": "1",
            "composer": "",
            "raw_id3": {"TIT2": "Title"},
        },
    )
    monkeypatch.setattr(
        audio_audit,
        "probe_flac",
        lambda path: {
            "duration_s": 180.5,
            "bitrate_kbps": 320,
            "codec": "mp3",
            "sample_rate_hz": 44100,
            "channels": 2,
            "decode_ok": True,
            "duration_ok": True,
            "bitrate_ok": True,
            "probe_ok": True,
            "probe_error": None,
            "decode_error": None,
            "issue_codes": [],
        },
    )
    monkeypatch.setattr(
        audio_audit,
        "classify_genre",
        lambda value: {
            "canonical_genre": "House",
            "canonical_subgenre": "Deep House",
        },
    )

    result = audio_audit.run_audio_audit(root, tmp_path / "reports")

    assert result.summary["audio_files"] == 2
    assert result.summary["skipped_files"] == 0
    assert result.summary["issue_counts"] == {"missing_label": 2}

    records = [
        json.loads(line)
        for line in result.jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event_type"] for record in records] == [
        "audio_audit",
        "audio_audit",
    ]
    assert records[0]["canonical_genre"] == "House"
    assert records[0]["canonical_subgenre"] == "Deep House"
    assert records[0]["sample_rate_hz"] == 44100
    assert records[0]["channels"] == 2
    assert records[0]["issue_codes"] == ["missing_label"]

    report_text = result.jsonl_path.read_text(encoding="utf-8")
    report_text += result.csv_path.read_text(encoding="utf-8")
    report_text += result.summary_path.read_text(encoding="utf-8")
    assert "local-audio-bytes" not in report_text
    assert "flac-audio-bytes" not in report_text

    with result.csv_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["artist"] == "Artist"
    assert csv_rows[0]["sample_rate_hz"] == "44100"
    assert csv_rows[0]["issue_codes"] == "missing_label"


def test_run_audio_audit_reads_real_isrc_without_monkeypatching_extractor(
    real_flac_factory, tmp_path: Path
) -> None:
    root = tmp_path / "music"
    root.mkdir()
    flac_path = real_flac_factory(
        {"artist": "Pitchben", "title": "Soda", "isrc": "DEM091100068"}
    )
    flac_path.rename(root / "track.flac")

    result = audio_audit.run_audio_audit(root, tmp_path / "reports")

    records = [
        json.loads(line)
        for line in result.jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert records[0]["isrc"] == "DEM091100068"
    assert records[0]["artist"] == "Pitchben"
    assert "missing_isrc" not in records[0]["issue_codes"]


def test_is_malformed_isrc_flags_multi_value_and_accepts_single_valid() -> None:
    assert audio_audit.is_malformed_isrc("USAT21600354; USAT21601223") is True
    assert audio_audit.is_malformed_isrc("not-an-isrc") is True
    assert audio_audit.is_malformed_isrc("") is False
    assert audio_audit.is_malformed_isrc(None) is False
    assert audio_audit.is_malformed_isrc("USABC2400001") is False


def test_metadata_issue_codes_flags_malformed_isrc() -> None:
    tags = {
        "artist": "Lizzo",
        "title": "Good as Hell",
        "bpm": "124",
        "musical_key": "Am",
        "label": "Atlantic",
        "isrc": "USAT21600354; USAT21601223",
        "genre": "Pop",
        "subgenre": "Pop",
    }

    issues = audio_audit.metadata_issue_codes(tags, {})

    assert issues == ["malformed_isrc"]


def test_metadata_issue_codes_reuses_import_batch_contract() -> None:
    tags = {
        "artist": "",
        "title": "",
        "bpm": "",
        "musical_key": "",
        "label": "",
        "isrc": "",
        "genre": "",
        "subgenre": "",
    }

    issues = audio_audit.metadata_issue_codes(tags, {})

    assert issues == [
        "missing_artist",
        "missing_bpm",
        "missing_genre",
        "missing_isrc",
        "missing_key",
        "missing_label",
        "missing_subgenre",
        "missing_title",
    ]
