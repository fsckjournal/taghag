from __future__ import annotations

import json
from pathlib import Path
import subprocess


def probe_mp3(path: str | Path) -> dict[str, object]:
    file_path = Path(path).expanduser().resolve()
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,bit_rate",
            "-of",
            "json",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    duration_seconds = None
    bit_rate = None
    if probe.returncode == 0 and probe.stdout.strip():
        payload = json.loads(probe.stdout)
        format_data = payload.get("format", {})
        if format_data.get("duration") is not None:
            duration_seconds = round(float(format_data["duration"]), 3)
        if format_data.get("bit_rate") is not None:
            bit_rate = int(format_data["bit_rate"])

    decode = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(file_path),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    return {
        "duration_seconds": duration_seconds,
        "bit_rate": bit_rate,
        "decode_ok": decode.returncode == 0,
        "probe_ok": probe.returncode == 0,
        "probe_error": probe.stderr.strip() or None,
        "decode_error": decode.stderr.strip() or None,
    }
