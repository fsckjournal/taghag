from __future__ import annotations

import json

from taghag_import.config import DatabaseConfig
from taghag_import.db_client import TaghagDbClient


class FakeResponse:
    status = 201

    def __init__(self, body: object | None = None) -> None:
        self._body = json.dumps(body or []).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_upload_receipt_events_uses_canonical_tables(monkeypatch) -> None:
    calls: list[tuple[str, list[dict[str, object]], str]] = []

    def fake_urlopen(req):
        payload = json.loads(req.data.decode("utf-8"))
        calls.append((req.full_url, payload, req.headers["Prefer"]))
        if "/mp3_file" in req.full_url:
            return FakeResponse([{"id": "file-id", "file_key": "sha256:abc"}])
        return FakeResponse([])

    monkeypatch.setattr("taghag_import.db_client.request.urlopen", fake_urlopen)
    client = TaghagDbClient(
        DatabaseConfig(
            supabase_url="https://example.supabase.co",
            service_role_key="service-key",
            owner_user_id="00000000-0000-0000-0000-000000000001",
        )
    )
    records = [
        {
            "event_type": "import_run_start",
            "import_run": {"id": "run-id", "status": "running"},
        },
        {
            "event_type": "mp3_observed",
            "mp3_file": {"file_key": "sha256:abc", "path": "/x.mp3", "filename": "x.mp3"},
            "mp3_observation": {"import_run_id": "run-id", "observed_path": "/x.mp3", "status": "observed"},
            "dj_tag": {"artist": "A", "title": "T"},
        },
        {
            "event_type": "quality_check",
            "file_key": "sha256:abc",
            "quality_check": {"import_run_id": "run-id", "issue_codes_json": []},
        },
        {
            "event_type": "tag_evidence",
            "file_key": "sha256:abc",
            "tag_evidence": {
                "provider": "beatport",
                "lookup_type": "isrc",
                "lookup_key": "USABC2400001",
                "status": "matched",
            },
        },
    ]

    result = client.upload_receipt_events(records)

    urls = [call[0] for call in calls]
    assert any("/import_run?on_conflict=id" in url for url in urls)
    assert any("/mp3_file?on_conflict=owner_user_id%2Cfile_key" in url for url in urls)
    assert any("/mp3_observation" in url for url in urls)
    assert any("/dj_tag?on_conflict=owner_user_id%2Cmp3_file_id" in url for url in urls)
    assert any("/quality_check" in url for url in urls)
    assert any("/tag_evidence" in url for url in urls)
    assert any("return=representation" in call[2] for call in calls)
    assert result["mp3_observation"] == 1

