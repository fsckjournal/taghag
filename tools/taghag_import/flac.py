from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


JUNK_DIRS = frozenset({"__MACOSX", ".Trashes", ".Spotlight-V100", ".fseventsd"})


def discover_flacs(source: str | Path) -> list[Path]:
    path = Path(source).expanduser().resolve()
    if path.is_file():
        if path.suffix.casefold() != ".flac" or path.name.startswith("._"):
            raise ValueError(f"source file is not a FLAC: {path}")
        return [path]
    if not path.is_dir():
        raise ValueError(f"source does not exist: {path}")
    return [
        item.resolve()
        for item in sorted(path.rglob("*"))
        if item.is_file()
        and item.suffix.casefold() == ".flac"
        and not item.name.startswith("._")
        and not any(part in JUNK_DIRS for part in item.parts)
    ]


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pcm_sha256(path: str | Path) -> str:
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(Path(path).resolve()),
            "-map",
            "0:a:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None:
        raise RuntimeError("ffmpeg PCM stdout was unavailable")
    digest = sha256()
    for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
        digest.update(chunk)
    returncode = process.wait()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    if returncode != 0:
        raise RuntimeError(f"ffmpeg PCM decode failed: {stderr.strip()}")
    return digest.hexdigest()


def probe_flac(path: str | Path) -> dict[str, object]:
    file_path = Path(path).resolve()
    integrity = subprocess.run(["flac", "-t", "-s", str(file_path)], capture_output=True, text=True)
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,bits_per_raw_sample:format=duration",
            "-of",
            "json",
            str(file_path),
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(probe.stdout) if probe.returncode == 0 and probe.stdout.strip() else {}
    stream = (payload.get("streams") or [{}])[0]
    format_data = payload.get("format") or {}
    return {
        "valid": integrity.returncode == 0 and probe.returncode == 0 and stream.get("codec_name") == "flac",
        "duration_s": float(format_data["duration"]) if format_data.get("duration") else None,
        "sample_rate": int(stream["sample_rate"]) if stream.get("sample_rate") else None,
        "channels": int(stream["channels"]) if stream.get("channels") else None,
        "bit_depth": int(stream["bits_per_raw_sample"]) if stream.get("bits_per_raw_sample") else None,
        "error": integrity.stderr.strip() or probe.stderr.strip() or None,
    }


def extract_flac_tags(path: str | Path) -> dict[str, Any]:
    from mutagen.flac import FLAC

    try:
        audio = FLAC(Path(path))
    except Exception:
        return {}

    def first(*names: str) -> str | None:
        for name in names:
            values = audio.get(name)
            if values:
                value = str(values[0]).strip()
                if value:
                    return value
        return None

    return {
        "artist": first("artist"),
        "title": first("title"),
        "album": first("album"),
        "album_artist": first("albumartist", "album artist"),
        "label": first("label", "organization"),
        "catalog_number": first("catalognumber", "catalog number"),
        "release_date": first("date", "originaldate"),
        "genre": first("genre"),
        "subgenre": first("subgenre"),
        "bpm": first("bpm"),
        "musical_key": first("initialkey", "key"),
        "isrc": first("isrc"),
        "track_number": first("tracknumber"),
        "compilation": first("compilation"),
        "comment": first("comment", "description"),
    }
