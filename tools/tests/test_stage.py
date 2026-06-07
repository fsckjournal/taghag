from __future__ import annotations

from pathlib import Path

from taghag_import.stage import plan_stage


def test_plan_stage_blocks_same_pcm_even_in_compilation_folder(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    first = source / "Album" / "a.flac"
    second = source / "Compilations" / "b.flac"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    monkeypatch.setattr("taghag_import.stage.probe_flac", lambda path: {"valid": True})
    monkeypatch.setattr("taghag_import.stage.sha256_file", lambda path: Path(path).name)
    monkeypatch.setattr("taghag_import.stage.pcm_sha256", lambda path: "same-pcm")
    monkeypatch.setattr(
        "taghag_import.stage.extract_flac_tags",
        lambda path: {"isrc": "SAME", "artist": "Artist", "title": "Title"},
    )

    plan = plan_stage(source, tmp_path / "out")

    admitted = [item for item in plan.items if item.status == "admitted"]
    blocked = [item for item in plan.items if item.status == "audio-duplicate-blocked"]
    assert [item.source for item in admitted] == [first.resolve()]
    assert [item.source for item in blocked] == [second.resolve()]
    assert blocked[0].duplicate_of == first.resolve()


def test_plan_stage_reports_metadata_match_without_blocking(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    first = source / "a.flac"
    second = source / "b.flac"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    monkeypatch.setattr("taghag_import.stage.probe_flac", lambda path: {"valid": True})
    monkeypatch.setattr("taghag_import.stage.sha256_file", lambda path: Path(path).name)
    monkeypatch.setattr("taghag_import.stage.pcm_sha256", lambda path: Path(path).name)
    monkeypatch.setattr(
        "taghag_import.stage.extract_flac_tags",
        lambda path: {"isrc": "SAME", "artist": "Artist", "title": "Title"},
    )

    plan = plan_stage(source, tmp_path / "out")

    assert len([item for item in plan.items if item.status == "admitted"]) == 2
    assert len(plan.metadata_candidates) == 4
