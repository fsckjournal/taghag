from __future__ import annotations

from pathlib import Path

from taghag_import.discover import discover_audio_files


def test_discover_audio_case_insensitive_and_out_of_scope_audio(tmp_path: Path) -> None:
    (tmp_path / "a.flac").write_bytes(b"flac")
    (tmp_path / "b.FLAC").write_bytes(b"flac")
    (tmp_path / "c.flac").write_bytes(b"flac")
    (tmp_path / "d.wav").write_bytes(b"wav")
    (tmp_path / "setlist.m3u").write_text("#EXTM3U\n", encoding="utf-8")
    (tmp_path / "setlist.m3u8").write_text("#EXTM3U\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not audio", encoding="utf-8")

    found, skipped = discover_audio_files(tmp_path)

    assert [item.relative_path for item in found] == ["a.flac", "b.FLAC", "c.flac"]
    assert {item.relative_path for item in skipped} == {
        "d.wav",
        "setlist.m3u",
        "setlist.m3u8",
    }
    assert {item.status for item in skipped} == {"out_of_scope_audio", "playlist"}


def test_discover_ignores_junk_files_and_dirs(tmp_path: Path) -> None:
    (tmp_path / ".DS_Store").write_bytes(b"junk")
    (tmp_path / "._ghost.flac").write_bytes(b"junk")
    macosx = tmp_path / "__MACOSX"
    macosx.mkdir()
    (macosx / "hidden.flac").write_bytes(b"mp3")
    hidden = tmp_path / ".metadata"
    hidden.mkdir()
    (hidden / "hidden.flac").write_bytes(b"mp3")
    (tmp_path / "real.flac").write_bytes(b"mp3")

    found, skipped = discover_audio_files(tmp_path)

    assert [item.relative_path for item in found] == ["real.flac"]
    assert skipped == []
    assert (tmp_path / "real.flac").exists()
