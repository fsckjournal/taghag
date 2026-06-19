from __future__ import annotations

from pathlib import Path

import pytest

from taghag_import.transcode import build_transcode_plan, execute_transcode_plan


def test_build_transcode_plan_mirrors_flac_paths(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    album = source / "Artist" / "Album"
    album.mkdir(parents=True)
    (album / "01 Track.FLAC").write_bytes(b"flac")
    (album / "cover.jpg").write_bytes(b"image")

    plan = build_transcode_plan(source, output)

    assert len(plan) == 1
    assert plan[0].source == (album / "01 Track.FLAC").resolve()
    assert plan[0].destination == (output / "Artist" / "Album" / "01 Track.flac").resolve()
    assert plan[0].status == "ready"


def test_build_transcode_plan_skips_existing_non_empty_flac(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    (output / "track.flac").write_bytes(b"existing")

    plan = build_transcode_plan(source, output)

    assert plan[0].status == "existing"


def test_execute_transcode_plan_dry_run_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    plan = build_transcode_plan(source, output)

    result = execute_transcode_plan(plan, dry_run=True)

    assert result == {"planned": 1, "transcoded": 0, "existing": 0, "failed": 0, "failed-skipped": 0}
    assert not output.exists()


def test_execute_transcode_plan_dry_run_prints_per_file_when_verbose(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    plan = build_transcode_plan(source, output)

    execute_transcode_plan(plan, dry_run=True, verbose=True)

    assert "planned:" in capsys.readouterr().out


def test_execute_transcode_plan_copies_flac_without_reencoding(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    (source / "track.flac").write_bytes(b"flac-bytes")
    plan = build_transcode_plan(source, output)

    result = execute_transcode_plan(plan)

    assert result["transcoded"] == 1
    assert (output / "track.flac").read_bytes() == b"flac-bytes"
