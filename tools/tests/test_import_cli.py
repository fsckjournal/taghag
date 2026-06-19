from __future__ import annotations

from pathlib import Path

from taghag_import import cli
from taghag_import.receipt import read_receipt


def test_import_batch_writes_receipt_before_upload_and_skips_db_on_dry_run(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "music"
    root.mkdir()
    (root / "track.flac").write_bytes(b"fake")
    receipt_dir = tmp_path / "receipts"

    monkeypatch.setattr(
        cli,
        "extract_flac_tags",
        lambda path: {
            "artist": "Artist",
            "title": "Title",
            "album": "Album",
            "label": "Label",
            "catalog_number": None,
            "release_date": None,
            "genre": "House",
            "subgenre": None,
            "bpm": "124",
            "musical_key": "Am",
            "year": "2024",
            "isrc": "USABC2400001",
            "compilation": None,
            "rating": None,
            "energy": None,
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

    class ExplodingClient:
        def __init__(self, config) -> None:
            raise AssertionError("DB client should not be constructed in dry-run")

    monkeypatch.setattr(cli, "TaghagDbClient", ExplodingClient)
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "import-batch",
            "--root",
            str(root),
            "--run-name",
            "batch",
            "--receipt-dir",
            str(receipt_dir),
            "--dry-run",
        ]
    )

    assert args.func(args) == 0

    receipts = list(receipt_dir.glob("*/receipt.jsonl"))
    assert len(receipts) == 1
    records = read_receipt(receipts[0])
    event_types = [record["event_type"] for record in records]
    assert "import_run_start" in event_types
    assert "audio_observed" in event_types
    assert "quality_check" in event_types
    assert "import_run_summary" in event_types
    assert "upload_result" not in event_types


def test_import_batch_accepts_required_flags() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "import-batch",
            "--root",
            "/tmp/music",
            "--run-name",
            "batch",
            "--dry-run",
            "--no-upload",
            "--receipt-dir",
            "receipts",
            "--postman-evidence",
            "evidence.log",
            "--unsafe-title-artist-evidence-match",
            "--verbose",
        ]
    )

    assert args.root == "/tmp/music"
    assert args.run_name == "batch"
    assert args.dry_run is True
    assert args.no_upload is True
    assert args.receipt_dir == "receipts"
    assert args.postman_evidence == "evidence.log"
    assert args.unsafe_title_artist_evidence_match is True
    assert args.verbose is True


def test_audit_mp3_command_accepts_root_and_output() -> None:
    args = cli.build_parser().parse_args(
        [
            "audit-flac",
            "--root",
            "/tmp/music",
            "--output-dir",
            "/tmp/reports",
        ]
    )

    assert args.root == "/tmp/music"
    assert args.output_dir == "/tmp/reports"


def test_dump_tags_command_accepts_one_input_source() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "dump-tags",
            "--path",
            "/tmp/track.flac",
            "--path",
            "/tmp/other.flac",
            "--out",
            "/tmp/tags.jsonl",
        ]
    )

    assert args.paths == ["/tmp/track.flac", "/tmp/other.flac"]
    assert args.out == "/tmp/tags.jsonl"


def test_write_tags_command_defaults_to_dry_run() -> None:
    parser = cli.build_parser()
    dry_run = parser.parse_args(["write-tags", "--plan", "/tmp/updates.csv"])
    execute = parser.parse_args(
        ["write-tags", "--plan", "/tmp/updates.csv", "--execute", "--force"]
    )

    assert dry_run.execute is False
    assert dry_run.force is False
    assert execute.execute is True
    assert execute.force is True


def test_provider_evidence_command_accepts_batch_inputs() -> None:
    args = cli.build_parser().parse_args(
        [
            "provider-evidence",
            "--isrc",
            "USABC2400001",
            "--isrc",
            "GBXYZ2400002",
            "--collection",
            "/tmp/collection.json",
            "--environment",
            "/tmp/environment.json",
            "--output-dir",
            "/tmp/provider-evidence",
            "--prepare-only",
        ]
    )

    assert args.isrcs == ["USABC2400001", "GBXYZ2400002"]
    assert args.collection == "/tmp/collection.json"
    assert args.environment == "/tmp/environment.json"
    assert args.output_dir == "/tmp/provider-evidence"
    assert args.prepare_only is True


def test_extract_dj_slice_command_accepts_sqlite_db_and_verbose() -> None:
    args = cli.build_parser().parse_args(
        [
            "extract-dj-slice",
            "--sqlite-db",
            "/tmp/music_v3.db",
            "--verbose",
        ]
    )

    assert args.sqlite_db == "/tmp/music_v3.db"
    assert args.verbose is True


def test_analyze_command_is_apple_only_without_engine_selector() -> None:
    args = cli.build_parser().parse_args(
        ["analyze", "--target", "/tmp/music", "--dry-run"]
    )

    assert args.target == Path("/tmp/music")
    assert args.dry_run is True
    assert not hasattr(args, "engines")
    assert not hasattr(args, "fm_model")
    assert not hasattr(args, "fm_prompt_version")
