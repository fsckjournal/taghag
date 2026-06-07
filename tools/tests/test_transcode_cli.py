from __future__ import annotations

from pathlib import Path

from taghag_import import cli


def test_transcode_command_dry_run_accepts_source_and_output(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    output = tmp_path / "output"
    args = cli.build_parser().parse_args(
        ["transcode", "--source", str(source), "--output", str(output), "--dry-run"]
    )

    assert args.func(args) == 0
    assert not output.exists()


def test_transcode_command_is_verbose_by_default() -> None:
    args = cli.build_parser().parse_args(
        ["transcode", "--source", "/tmp/source", "--output", "/tmp/output"]
    )

    assert args.verbose is True


def test_transcode_command_accepts_quiet_mode() -> None:
    args = cli.build_parser().parse_args(
        ["transcode", "--source", "/tmp/source", "--output", "/tmp/output", "--quiet"]
    )

    assert args.verbose is False
