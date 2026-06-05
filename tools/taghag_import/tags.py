from __future__ import annotations

from hashlib import sha1
from pathlib import Path
from typing import Any


ID3_TO_FIELD = {
    "TIT2": "title",
    "TPE1": "artist",
    "TALB": "album",
    "TCON": "genre",
    "TBPM": "bpm",
    "TKEY": "musical_key",
    "TYER": "year",
    "TDRC": "year",
    "TRCK": "track_number",
    "TCOM": "composer",
    "COMM": "comment",
}


def _first_text(frame: Any) -> str | None:
    text = getattr(frame, "text", None)
    if isinstance(text, list) and text:
        value = str(text[0]).strip()
        return value or None
    if text:
        value = str(text).strip()
        return value or None
    if hasattr(frame, "text"):
        value = str(frame.text).strip()
        return value or None
    return None


def _load_id3(path: Path) -> dict[str, Any]:
    from mutagen.id3 import ID3

    try:
        tags = ID3(path)
    except Exception:
        return {}

    return tags


def extract_mp3_tags(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    stat = file_path.stat()
    id3_tags = _load_id3(file_path)

    normalized: dict[str, Any] = {
        "file_name": file_path.name,
        "relative_path_hint": file_path.name,
        "file_size_bytes": stat.st_size,
        "modified_at_epoch": int(stat.st_mtime),
        "library_fingerprint": sha1(
            f"{file_path}:{stat.st_size}:{int(stat.st_mtime)}".encode("utf-8")
        ).hexdigest(),
        "title": None,
        "artist": None,
        "album": None,
        "genre": None,
        "bpm": None,
        "musical_key": None,
        "year": None,
        "track_number": None,
        "composer": None,
        "comment": None,
        "raw_id3": {},
    }

    for frame_id, field_name in ID3_TO_FIELD.items():
        frame = id3_tags.get(frame_id)
        if frame is None:
            continue
        value = _first_text(frame)
        if value is not None:
            normalized[field_name] = value

    normalized["raw_id3"] = {
        key: _first_text(value)
        for key, value in id3_tags.items()
        if _first_text(value) is not None
    }

    return normalized
