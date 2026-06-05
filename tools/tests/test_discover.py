from __future__ import annotations

from pathlib import Path

from taghag_import.discover import discover_audio_files


def test_discover_mp3_case_insensitive_and_out_of_scope_audio(tmp_path: Path) -> None:
    (tmp_path / "a.mp3").write_bytes(b"mp3")
    (tmp_path / "b.MP3").write_bytes(b"mp3")
    (tmp_path / "c.flac").write_bytes(b"flac")
    (tmp_path / "d.wav").write_bytes(b"wav")
    (tmp_path / "notes.txt").write_text("not audio", encoding="utf-8")

    found, skipped = discover_audio_files(tmp_path)

    assert [item.relative_path for item in found] == ["a.mp3", "b.MP3"]
    assert {item.relative_path for item in skipped} == {"c.flac", "d.wav"}
    assert {item.status for item in skipped} == {"out_of_scope_audio"}


def test_discover_ignores_junk_files_and_dirs(tmp_path: Path) -> None:
    (tmp_path / ".DS_Store").write_bytes(b"junk")
    (tmp_path / "._ghost.mp3").write_bytes(b"junk")
    macosx = tmp_path / "__MACOSX"
    macosx.mkdir()
    (macosx / "hidden.mp3").write_bytes(b"mp3")
    (tmp_path / "real.mp3").write_bytes(b"mp3")

    found, skipped = discover_audio_files(tmp_path)

    assert [item.relative_path for item in found] == ["real.mp3"]
    assert skipped == []
    assert (tmp_path / "real.mp3").exists()

