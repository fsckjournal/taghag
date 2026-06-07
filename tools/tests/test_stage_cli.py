from __future__ import annotations

from pathlib import Path

from taghag_import import cli


def test_stage_cli_dry_run_uses_no_database(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "track.flac").write_bytes(b"flac")
    output = tmp_path / "output"
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
    args = cli.build_parser().parse_args(
        ["stage", "--source", str(source), "--output", str(output), "--dry-run"]
    )

    assert args.func(args) == 0
    assert args.verbose is True
