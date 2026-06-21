from __future__ import annotations

import json
from pathlib import Path
import subprocess


def probe_flac(path: str | Path) -> dict[str, object]:
    file_path = Path(path).expanduser().resolve()
    issue_codes: list[str] = []
    duration_s = None
    bitrate_kbps = None
    codec = "unknown"
    sample_rate_hz = None
    channels = None
    probe_ok = False
    probe_error = None

    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,bit_rate",
                "-show_entries",
                "stream=codec_name,codec_type,sample_rate,channels",
                "-of",
                "json",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        probe_ok = probe.returncode == 0
        probe_error = probe.stderr.strip() or None
        if probe.returncode == 0 and probe.stdout.strip():
            payload = json.loads(probe.stdout)
            format_data = payload.get("format", {})
            streams = payload.get("streams") or []
            audio_stream = next(
                (
                    stream
                    for stream in streams
                    if isinstance(stream, dict) and stream.get("codec_type") == "audio"
                ),
                streams[0] if streams else {},
            )
            if format_data.get("duration") is not None:
                duration_s = round(float(format_data["duration"]), 3)
            else:
                issue_codes.append("duration_missing")
            if format_data.get("bit_rate") is not None:
                bitrate_kbps = max(1, round(int(format_data["bit_rate"]) / 1000))
            else:
                issue_codes.append("bitrate_missing")
            if isinstance(audio_stream, dict) and audio_stream.get("codec_name"):
                codec = str(audio_stream["codec_name"]).lower()
                if codec != "flac":
                    issue_codes.append("codec_mismatch")
                if audio_stream.get("sample_rate") is not None:
                    sample_rate_hz = int(audio_stream["sample_rate"])
                if audio_stream.get("channels") is not None:
                    channels = int(audio_stream["channels"])
        else:
            issue_codes.extend(["duration_missing", "bitrate_missing"])
    except FileNotFoundError:
        probe_error = "ffprobe not found"
        issue_codes.extend(["tool_missing_ffprobe", "duration_missing", "bitrate_missing"])
    except (json.JSONDecodeError, ValueError) as exc:
        probe_error = str(exc)
        issue_codes.extend(["duration_missing", "bitrate_missing"])

    decode_ok = None
    decode_error = None
    try:
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
        decode_ok = decode.returncode == 0
        decode_error = decode.stderr.strip() or None
        if not decode_ok:
            issue_codes.append("decode_failed")
    except FileNotFoundError:
        decode_ok = None
        decode_error = "ffmpeg not found"
        issue_codes.append("tool_missing_ffmpeg")

    if bitrate_kbps is not None and bitrate_kbps < 192:
        issue_codes.append("bitrate_low")

    return {
        "duration_s": duration_s,
        "bitrate_kbps": bitrate_kbps,
        "codec": codec,
        "sample_rate_hz": sample_rate_hz,
        "channels": channels,
        "decode_ok": decode_ok,
        "duration_ok": duration_s is not None,
        "bitrate_ok": bitrate_kbps is not None and bitrate_kbps >= 192,
        "probe_ok": probe_ok,
        "probe_error": probe_error,
        "decode_error": decode_error,
        "issue_codes": sorted(set(issue_codes)),
    }
