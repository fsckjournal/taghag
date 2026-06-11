from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping


ID3_TO_FIELD = {
    "TIT2": "title",
    "TPE1": "artist",
    "TALB": "album",
    "TPUB": "label",
    "TXXX:LABEL": "label",
    "TPE2": "album_artist",
    "TXXX:CATALOGNUMBER": "catalog_number",
    "TCON": "genre",
    "TXXX:SUBGENRE": "subgenre",
    "TBPM": "bpm",
    "TKEY": "musical_key",
    "TXXX:INITIALKEY": "musical_key",
    "TYER": "year",
    "TDRC": "year",
    "TDOR": "release_date",
    "TSRC": "isrc",
    "TRCK": "track_number",
    "TCOM": "composer",
    "COMM": "comment",
    "TXXX:COMPILATION": "compilation",
    "TXXX:RATING": "rating",
    "TXXX:ENERGY": "energy",
    "TXXX:PCM_HASH": "pcm_hash",
    "TXXX:SPOTIFY_ID": "spotify_id",
    "TXXX:BEATPORT_ALBUM_ID": "beatport_album_id",
    "TXXX:BEATPORT_TRACK_ID": "beatport_track_id",
}

FIELD_ALIASES = {
    "catalog": "catalog_number",
    "date": "release_date",
    "key": "musical_key",
}

WRITABLE_FIELDS = frozenset(
    {
        "album",
        "album_artist",
        "artist",
        "bpm",
        "catalog_number",
        "compilation",
        "composer",
        "energy",
        "genre",
        "isrc",
        "label",
        "musical_key",
        "pcm_hash",
        "rating",
        "release_date",
        "subgenre",
        "title",
        "track_number",
        "year",
        "spotify_id",
        "beatport_album_id",
        "beatport_track_id",
    }
)


@dataclass(frozen=True)
class TagWriteResult:
    path: str
    planned_fields: list[str]
    applied_fields: list[str]
    skipped_fields: list[str]
    executed: bool


def _first_text(frame: Any) -> str | None:
    text = getattr(frame, "text", None)
    if isinstance(text, (list, tuple)) and text:
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
    from mutagen import MutagenError
    from mutagen.id3 import ID3, ID3NoHeaderError

    try:
        tags = ID3(path)
    except (ID3NoHeaderError, MutagenError):
        return {}

    return tags


def _year_from_value(value: object) -> str | None:
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return match.group(0) if match else None


def _find_frame(id3_tags: Mapping[str, Any], frame_id: str) -> Any | None:
    frame = id3_tags.get(frame_id)
    if frame is not None:
        return frame

    if frame_id.startswith("TXXX:"):
        wanted_desc = frame_id.split(":", 1)[1].casefold()
        for candidate in id3_tags.values():
            if getattr(candidate, "FrameID", "") == "TXXX" and str(
                getattr(candidate, "desc", "")
            ).casefold() == wanted_desc:
                return candidate

    if frame_id == "COMM":
        for candidate in id3_tags.values():
            if getattr(candidate, "FrameID", "") == "COMM":
                return candidate
    return None


