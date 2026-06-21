from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping

from .provider_runner import normalize_isrc


# Vorbis comment key for each writable field (lowercase; mutagen is case-insensitive).
FIELD_TO_VORBIS_KEY: dict[str, str] = {
    "title": "title",
    "artist": "artist",
    "album": "album",
    "album_artist": "albumartist",
    "label": "label",
    "catalog_number": "catalognumber",
    "release_date": "date",
    "genre": "genre",
    "subgenre": "subgenre",
    "bpm": "bpm",
    "musical_key": "initialkey",
    "year": "year",
    "isrc": "isrc",
    "track_number": "tracknumber",
    "compilation": "compilation",
    "composer": "composer",
    "rating": "rating",
    "energy": "energy",
    "pcm_hash": "pcm_hash",
    "spotify_id": "spotify_id",
    "beatport_album_id": "beatport_album_id",
    "beatport_track_id": "beatport_track_id",
}

FIELD_ALIASES = {
    "catalog": "catalog_number",
    "date": "release_date",
    "key": "musical_key",
}

WRITABLE_FIELDS = frozenset(FIELD_TO_VORBIS_KEY)


@dataclass(frozen=True)
class TagWriteResult:
    path: str
    planned_fields: list[str]
    applied_fields: list[str]
    skipped_fields: list[str]
    executed: bool


def _year_from_value(value: object) -> str | None:
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return match.group(0) if match else None


def extract_flac_tags(path: str | Path) -> dict[str, Any]:
    from mutagen import MutagenError
    from mutagen.flac import FLAC

    file_path = Path(path).expanduser().resolve()
    try:
        audio = FLAC(file_path)
    except (MutagenError, OSError):
        return {}

    def first(*names: str) -> str | None:
        for name in names:
            values = audio.get(name)
            if values:
                value = str(values[0]).strip()
                if value:
                    return value
        return None

    result: dict[str, Any] = {
        "title": first("title"),
        "artist": first("artist"),
        "album": first("album"),
        "album_artist": first("albumartist", "album artist"),
        "label": first("label", "organization"),
        "catalog_number": first("catalognumber", "catalog number"),
        "release_date": first("date", "originaldate"),
        "genre": first("genre"),
        "subgenre": first("subgenre"),
        "bpm": first("bpm"),
        "musical_key": first("initialkey", "key"),
        "year": first("year"),
        "isrc": first("isrc"),
        "track_number": first("tracknumber"),
        "compilation": first("compilation"),
        "composer": first("composer"),
        "comment": first("comment", "description"),
        "rating": first("rating"),
        "energy": first("energy"),
        "pcm_hash": first("pcm_hash"),
        "spotify_id": first("spotify_id"),
        "beatport_album_id": first("beatport_album_id"),
        "beatport_track_id": first("beatport_track_id"),
        "raw_tags": {},
    }

    if audio.tags is not None:
        result["raw_tags"] = {
            k: [str(v) for v in vals]
            for k, vals in audio.tags.as_dict().items()
        }

    if result["year"]:
        if not result["release_date"]:
            result["release_date"] = result["year"]
        result["year"] = _year_from_value(result["year"])
    elif result["release_date"]:
        result["year"] = _year_from_value(result["release_date"])

    return result


def dump_flac_tags(
    path: str | Path,
    *,
    max_value_len: int = 2000,
) -> dict[str, list[str]]:
    from mutagen import MutagenError
    from mutagen.flac import FLAC

    file_path = Path(path).expanduser().resolve()
    try:
        audio = FLAC(file_path)
    except (MutagenError, OSError):
        return {}

    dumped: dict[str, list[str]] = {}

    if audio.tags is not None:
        for key, vals in sorted(audio.tags.as_dict().items()):
            dumped[key] = [str(v)[:max_value_len] for v in vals]

    for i, pic in enumerate(audio.pictures):
        label = pic.desc or str(i)
        dumped[f"PICTURE:{label}"] = [f"<binary:{len(pic.data)} bytes>"]

    return dumped


def _normalize_updates(updates: Mapping[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_field, raw_value in updates.items():
        field = FIELD_ALIASES.get(str(raw_field).strip().lower(), str(raw_field).strip().lower())
        if field not in WRITABLE_FIELDS:
            raise ValueError(f"unsupported FLAC tag field: {raw_field}")
        value = str(raw_value or "").strip()
        if not value:
            continue
        if field == "isrc":
            # Every track is tagged at acquisition with exactly one valid
            # ISRC, so the tagger never writes a semicolon-joined or
            # otherwise malformed value -- there's no legitimate multi-ISRC
            # case left to support.
            value = normalize_isrc(value)
        normalized[field] = value
    return normalized


def _field_has_value(audio: Any, field: str) -> bool:
    vorbis_key = FIELD_TO_VORBIS_KEY[field]
    vals = audio.get(vorbis_key)
    if vals and str(vals[0]).strip():
        return True
    # album_artist has a secondary lookup key
    if field == "album_artist":
        vals2 = audio.get("album artist")
        return bool(vals2 and str(vals2[0]).strip())
    return False


def _set_field(audio: Any, field: str, value: str) -> None:
    vorbis_key = FIELD_TO_VORBIS_KEY[field]
    audio[vorbis_key] = [value]


def apply_flac_tag_updates(
    path: str | Path,
    updates: Mapping[str, object],
    *,
    execute: bool = False,
    force: bool = False,
) -> TagWriteResult:
    from mutagen.flac import FLAC

    file_path = Path(path).expanduser().resolve()
    if file_path.suffix.lower() != ".flac":
        raise ValueError(f"not a FLAC file: {file_path}")
    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    audio = FLAC(file_path)
    if audio.tags is None:
        audio.add_tags()

    normalized = _normalize_updates(updates)
    planned: list[str] = []
    skipped: list[str] = []
    for field in sorted(normalized):
        if not force and _field_has_value(audio, field):
            skipped.append(field)
        else:
            planned.append(field)

    applied: list[str] = []
    if execute and planned:
        for field in planned:
            _set_field(audio, field, normalized[field])
            applied.append(field)
        audio.save()

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
