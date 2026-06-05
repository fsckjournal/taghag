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
    ) -> None:
        query = ""
        if on_conflict:
            query = "?" + parse.urlencode({"on_conflict": on_conflict})

        url = f"{self._config.supabase_url}/rest/v1/{table}{query}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "apikey": self._config.service_role_key,
                "Authorization": f"Bearer {self._config.service_role_key}",
                "Prefer": "resolution=merge-duplicates,return=minimal",
                "Accept-Profile": self._config.schema,
                "Content-Profile": self._config.schema,
            },
        )

        try:
            with request.urlopen(req) as response:
                if response.status >= 300:
                    raise RuntimeError(f"upload failed with status {response.status}")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"upload failed: {exc.code} {detail}") from exc

    def upsert_import_run(self, import_run: dict[str, object]) -> None:
        self._postgrest_request("import_run", [import_run], on_conflict="id")

    def upsert_tracks(self, tracks: list[dict[str, object]]) -> None:
        if not tracks:
            return
        self._postgrest_request("mp3_track", tracks, on_conflict="owner_user_id,library_fingerprint")
