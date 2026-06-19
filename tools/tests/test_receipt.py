from __future__ import annotations

from pathlib import Path

import pytest

from taghag_import.receipt import event, read_receipt, receipt_path_for_run, write_receipt
from taghag_import.tags import compute_file_identity


def test_receipt_path_for_run() -> None:
    path = receipt_path_for_run("artifacts/import_runs", "run-1")

    assert path.as_posix().endswith("artifacts/import_runs/run-1/receipt.jsonl")


def test_write_receipt_uses_sorted_jsonl_keys(tmp_path: Path) -> None:
    path = tmp_path / "receipt.jsonl"

    write_receipt(path, [event("import_run_summary", z=1, a=2)])

    line = path.read_text(encoding="utf-8").strip()
    assert line.startswith('{"a": 2, "event_type":')
    assert read_receipt(path) == [{"a": 2, "event_type": "import_run_summary", "z": 1}]


def test_write_receipt_rejects_header_shaped_secrets(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_receipt(tmp_path / "receipt.jsonl", [{"Authorization": "Bearer nope"}])


def test_compute_file_identity_prefers_sha256(tmp_path: Path) -> None:
    file_path = tmp_path / "track.flac"
    file_path.write_bytes(b"hello")

    identity = compute_file_identity(file_path, "track.flac")

    assert str(identity["file_key"]).startswith("sha256:")
    assert identity["checksum_sha256"]
    assert identity["checksum_prefix"] == str(identity["checksum_sha256"])[:24]
    assert identity["identity_source"] == "checksum_sha256"

