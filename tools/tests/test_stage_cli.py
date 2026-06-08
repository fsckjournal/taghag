from __future__ import annotations

from pathlib import Path

import pytest

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


def test_stage_cli_routes_manifest_input(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("", encoding="utf-8")
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        cli,
        "plan_stage_manifest",
        lambda manifest_path, output: calls.append((manifest_path, output))
        or type("Plan", (), {"items": [], "metadata_candidates": []})(),
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
        ["stage", "--manifest", str(manifest), "--output", str(tmp_path / "out"), "--dry-run"]
    )

    assert args.func(args) == 0
    assert calls == [(str(manifest), str(tmp_path / "out"))]


def test_stage_cli_requires_exactly_one_input() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["stage", "--dry-run"])
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["stage", "--source", "/tmp/source", "--manifest", "/tmp/manifest.jsonl"]
        )
