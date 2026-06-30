from __future__ import annotations

import json
from urllib import error, parse, request

from .config import DatabaseConfig


class TaghagDbClient:
    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config

    def _postgrest_request(
        self,
        table: str,
        payload: list[dict[str, object]],
        *,
        on_conflict: str | None = None,
        return_rows: bool = False,
    ) -> list[dict[str, object]]:
        if not payload:
            return []

        query = ""
        if on_conflict:
            query = "?" + parse.urlencode({"on_conflict": on_conflict})

        url = f"{self._config.supabase_url}/rest/v1/{table}{query}"
        body = json.dumps(payload).encode("utf-8")
        prefer_return = "representation" if return_rows else "minimal"
        req = request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "apikey": self._config.secret_key,
                "Prefer": f"resolution=merge-duplicates,return={prefer_return}",
                "Accept-Profile": self._config.schema,
                "Content-Profile": self._config.schema,
            },
        )

        try:
            with request.urlopen(req) as response:
                if response.status >= 300:
                    raise RuntimeError(f"upload failed with status {response.status}")
                if not return_rows:
                    return []
                raw = response.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return []
                payload_obj = json.loads(raw)
                if isinstance(payload_obj, list):
                    return [dict(item) for item in payload_obj if isinstance(item, dict)]
                return []
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"upload failed: {exc.code} {detail}") from exc

    def _get_postgrest_rows(self, table: str, query: dict[str, str]) -> list[dict[str, object]]:
        url = f"{self._config.supabase_url}/rest/v1/{table}?" + parse.urlencode(query)
        req = request.Request(
            url,
            method="GET",
            headers={
                "apikey": self._config.secret_key,
                "Accept-Profile": self._config.schema,
            },
        )
        try:
            with request.urlopen(req) as response:
                raw = response.read().decode("utf-8", errors="replace")
                payload_obj = json.loads(raw) if raw.strip() else []
                if isinstance(payload_obj, list):
                    return [dict(item) for item in payload_obj if isinstance(item, dict)]
                return []
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"lookup failed: {exc.code} {detail}") from exc

    def upsert_import_run(self, import_run: dict[str, object]) -> None:
        self._postgrest_request("import_run", [import_run], on_conflict="id")

    def upsert_audio_files(self, files: list[dict[str, object]]) -> list[dict[str, object]]:
        return self._postgrest_request(
            "audio_file",
            files,
            on_conflict="owner_user_id,file_key",
            return_rows=True,
        )

    def insert_observations(self, observations: list[dict[str, object]]) -> None:
        self._postgrest_request("audio_observation", observations)

    def upsert_dj_tags(self, tags: list[dict[str, object]]) -> None:
        self._postgrest_request("dj_tag", tags, on_conflict="owner_user_id,audio_file_id")

    def insert_quality_checks(self, checks: list[dict[str, object]]) -> None:
        self._postgrest_request("quality_check", checks)

    def insert_tag_evidence(self, evidence_rows: list[dict[str, object]]) -> None:
        self._postgrest_request("tag_evidence", evidence_rows)

    def upsert_track_analysis(self, analysis_rows: list[dict[str, object]]) -> None:
        self._postgrest_request(
            "track_analysis",
            analysis_rows,
            on_conflict="owner_user_id,audio_file_id,schema_name,source_artifact_sha256",
        )

    def upsert_apple_track_analysis(self, analysis_rows: list[dict[str, object]]) -> None:
        self._postgrest_request(
            "apple_track_analysis",
            analysis_rows,
            on_conflict="owner_user_id,audio_file_id,source_artifact_sha256",
        )

    def upsert_apple_analysis_runs(self, run_rows: list[dict[str, object]]) -> list[dict[str, object]]:
        return self._postgrest_request(
            "apple_analysis_runs",
            run_rows,
            on_conflict="owner_user_id,audio_file_id,source_artifact_sha256",
            return_rows=True,
        )

    def upsert_apple_derived_features(self, feature_rows: list[dict[str, object]]) -> None:
        self._postgrest_request(
            "apple_derived_features",
            feature_rows,
            on_conflict="owner_user_id,audio_file_id,source_artifact_sha256",
        )

    def upsert_track_embedding(self, embedding_rows: list[dict[str, object]]) -> None:
        self._postgrest_request(
            "track_embedding",
            embedding_rows,
            on_conflict="owner_user_id,audio_file_id,vector_schema",
        )

    def upsert_track_curation(self, curation_rows: list[dict[str, object]]) -> None:
        self._postgrest_request(
            "track_curation",
            curation_rows,
            on_conflict="owner_user_id,audio_file_id",
        )

    def insert_track_cues(self, cues: list[dict[str, object]]) -> None:
        self._postgrest_request("track_cue", cues)

    def insert_track_segments(self, segments: list[dict[str, object]]) -> None:
        self._postgrest_request("track_segment", segments)

    def insert_transition_edges(self, edges: list[dict[str, object]]) -> None:
        self._postgrest_request("transition_edge", edges)

    def upsert_rendition_time_offsets(self, offsets: list[dict[str, object]]) -> None:
        self._postgrest_request(
            "rendition_time_offset",
            offsets,
            on_conflict="audio_file_id,measured_against_file_id,source_system",
        )


    def _audio_file_ids_for_file_keys(self, file_keys: set[str]) -> dict[str, str]:
        if not file_keys:
            return {}
        rows: list[dict[str, object]] = []
        sorted_keys = sorted(file_keys)
        for offset in range(0, len(sorted_keys), 50):
            quoted = ",".join(f'"{key}"' for key in sorted_keys[offset : offset + 50])
            rows.extend(
                self._get_postgrest_rows(
                    "audio_file",
                    {
                        "select": "id,file_key",
                        "owner_user_id": f"eq.{self._config.owner_user_id}",
                        "file_key": f"in.({quoted})",
                    },
                )
            )
        return {
            str(row.get("file_key")): str(row.get("id"))
            for row in rows
            if row.get("file_key") and row.get("id")
        }

    def upload_analysis_events(self, records: list[dict[str, object]]) -> dict[str, int]:
        if not self._config.owner_user_id:
            raise RuntimeError("TAGHAG_OWNER_USER_ID is required")
        owner_user_id = self._config.owner_user_id
        analysis_events = [record for record in records if record.get("event_type") == "track_analysis"]
        file_ids = self._audio_file_ids_for_file_keys({str(record.get("file_key")) for record in analysis_events})

        analysis_rows: list[dict[str, object]] = []
        unmatched = 0
        for record in analysis_events:
            file_key = str(record.get("file_key") or "")
            audio_file_id = file_ids.get(file_key)
            if not audio_file_id:
                unmatched += 1
                continue
            row = dict(record["track_analysis"])  # type: ignore[index]
            row["owner_user_id"] = owner_user_id
            row["audio_file_id"] = audio_file_id
            analysis_rows.append(row)

        self.upsert_track_analysis(analysis_rows)
        return {"track_analysis": len(analysis_rows), "unmatched": unmatched}

    def upload_receipt_events(self, records: list[dict[str, object]]) -> dict[str, int]:
        if not self._config.owner_user_id:
            raise RuntimeError("TAGHAG_OWNER_USER_ID is required")
        owner_user_id = self._config.owner_user_id

        import_run_rows: list[dict[str, object]] = []
        audio_file_rows: list[dict[str, object]] = []
        observation_events: list[dict[str, object]] = []
        dj_tag_events: list[dict[str, object]] = []
        quality_events: list[dict[str, object]] = []
        evidence_events: list[dict[str, object]] = []

        for record in records:
            event_type = record.get("event_type")
            if event_type == "import_run_start":
                row = dict(record["import_run"])  # type: ignore[index]
                row["owner_user_id"] = owner_user_id
                import_run_rows.append(row)
            elif event_type == "audio_observed":
                file_row = dict(record["audio_file"])  # type: ignore[index]
                file_row["owner_user_id"] = owner_user_id
                audio_file_rows.append(file_row)
                observation_events.append(record)
                dj_tag_events.append(record)
            elif event_type == "quality_check":
                quality_events.append(record)
            elif event_type == "tag_evidence":
                evidence_events.append(record)

        if not import_run_rows:
            raise RuntimeError("receipt is missing import_run_start event")

        self.upsert_import_run(import_run_rows[0])
        returned_files = self.upsert_audio_files(audio_file_rows)
        file_ids = {
            str(row.get("file_key")): str(row.get("id"))
            for row in returned_files
            if row.get("file_key") and row.get("id")
        }

        observations: list[dict[str, object]] = []
        dj_tags: list[dict[str, object]] = []
        for record in observation_events:
            file_key = str(dict(record["audio_file"])["file_key"])  # type: ignore[index]
            audio_file_id = file_ids.get(file_key)
            if not audio_file_id:
                continue
            observation = dict(record["audio_observation"])  # type: ignore[index]
            observation["owner_user_id"] = owner_user_id
            observation["audio_file_id"] = audio_file_id
            observations.append(observation)

            tag = dict(record["dj_tag"])  # type: ignore[index]
            tag["owner_user_id"] = owner_user_id
            tag["audio_file_id"] = audio_file_id
            dj_tags.append(tag)

        quality_checks: list[dict[str, object]] = []
        for record in quality_events:
            file_key = str(record.get("file_key") or "")
            audio_file_id = file_ids.get(file_key)
            if not audio_file_id:
                continue
            row = dict(record["quality_check"])  # type: ignore[index]
            row["owner_user_id"] = owner_user_id
            row["audio_file_id"] = audio_file_id
            quality_checks.append(row)

        evidence_rows: list[dict[str, object]] = []
        for record in evidence_events:
            file_key = str(record.get("file_key") or "")
            audio_file_id = file_ids.get(file_key)
            if not audio_file_id:
                continue
            row = dict(record["tag_evidence"])  # type: ignore[index]
            row["owner_user_id"] = owner_user_id
            row["audio_file_id"] = audio_file_id
            evidence_rows.append(row)

        self.insert_observations(observations)
        self.upsert_dj_tags(dj_tags)
        self.insert_quality_checks(quality_checks)
        self.insert_tag_evidence(evidence_rows)

        return {
            "import_run": 1,
            "audio_file": len(audio_file_rows),
            "audio_observation": len(observations),
            "dj_tag": len(dj_tags),
            "quality_check": len(quality_checks),
            "tag_evidence": len(evidence_rows),
        }

    def _delete_postgrest_rows(self, table: str, query: dict[str, str]) -> None:
        url = f"{self._config.supabase_url}/rest/v1/{table}?" + parse.urlencode(query)
        req = request.Request(
            url,
            method="DELETE",
            headers={
                "apikey": self._config.secret_key,
                "Content-Profile": self._config.schema,
            },
        )
        try:
            with request.urlopen(req) as response:
                if response.status >= 300:
                    raise RuntimeError(f"delete failed with status {response.status}")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"delete failed: {exc.code} {detail}") from exc

    def _patch_postgrest_rows(self, table: str, query: dict[str, str], payload: dict[str, object]) -> None:
        url = f"{self._config.supabase_url}/rest/v1/{table}?" + parse.urlencode(query)
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            method="PATCH",
            headers={
                "Content-Type": "application/json",
                "apikey": self._config.secret_key,
                "Content-Profile": self._config.schema,
            },
        )
        try:
            with request.urlopen(req) as response:
                if response.status >= 300:
                    raise RuntimeError(f"patch failed with status {response.status}")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"patch failed: {exc.code} {detail}") from exc
