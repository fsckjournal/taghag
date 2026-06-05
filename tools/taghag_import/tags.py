from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any


ID3_TO_FIELD = {
    "TIT2": "title",
    "TPE1": "artist",
    "TALB": "album",
    "TPUB": "label",
    "TPE2": "album_artist",
    "TCAT": "catalog_number",
    "TCON": "genre",
    "TXXX:SUBGENRE": "subgenre",
    "TBPM": "bpm",
    "TKEY": "musical_key",
    "TYER": "year",
    "TDRC": "year",
    "TDOR": "release_date",
    "TSRC": "isrc",
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
    id3_tags = _load_id3(file_path)

    normalized: dict[str, Any] = {
        "title": None,
        "artist": None,
        "album": None,
        "label": None,
        "catalog_number": None,
        "release_date": None,
        "genre": None,
        "subgenre": None,
        "bpm": None,
        "musical_key": None,
        "year": None,
        "isrc": None,
        "compilation": None,
        "rating": None,
        "energy": None,
        "track_number": None,
        "composer": None,
        "comment": None,
        "raw_id3": {},
    }

    for frame_id, field_name in ID3_TO_FIELD.items():
        frame = id3_tags.get(frame_id)
        if frame is None and frame_id.startswith("TXXX:"):
            wanted_desc = frame_id.split(":", 1)[1].casefold()
            for candidate in id3_tags.values():
                if getattr(candidate, "FrameID", "") == "TXXX" and str(
                    getattr(candidate, "desc", "")
                ).casefold() == wanted_desc:
                    frame = candidate
                    break
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


def compute_file_identity(path: str | Path, relative_path: str) -> dict[str, object]:
    file_path = Path(path).expanduser().resolve()
    stat = file_path.stat()
    try:
        digest = sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        checksum = digest.hexdigest()
        return {
            "file_key": f"sha256:{checksum}",
            "checksum_sha256": checksum,
            "checksum_prefix": checksum[:24],
            "identity_source": "checksum_sha256",
            "identity_confidence": 1.0,
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "issue_codes": [],
        }
    except OSError:
        path_hash = sha256(str(relative_path).encode("utf-8")).hexdigest()[:24]
        return {
            "file_key": f"stat:{stat.st_size}:{stat.st_mtime_ns}:{path_hash}",
            "checksum_sha256": None,
            "checksum_prefix": None,
            "identity_source": "stat_fallback",
            "identity_confidence": 0.4,
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "issue_codes": ["checksum_failed"],
        }