def extract_mp3_tags(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    id3_tags = _load_id3(file_path)

    normalized: dict[str, Any] = {
        "title": None,
        "artist": None,
        "album": None,
        "album_artist": None,
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
        "pcm_hash": None,
        "track_number": None,
        "composer": None,
        "comment": None,
        "spotify_id": None,
        "beatport_album_id": None,
        "beatport_track_id": None,
        "raw_id3": {},
    }

    for frame_id, field_name in ID3_TO_FIELD.items():
        frame = _find_frame(id3_tags, frame_id)
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
    if normalized["year"]:
        if not normalized["release_date"]:
            normalized["release_date"] = normalized["year"]
        normalized["year"] = _year_from_value(normalized["year"])
    elif normalized["release_date"]:
        normalized["year"] = _year_from_value(normalized["release_date"])

    return normalized


def _safe_frame_values(frame: Any, max_value_len: int) -> list[str]:
    data = getattr(frame, "data", None)
    if isinstance(data, (bytes, bytearray)):
        return [f"<binary:{len(data)} bytes>"]

    text = getattr(frame, "text", None)
    if isinstance(text, (list, tuple)):
        return [str(value)[:max_value_len] for value in text if str(value)]
    if text not in (None, ""):
        return [str(text)[:max_value_len]]

    for attribute in ("url", "rating", "count", "owner"):
        value = getattr(frame, attribute, None)
        if value not in (None, ""):
            return [str(value)[:max_value_len]]

    rendered = str(frame).strip()
    return [rendered[:max_value_len]] if rendered else []


def dump_mp3_tags(
    path: str | Path,
    *,
    max_value_len: int = 2000,
) -> dict[str, list[str]]:
    file_path = Path(path).expanduser().resolve()
    tags = _load_id3(file_path)
    dumped: dict[str, list[str]] = {}
    for key, frame in sorted(tags.items(), key=lambda item: str(item[0])):
        values = _safe_frame_values(frame, max_value_len)
        if values:
            dumped[str(key)] = values
    return dumped


def _normalize_updates(updates: Mapping[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_field, raw_value in updates.items():
        field = FIELD_ALIASES.get(str(raw_field).strip().lower(), str(raw_field).strip().lower())
        if field not in WRITABLE_FIELDS:
            raise ValueError(f"unsupported MP3 tag field: {raw_field}")
        value = str(raw_value or "").strip()
        if value:
            normalized[field] = value
    return normalized


def _txxx_value(tags: Any, description: str) -> str:
    wanted = description.casefold()
    for frame in tags.getall("TXXX"):
        if str(getattr(frame, "desc", "")).casefold() != wanted:
            continue
        return _first_text(frame) or ""
    return ""


def _frame_value(tags: Any, frame_id: str) -> str:
    return _first_text(tags.get(frame_id)) or ""


def _field_has_value(tags: Any, field: str) -> bool:
    if field == "label":
        return bool(_frame_value(tags, "TPUB") or _txxx_value(tags, "LABEL"))
    if field == "catalog_number":
        return bool(_txxx_value(tags, "CATALOGNUMBER"))
    if field == "subgenre":
        return bool(_txxx_value(tags, "SUBGENRE"))
    if field == "musical_key":
        return bool(_frame_value(tags, "TKEY") or _txxx_value(tags, "INITIALKEY"))
    if field in {"compilation", "rating", "energy", "pcm_hash", "spotify_id", "beatport_album_id", "beatport_track_id"}:
        return bool(_txxx_value(tags, field.upper()))

    frame_by_field = {
        "title": "TIT2",
        "artist": "TPE1",
        "album": "TALB",
        "album_artist": "TPE2",
        "release_date": "TDRC",
        "year": "TDRC",
        "genre": "TCON",
        "bpm": "TBPM",
        "isrc": "TSRC",
        "track_number": "TRCK",
        "composer": "TCOM",
    }
    return bool(_frame_value(tags, frame_by_field[field]))


def _replace_txxx(tags: Any, description: str, value: str) -> None:
    from mutagen.id3 import TXXX

    wanted = description.casefold()
    kept = [
        frame
        for frame in tags.getall("TXXX")
        if str(getattr(frame, "desc", "")).casefold() != wanted
    ]
    tags.setall("TXXX", kept)
    tags.add(TXXX(encoding=3, desc=description, text=[value]))


def _set_field(tags: Any, field: str, value: str) -> None:
    from mutagen.id3 import (
        TALB,
        TBPM,
        TCOM,
        TCON,
        TDRC,
        TIT2,
        TKEY,
        TPE1,
        TPE2,
        TPUB,
        TRCK,
        TSRC,
    )

    text_frames = {
        "title": ("TIT2", TIT2),
        "artist": ("TPE1", TPE1),
        "album": ("TALB", TALB),
        "album_artist": ("TPE2", TPE2),
        "release_date": ("TDRC", TDRC),
        "year": ("TDRC", TDRC),
        "genre": ("TCON", TCON),
        "bpm": ("TBPM", TBPM),
        "isrc": ("TSRC", TSRC),
        "track_number": ("TRCK", TRCK),
        "composer": ("TCOM", TCOM),
    }
    if field in text_frames:
        frame_id, frame_type = text_frames[field]
        tags.setall(frame_id, [frame_type(encoding=3, text=[value])])
        return
    if field == "label":
        tags.setall("TPUB", [TPUB(encoding=3, text=[value])])
        _replace_txxx(tags, "LABEL", value)
        return
    if field == "catalog_number":
        _replace_txxx(tags, "CATALOGNUMBER", value)
        return
    if field == "subgenre":
        _replace_txxx(tags, "SUBGENRE", value)
        return
    if field == "musical_key":
        tags.setall("TKEY", [TKEY(encoding=3, text=[value])])
        _replace_txxx(tags, "INITIALKEY", value)
        return
    if field in {"compilation", "rating", "energy", "pcm_hash", "spotify_id", "beatport_album_id", "beatport_track_id"}:
        _replace_txxx(tags, field.upper(), value)
        return
    raise ValueError(f"unsupported MP3 tag field: {field}")


def apply_mp3_tag_updates(
    path: str | Path,
    updates: Mapping[str, object],
    *,
    execute: bool = False,
    force: bool = False,
) -> TagWriteResult:
    from mutagen.id3 import ID3, ID3NoHeaderError

    file_path = Path(path).expanduser().resolve()
    if file_path.suffix.lower() != ".mp3":
        raise ValueError(f"not an MP3 file: {file_path}")
    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    try:
        tags = ID3(file_path)
    except ID3NoHeaderError:
        tags = ID3()

    normalized = _normalize_updates(updates)
    planned: list[str] = []
    skipped: list[str] = []
    for field in sorted(normalized):
        if not force and _field_has_value(tags, field):
            skipped.append(field)
        else:
            planned.append(field)

    applied: list[str] = []
    if execute and planned:
        for field in planned:
            _set_field(tags, field, normalized[field])
            applied.append(field)
        tags.save(file_path, v2_version=3)

    return TagWriteResult(
        path=str(file_path),
        planned_fields=planned,
        applied_fields=applied,
        skipped_fields=skipped,
        executed=execute,
    )


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
