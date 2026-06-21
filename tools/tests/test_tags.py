from __future__ import annotations

from pathlib import Path

import pytest
from mutagen.flac import FLAC, Picture

from taghag_import.tags import apply_flac_tag_updates, dump_flac_tags, extract_flac_tags
from taghag_import.flac import extract_flac_tags as production_reader


def test_dump_flac_tags_summarizes_picture_frames(real_flac_factory) -> None:
    flac_path = real_flac_factory({"title": "Orig", "artist": "A"})
    audio = FLAC(flac_path)
    pic = Picture()
    pic.type = 3
    pic.mime = "image/jpeg"
    pic.desc = "Cover"
    pic.data = b"jpeg"
    audio.add_picture(pic)
    audio.save()

    dumped = dump_flac_tags(flac_path)

    assert dumped["title"] == ["Orig"]
    assert dumped["artist"] == ["A"]
    assert dumped["PICTURE:Cover"] == ["<binary:4 bytes>"]
    assert b"jpeg" not in repr(dumped).encode("utf-8")


def test_apply_flac_tag_updates_is_dry_run_by_default(real_flac_factory) -> None:
    flac_path = real_flac_factory({"title": "Orig"})
    before = flac_path.read_bytes()

    result = apply_flac_tag_updates(
        flac_path,
        {"bpm": "124", "label": "Dry Run Records"},
    )

    assert result.executed is False
    assert result.planned_fields == ["bpm", "label"]
    assert result.applied_fields == []
    assert flac_path.read_bytes() == before
    audio = FLAC(flac_path)
    assert not audio.get("bpm")
    assert not audio.get("label")


def test_apply_flac_tag_updates_preserves_existing_fields(real_flac_factory) -> None:
    flac_path = real_flac_factory({"title": "Original Title"})

    result = apply_flac_tag_updates(
        flac_path,
        {
            "title": "Replacement Title",
            "bpm": "126",
            "label": "Selective Records",
            "energy": "7",
        },
        execute=True,
    )

    audio = FLAC(flac_path)
    assert result.planned_fields == ["bpm", "energy", "label"]
    assert result.applied_fields == ["bpm", "energy", "label"]
    assert result.skipped_fields == ["title"]
    assert audio["title"] == ["Original Title"]
    assert audio["bpm"] == ["126"]
    assert audio["label"] == ["Selective Records"]
    assert audio["energy"] == ["7"]


def test_apply_flac_tag_updates_force_overwrites_only_requested_field(real_flac_factory) -> None:
    flac_path = real_flac_factory({"title": "Orig", "bpm": "120"})

    result = apply_flac_tag_updates(
        flac_path,
        {"title": "Forced Title"},
        execute=True,
        force=True,
    )

    audio = FLAC(flac_path)
    assert result.applied_fields == ["title"]
    assert audio["title"] == ["Forced Title"]
    assert audio["bpm"] == ["120"]


def test_apply_flac_tag_updates_rejects_multi_value_isrc(real_flac_factory) -> None:
    flac_path = real_flac_factory()

    with pytest.raises(ValueError, match="invalid ISRC"):
        apply_flac_tag_updates(
            flac_path,
            {"isrc": "USAT21600354; USAT21601223"},
            execute=True,
        )


def test_apply_flac_tag_updates_accepts_single_valid_isrc(real_flac_factory) -> None:
    flac_path = real_flac_factory()

    result = apply_flac_tag_updates(
        flac_path,
        {"isrc": "usabc2400001"},
        execute=True,
    )

    audio = FLAC(flac_path)
    assert result.applied_fields == ["isrc"]
    assert audio["isrc"] == ["USABC2400001"]


def test_extract_flac_tags_derives_release_date_and_year(real_flac_factory) -> None:
    flac_path = real_flac_factory({"date": "2024-05-03"})

    extracted = extract_flac_tags(flac_path)

    assert extracted["release_date"] == "2024-05-03"
    assert extracted["year"] == "2024"


def test_round_trip_via_production_reader(real_flac_factory) -> None:
    """apply_flac_tag_updates writes must be readable by flac.py's production reader."""
    flac_path = real_flac_factory()

    apply_flac_tag_updates(
        flac_path,
        {
            "title": "Round Trip",
            "artist": "RT Artist",
            "isrc": "USABC2400001",
            "bpm": "128",
            "musical_key": "Am",
            "label": "RT Label",
            "catalog_number": "RT001",
            "release_date": "2024-01-01",
            "genre": "Techno",
        },
        execute=True,
    )

    via_prod = production_reader(flac_path)
    assert via_prod["title"] == "Round Trip"
    assert via_prod["artist"] == "RT Artist"
    assert via_prod["isrc"] == "USABC2400001"
    assert via_prod["bpm"] == "128"
    assert via_prod["musical_key"] == "Am"
    assert via_prod["label"] == "RT Label"
    assert via_prod["catalog_number"] == "RT001"
    assert via_prod["release_date"] == "2024-01-01"
    assert via_prod["genre"] == "Techno"


def test_round_trip_extended_fields_via_mutagen(real_flac_factory) -> None:
    """Fields that flac.py doesn't read must round-trip through mutagen directly."""
    flac_path = real_flac_factory()

    apply_flac_tag_updates(
        flac_path,
        {
            "rating": "8",
            "energy": "9",
            "pcm_hash": "abc123",
            "spotify_id": "spotify:track:x",
            "beatport_album_id": "12345",
            "beatport_track_id": "67890",
        },
        execute=True,
    )

    audio = FLAC(flac_path)
    assert audio["rating"] == ["8"]
    assert audio["energy"] == ["9"]
    assert audio["pcm_hash"] == ["abc123"]
    assert audio["spotify_id"] == ["spotify:track:x"]
    assert audio["beatport_album_id"] == ["12345"]
    assert audio["beatport_track_id"] == ["67890"]
