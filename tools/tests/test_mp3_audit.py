from __future__ import annotations

import csv
import json
from pathlib import Path

from taghag_import import mp3_audit


def test_run_mp3_audit_writes_metadata_only_reports(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "music"
    root.mkdir()
    mp3 = root / "track.mp3"
    mp3.write_bytes(b"local-audio-bytes")
    (root / "source.flac").write_bytes(b"flac-audio-bytes")

    monkeypatch.setattr(
        mp3_audit,
        "extract_mp3_tags",
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
        mp3_audit,
        "probe_mp3",
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
        mp3_audit,
        "classify_genre",
        lambda value: {
            "canonical_genre": "House",
            "canonical_subgenre": "Deep House",
        },
    )

    result = mp3_audit.run_mp3_audit(root, tmp_path / "reports")

    assert result.summary["mp3_files"] == 1
    assert result.summary["skipped_files"] == 1
    assert result.summary["issue_counts"] == {"missing_label": 1}

    records = [
        json.loads(line)
        for line in result.jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event_type"] for record in records] == [
        "mp3_audit",
        "skipped_input",
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

    issues = mp3_audit.metadata_issue_codes(tags, {})

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
