from __future__ import annotations

from pathlib import Path

from mutagen.id3 import APIC, COMM, ID3, TBPM, TDRC, TIT2, TPE1, TXXX

from taghag_import.tags import apply_flac_tag_updates, dump_flac_tags, extract_flac_tags


def _tagged_mp3(path: Path) -> None:
    path.write_bytes(b"")
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["Original Title"]))
    tags.add(TPE1(encoding=3, text=["Original Artist"]))
    tags.add(COMM(encoding=3, lang="eng", desc="", text=["8 Energy"]))
    tags.add(TXXX(encoding=3, desc="CUSTOM_KEEP", text=["keep me"]))
    tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=b"jpeg"))
    tags.save(path)


def test_dump_flac_tags_summarizes_binary_frames(tmp_path: Path) -> None:
    mp3 = tmp_path / "track.flac"
    _tagged_mp3(mp3)

    dumped = dump_flac_tags(mp3)

    assert dumped["TIT2"] == ["Original Title"]
    assert dumped["TXXX:CUSTOM_KEEP"] == ["keep me"]
    assert dumped["APIC:Cover"] == ["<binary:4 bytes>"]
    assert b"jpeg" not in repr(dumped).encode("utf-8")


def test_apply_flac_tag_updates_is_dry_run_by_default(tmp_path: Path) -> None:
    mp3 = tmp_path / "track.flac"
    _tagged_mp3(mp3)
    before = mp3.read_bytes()

    result = apply_flac_tag_updates(
        mp3,
        {"bpm": "124", "label": "Dry Run Records"},
    )

    assert result.executed is False
    assert result.planned_fields == ["bpm", "label"]
    assert result.applied_fields == []
    assert mp3.read_bytes() == before
    tags = ID3(mp3)
    assert "TBPM" not in tags
    assert "TPUB" not in tags


def test_apply_flac_tag_updates_preserves_existing_and_unknown_frames(tmp_path: Path) -> None:
    mp3 = tmp_path / "track.flac"
    _tagged_mp3(mp3)

    result = apply_flac_tag_updates(
        mp3,
        {
            "title": "Replacement Title",
            "bpm": "126",
            "label": "Selective Records",
            "energy": "7",
        },
        execute=True,
    )

    tags = ID3(mp3)
    assert result.planned_fields == ["bpm", "energy", "label"]
    assert result.applied_fields == ["bpm", "energy", "label"]
    assert result.skipped_fields == ["title"]
    assert tags["TIT2"].text == ["Original Title"]
    assert tags["TBPM"].text == ["126"]
    assert tags["TPUB"].text == ["Selective Records"]
    assert tags["TXXX:LABEL"].text == ["Selective Records"]
    assert tags["TXXX:ENERGY"].text == ["7"]
    assert tags["TXXX:CUSTOM_KEEP"].text == ["keep me"]
    assert tags.getall("COMM")[0].text == ["8 Energy"]
    assert tags["APIC:Cover"].data == b"jpeg"


def test_apply_flac_tag_updates_force_overwrites_only_requested_field(tmp_path: Path) -> None:
    mp3 = tmp_path / "track.flac"
    _tagged_mp3(mp3)
    tags = ID3(mp3)
    tags.add(TBPM(encoding=3, text=["120"]))
    tags.save(mp3)

    result = apply_flac_tag_updates(
        mp3,
        {"title": "Forced Title"},
        execute=True,
        force=True,
    )

    tags = ID3(mp3)
    assert result.applied_fields == ["title"]
    assert tags["TIT2"].text == ["Forced Title"]
    assert tags["TBPM"].text == ["120"]
    assert tags["TXXX:CUSTOM_KEEP"].text == ["keep me"]
    assert tags.getall("COMM")[0].text == ["8 Energy"]


def test_extract_flac_tags_derives_release_date_and_year_from_date_frame(
    tmp_path: Path,
) -> None:
    mp3 = tmp_path / "track.flac"
    mp3.write_bytes(b"")
    tags = ID3()
    tags.add(TDRC(encoding=3, text=["2024-05-03"]))
    tags.save(mp3)

    extracted = extract_flac_tags(mp3)

    assert extracted["release_date"] == "2024-05-03"
    assert extracted["year"] == "2024"
