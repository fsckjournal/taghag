from __future__ import annotations

from datetime import UTC, datetime
import uuid

from .analysis_contract import load_analysis_sidecar
from .receipt import event


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_analysis_import_records(sidecar_path: str) -> list[dict[str, object]]:
    artifact = load_analysis_sidecar(sidecar_path)
    run_id = str(uuid.uuid4())
    records: list[dict[str, object]] = [
        event(
            "analysis_import_start",
            run_id=run_id,
            source_artifact=str(artifact.path),
            source_artifact_sha256=artifact.digest_sha256,
            schema_name=artifact.schema,
            model_profile=artifact.model_profile,
            models_json=artifact.models,
            started_at=_now(),
        )
    ]

    for track in artifact.tracks:
        row = {
            "schema_name": artifact.schema,
            "model_profile": artifact.model_profile,
            "models_json": artifact.models,
            "source_artifact_sha256": artifact.digest_sha256,
            "source_path": track.path,
            "genres_json": track.genres,
            "raw_json": track.raw_json,
            **track.attributes,
            "computed_at": _now(),
        }
        records.append(event("track_analysis", run_id=run_id, file_key=track.file_key, track_analysis=row))

    records.append(
        event(
            "analysis_import_summary",
            run_id=run_id,
            summary={"track_analysis": len(artifact.tracks), "source_artifact_sha256": artifact.digest_sha256},
        )
    )
    return records
