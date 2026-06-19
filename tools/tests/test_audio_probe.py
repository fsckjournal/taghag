from __future__ import annotations

import json
from pathlib import Path

from taghag_import.audio_probe import probe_flac


def test_probe_flac_selects_audio_stream_and_reports_technical_fields(
    tmp_path: Path, monkeypatch
) -> None:
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"fake")

    class Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, **kwargs):
        if command[0] == "ffprobe":
            return Completed(
                0,
                json.dumps(
                    {
                        "format": {"duration": "180.25", "bit_rate": "320000"},
                        "streams": [
                            {"codec_type": "video", "codec_name": "mjpeg"},
                            {
                                "codec_type": "audio",
                                "codec_name": "flac",
                                "sample_rate": "44100",
                                "channels": 2,
                            },
                        ],
                    }
                ),
            )
        return Completed(0)

    monkeypatch.setattr("taghag_import.audio_probe.subprocess.run", fake_run)

    result = probe_flac(flac)

    assert result["codec"] == "flac"
    assert result["sample_rate_hz"] == 44100
    assert result["channels"] == 2
    assert result["duration_s"] == 180.25
    assert result["bitrate_kbps"] == 320
    assert result["issue_codes"] == []
