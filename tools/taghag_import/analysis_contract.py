from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path

from .tags import compute_file_identity


ANALYSIS_SCHEMA = "essentia-lexicon-sidecar/2"
ATTRIBUTES = ("happy", "aggressive", "relaxed", "party", "danceability")


@dataclass(frozen=True)
class AnalysisTrack:
    path: str
    file_key: str
    genres: list[dict[str, object]]
    attributes: dict[str, float]
    raw_json: dict[str, object]

    def to_row(self) -> dict[str, object]:
        return {
            "source_path": self.path,
            "file_key": self.file_key,
            "genres_json": self.genres,
            **self.attributes,
        }


@dataclass(frozen=True)
class AnalysisArtifact:
    path: Path
    schema: str
    digest_sha256: str
    model_profile: str | None
    models: dict[str, object]
    tracks: list[AnalysisTrack]


def _read_json_with_digest(path: Path) -> tuple[dict[str, object], str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("analysis sidecar must be a JSON object")
    return payload, sha256(raw).hexdigest()


def _attribute(track_path: str, attributes: dict[str, object], name: str) -> float:
    value = attributes.get(name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{track_path}: missing numeric attribute {name}")
    number = float(value)
    if not math.isfinite(number) or number < 0 or number > 1:
        raise ValueError(f"{track_path}: attribute {name} must be between 0 and 1")
    return number


def _genres(track_path: str, value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{track_path}: genres must be a list")
    genres: list[dict[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{track_path}: genre {index} must be an object")
        label = item.get("label")
        confidence = item.get("confidence")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"{track_path}: genre {index} is missing label")
        if not isinstance(confidence, int | float) or isinstance(confidence, bool):
            raise ValueError(f"{track_path}: genre {index} is missing confidence")
        confidence_value = float(confidence)
        if not math.isfinite(confidence_value) or confidence_value < 0 or confidence_value > 1:
            raise ValueError(f"{track_path}: genre {index} confidence must be between 0 and 1")
        genres.append({"label": label, "confidence": confidence_value})
    return genres


def load_analysis_sidecar(path: str | Path) -> AnalysisArtifact:
    sidecar_path = Path(path).expanduser().resolve()
    payload, digest = _read_json_with_digest(sidecar_path)

    schema = payload.get("schema")
    if schema != ANALYSIS_SCHEMA:
        raise ValueError(f"unsupported analysis schema: {schema!r}")

    raw_tracks = payload.get("tracks")
    if not isinstance(raw_tracks, dict):
        raise ValueError("analysis sidecar tracks must be an object")

    tracks: list[AnalysisTrack] = []
    for track_path, raw_track in sorted(raw_tracks.items()):
        if not isinstance(track_path, str) or not isinstance(raw_track, dict):
            raise ValueError("analysis sidecar track entries must map path strings to objects")
        file_key = raw_track.get("file_key")
        if not isinstance(file_key, str) or not file_key.strip():
            local_path = Path(track_path).expanduser()
            if local_path.suffix.casefold() != ".mp3" or not local_path.is_file():
                raise ValueError(f"{track_path}: file_key is required when the local MP3 is unavailable")
            file_key = str(compute_file_identity(local_path, local_path.name)["file_key"])
        raw_attributes = raw_track.get("attributes")
        if not isinstance(raw_attributes, dict):
            raise ValueError(f"{track_path}: attributes must be an object")
        attributes = {name: _attribute(track_path, raw_attributes, name) for name in ATTRIBUTES}
        tracks.append(
            AnalysisTrack(
                path=track_path,
                file_key=file_key,
                genres=_genres(track_path, raw_track.get("genres", [])),
                attributes=attributes,
                raw_json=dict(raw_track),
            )
        )

    models = payload.get("models", {})
    if not isinstance(models, dict):
        raise ValueError("analysis sidecar models must be an object")
    model_profile = payload.get("model_profile")

    return AnalysisArtifact(
        path=sidecar_path,
        schema=ANALYSIS_SCHEMA,
        digest_sha256=digest,
        model_profile=str(model_profile) if model_profile is not None else None,
        models=dict(models),
        tracks=tracks,
    )
