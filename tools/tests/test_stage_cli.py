from __future__ import annotations

from pathlib import Path

from taghag_import import cli


def test_stage_cli_dry_run_uses_no_database(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    monkeypatch.setattr(
        cli,
        "plan_stage",
        lambda source, output: type("Plan", (), {"items": [], "metadata_candidates": []})(),
    )
    monkeypatch.setattr(
        cli,
        "execute_stage",
        lambda plan, dry_run, verbose: {
            "discovered": 0,
            "admitted": 0,
            "duplicates_blocked": 0,
            "invalid": 0,
            "planned": 0,
            "transcoded": 0,
            "existing": 0,
            "failed": 0,
        },
    )
    args = cli.build_parser().parse_args(["stage", "--source", str(source), "--dry-run"])

    assert args.func(args) == 0
    assert args.verbose is True


def test_stage_cli_uses_env_default_output(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setenv("TAGHAG_MP3_OUTPUT_ROOT", "/Volumes/LOSSY/taghag")

    args = cli.build_parser().parse_args(["stage", "--source", str(source), "--dry-run"])

    assert args.output == "/Volumes/LOSSY/taghag"
