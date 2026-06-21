from __future__ import annotations

import hashlib
from pathlib import Path

from taghag_import.flac import discover_flacs, extract_flac_tags, pcm_sha256


def test_discover_flacs_accepts_file_and_filters_junk(tmp_path: Path) -> None:
    album = tmp_path / "album"
    album.mkdir()
    track = album / "track.FLAC"
    track.write_bytes(b"flac")
    (album / "cover.jpg").write_bytes(b"jpg")
    (album / "._track.flac").write_bytes(b"junk")

    assert discover_flacs(track) == [track.resolve()]
    assert discover_flacs(album) == [track.resolve()]


def test_pcm_sha256_hashes_decoded_stdout(tmp_path: Path, monkeypatch) -> None:
    track = tmp_path / "track.flac"
    track.write_bytes(b"container")

    class Stdout:
        def read(self, size: int) -> bytes:
            return b"pcm" if not getattr(self, "done", False) else b""

        done = False

    stdout = Stdout()
    original_read = stdout.read

    def read_once(size: int) -> bytes:
        chunk = original_read(size)
        stdout.done = True
        return chunk

    stdout.read = read_once  # type: ignore[method-assign]

    class Process:
        returncode = 0
        stderr = type("Stderr", (), {"read": lambda self: b""})()

        def wait(self) -> int:
            return 0

    process = Process()
    process.stdout = stdout
    monkeypatch.setattr("taghag_import.flac.subprocess.Popen", lambda *args, **kwargs: process)

    assert pcm_sha256(track) == hashlib.sha256(b"pcm").hexdigest()


def test_extract_flac_tags_reads_real_vorbis_comments(real_flac_factory) -> None:
    flac_path = real_flac_factory(
        {
            "artist": "Pitchben",
            "title": "Soda",
            "album": "Soda",
            "isrc": "DEM091100068",
            "bpm": "121",
            "initialkey": "2B",
        }
    )

    extracted = extract_flac_tags(flac_path)

    assert extracted["artist"] == "Pitchben"
    assert extracted["title"] == "Soda"
    assert extracted["isrc"] == "DEM091100068"
    assert extracted["bpm"] == "121"
    assert extracted["musical_key"] == "2B"
