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
    assert plan[0].destination == (output / "Artist" / "Album" / "01 Track.mp3").resolve()
    assert plan[0].status == "ready"


def test_build_transcode_plan_skips_existing_non_empty_mp3(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    (output / "track.mp3").write_bytes(b"existing")

    plan = build_transcode_plan(source, output)

    assert plan[0].status == "existing"


def test_execute_transcode_plan_dry_run_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    plan = build_transcode_plan(source, output)

    result = execute_transcode_plan(plan, dry_run=True)

    assert result == {"planned": 1, "transcoded": 0, "existing": 0, "failed": 0}
    assert not output.exists()


def test_execute_transcode_plan_uses_metadata_only_ffmpeg_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    plan = build_transcode_plan(source, output)
    commands: list[list[str]] = []

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"mp3")
        return Completed()

    monkeypatch.setattr("taghag_import.transcode.subprocess.run", fake_run)

    result = execute_transcode_plan(plan)

    assert result["transcoded"] == 1
    command = commands[0]
    assert command[command.index("-map_metadata") + 1] == "0"
    assert command[command.index("-codec:a") + 1] == "libmp3lame"
    assert command[command.index("-b:a") + 1] == "320k"
    assert "-map" in command
    assert "0:a:0" in command
