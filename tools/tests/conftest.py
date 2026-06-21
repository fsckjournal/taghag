from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


@pytest.fixture
def real_flac_factory(tmp_path: Path):
    """Build genuine FLAC containers (real header, real Vorbis comments).

    Exercises mutagen.flac.FLAC against an actual FLAC stream rather than a
    monkeypatched extractor, so regressions in reading the real container
    format (as opposed to ID3 frames, which FLAC files don't carry) get
    caught instead of silently passing against a fake.
    """
    if shutil.which("flac") is None:
        pytest.skip("flac CLI not available")

    counter = {"n": 0}

    def _build(tags: dict[str, str] | None = None) -> Path:
        from mutagen.flac import FLAC

        counter["n"] += 1
        wav_path = tmp_path / f"_silence_{counter['n']}.wav"
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(44100)
            wav_file.writeframes(b"\x00\x00" * 4410)

        flac_path = tmp_path / f"_track_{counter['n']}.flac"
        subprocess.run(
            ["flac", "--totally-silent", "-f", "-o", str(flac_path), str(wav_path)],
            check=True,
        )

        if tags:
            audio = FLAC(flac_path)
            for key, value in tags.items():
                audio[key] = value
            audio.save()

        return flac_path

    return _build
