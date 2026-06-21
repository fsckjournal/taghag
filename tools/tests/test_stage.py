from __future__ import annotations

import json
from pathlib import Path

import pytest

from taghag_import.stage import load_stage_manifest, plan_stage, plan_stage_manifest


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


def test_plan_stage_reads_real_isrc_without_monkeypatching_extractor(
    real_flac_factory, tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    flac_path = real_flac_factory(
        {"artist": "Pitchben", "title": "Soda", "isrc": "DEM091100068"}
    )
    flac_path.rename(source / "track.flac")

    monkeypatch.setattr("taghag_import.stage.probe_flac", lambda path: {"valid": True})
    monkeypatch.setattr("taghag_import.stage.sha256_file", lambda path: Path(path).name)
    monkeypatch.setattr("taghag_import.stage.pcm_sha256", lambda path: Path(path).name)

    plan = plan_stage(source, tmp_path / "out")

    assert len(plan.items) == 1
    assert plan.items[0].tags["isrc"] == "DEM091100068"
    assert plan.items[0].tags["artist"] == "Pitchben"


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


def test_load_stage_manifest_sorts_valid_sources(tmp_path: Path) -> None:
    first = tmp_path / "a.flac"
    second = tmp_path / "b.flac"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(
            [
                json.dumps({"source": str(second), "relative_path": "release/b.flac"}),
                json.dumps({"source": str(first), "relative_path": "release/a.flac"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    sources = load_stage_manifest(manifest)

    assert [item.source for item in sources] == [first.resolve(), second.resolve()]
    assert [item.relative_path for item in sources] == ["release/a.flac", "release/b.flac"]


@pytest.mark.parametrize(
    ("source_value", "relative_path", "error"),
    [
        ("missing.flac", "release/missing.flac", "absolute"),
        ("/missing.flac", "release/missing.flac", "does not exist"),
        ("/tmp/track.wav", "release/track.wav", "FLAC"),
        ("/tmp/track.flac", "/absolute.flac", "relative"),
        ("/tmp/track.flac", "../escape.flac", "traversal"),
    ],
)
def test_load_stage_manifest_rejects_invalid_entries(
    tmp_path: Path,
    source_value: str,
    relative_path: str,
    error: str,
) -> None:
    if source_value.startswith("/tmp/"):
        source = tmp_path / Path(source_value).name
        source.write_bytes(b"audio")
        source_value = str(source)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps({"source": source_value, "relative_path": relative_path}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=error):
        load_stage_manifest(manifest)


def test_load_stage_manifest_rejects_duplicate_sources_and_destinations(tmp_path: Path) -> None:
    first = tmp_path / "a.flac"
    second = tmp_path / "b.flac"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    duplicate_source = tmp_path / "duplicate-source.jsonl"
    duplicate_source.write_text(
        "\n".join(
            [
                json.dumps({"source": str(first), "relative_path": "release/a.flac"}),
                json.dumps({"source": str(first), "relative_path": "release/b.flac"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate source"):
        load_stage_manifest(duplicate_source)

    duplicate_destination = tmp_path / "duplicate-destination.jsonl"
    duplicate_destination.write_text(
        "\n".join(
            [
                json.dumps({"source": str(first), "relative_path": "release/track.flac"}),
                json.dumps({"source": str(second), "relative_path": "release/track.flac"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate relative_path"):
        load_stage_manifest(duplicate_destination)


def test_plan_stage_manifest_uses_relative_paths_and_cross_source_dedupe(
    tmp_path: Path, monkeypatch
) -> None:
    first = tmp_path / "source-a" / "a.flac"
    second = tmp_path / "source-b" / "b.flac"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(
            [
                json.dumps({"source": str(second), "relative_path": "release-b/b.flac"}),
                json.dumps({"source": str(first), "relative_path": "release-a/a.flac"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("taghag_import.stage.probe_flac", lambda path: {"valid": True})
    monkeypatch.setattr("taghag_import.stage.sha256_file", lambda path: Path(path).name)
    monkeypatch.setattr("taghag_import.stage.pcm_sha256", lambda path: "same-pcm")
    monkeypatch.setattr(
        "taghag_import.stage.extract_flac_tags",
        lambda path: {"isrc": None, "artist": "Artist", "title": Path(path).stem},
    )

    plan = plan_stage_manifest(manifest, tmp_path / "out")

    assert plan.source_root == manifest.resolve()
    assert plan.items[0].destination == (tmp_path / "out/flac/release-a/a.flac").resolve()
    assert plan.items[0].status == "admitted"
    assert plan.items[1].status == "audio-duplicate-blocked"
    assert plan.items[1].duplicate_of == first.resolve()
