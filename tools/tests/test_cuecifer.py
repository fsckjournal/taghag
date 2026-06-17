from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import cuecifer.crates as crates
import cuecifer.human_correction as human_correction
import cuecifer.map as cuecifer_map
import cuecifer.sonic_discovery as sonic_discovery
import cuecifer.sync_vibes as sync_vibes
import pytest
from taghag_import.config import DatabaseConfig


class _DummyCursor:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.executemany_calls: list[tuple[str, list[tuple[object, ...]]]] = []

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed.append((sql, params))

    def executemany(self, sql: str, params) -> None:
        self.executemany_calls.append((sql, list(params)))

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows


class _DummyCursorContext:
    def __init__(self, cursor: _DummyCursor) -> None:
        self.cursor = cursor

    def __enter__(self) -> _DummyCursor:
        return self.cursor

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _DummyConnection:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


@contextmanager
def _dummy_database(_config):
    yield _DummyConnection()


def _build_index(*, raw_json: dict[str, object] | None = None) -> sonic_discovery.SonicDiscoveryIndex:
    track = sonic_discovery.TrackRecord(
        owner_user_id="owner",
        audio_file_id="track-1",
        path="/music/track-1.mp3",
        analysis_id="analysis-1",
        analysis_computed_at=datetime.now(timezone.utc),
        happy=0.4,
        aggressive=0.1,
        relaxed=0.3,
        party=0.9,
        danceability=0.95,
        bpm=128.0,
        energy=7.5,
        raw_json=raw_json
        or {
            "segments": [
                {"attributes": {"happy": 0.0, "aggressive": 0.0}},
                {"attributes": {"happy": 0.5, "aggressive": 0.5}},
            ]
        },
    )
    config = DatabaseConfig(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role",
        database_url="postgresql://example",
        owner_user_id="owner",
    )
    return sonic_discovery.SonicDiscoveryIndex(config=config, tracks=[track])


def test_sonic_discovery_producer_vibes_vector_and_evolution() -> None:
    index = _build_index()

    vibe_names = [vibe.name for vibe in index.producer_vibes_for("/music/track-1.mp3")]
    assert vibe_names == ["peak_time_house", "warm_dancefloor"]

    vector = index.sonic_vector_for("/music/track-1.mp3")
    assert len(vector) == 7
    assert sum(value * value for value in vector) == pytest.approx(1.0)

    assert index.dynamic_evolution_for("/music/track-1.mp3") is True
    assert index.evolution_delta_for("/music/track-1.mp3") == pytest.approx(0.7071067811865476)


def test_sonic_discovery_recompute_all_upserts(monkeypatch) -> None:
    index = _build_index()
    cursor = _DummyCursor()

    monkeypatch.setattr(sonic_discovery, "open_database", _dummy_database)
    monkeypatch.setattr(sonic_discovery, "dict_cursor", lambda conn: _DummyCursorContext(cursor))
    monkeypatch.setattr(sonic_discovery, "Json", lambda value: value)

    inserted = index.recompute_all()

    assert inserted == 1
    assert cursor.executemany_calls, "expected a bulk upsert"
    sql, params = cursor.executemany_calls[0]
    assert "on conflict (owner_user_id, audio_file_id, vector_schema)" in sql
    assert params[0][0] == "owner"
    assert params[0][1] == "track-1"
    assert params[0][2] == sonic_discovery.VECTOR_SCHEMA
    assert params[0][4] == ["peak_time_house", "warm_dancefloor"]


def test_sonic_discovery_similar_tracks_queries_postgres(monkeypatch) -> None:
    index = _build_index()
    cursor = _DummyCursor(
        rows=[
            {
                "path": "/music/track-2.mp3",
                "embedding_text": "[0.1,0.2,0.3,0.4,0.5,0.6,0.7]",
                "distance": 0.125,
            }
        ]
    )

    monkeypatch.setattr(sonic_discovery, "open_database", _dummy_database)
    monkeypatch.setattr(sonic_discovery, "dict_cursor", lambda conn: _DummyCursorContext(cursor))

    results = index.similar_tracks("/music/track-1.mp3", limit=5)

    assert len(results) == 1
    assert results[0].path == "/music/track-2.mp3"
    assert results[0].distance == 0.125
    assert cursor.executed, "expected a SQL query"
    sql, params = cursor.executed[0]
    assert "order by te.embedding <=> (%s::extensions.vector)" in sql.lower()
    assert params[1] == "owner"
    assert params[2] == sonic_discovery.VECTOR_SCHEMA


def test_generate_neighborhood_crate_writes_playlist(tmp_path: Path, monkeypatch) -> None:
    class FakeIndex:
        def __init__(self, config) -> None:
            self.config = config

        def similar_tracks(self, seed_path: str, limit: int = 30):
            assert seed_path == "/music/track-1.mp3"
            assert limit == 2
            return [
                sonic_discovery.SimilarTrack(
                    path="/music/track-2.mp3",
                    distance=0.1234,
                    producer_vibes=["peak_time_house"],
                    sonic_vector=[0.0] * 7,
                )
            ]

    monkeypatch.setattr(crates, "SonicDiscoveryIndex", FakeIndex)
    monkeypatch.setattr(crates, "read_database_config", lambda: DatabaseConfig(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role",
        database_url="postgresql://example",
        owner_user_id="owner",
    ))
    output = crates.generate_neighborhood_crate("/music/track-1.mp3", limit=2, out_dir=tmp_path)

    assert output.exists()
    contents = output.read_text(encoding="utf-8")
    assert "#EXTM3U" in contents
    assert "# Seed: /music/track-1.mp3" in contents
    assert "/music/track-2.mp3" in contents


def test_generate_map_writes_json_and_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        cuecifer_map,
        "_load_rows",
        lambda: [
            {
                "path": "/music/track-1.mp3",
                "embedding_text": "[0.2,0.1,0.3,0.4,0.5,0.6,0.7]",
                "producer_vibes_json": ["peak_time_house"],
                "artist": "Artist",
                "title": "Title",
            },
            {
                "path": "/music/track-2.mp3",
                "embedding_text": "[0.4,0.3,0.2,0.1,0.0,0.1,0.2]",
                "producer_vibes_json": [],
                "artist": None,
                "title": None,
            },
        ],
    )

    json_out, csv_out = cuecifer_map.generate_map(tmp_path)

    assert json_out.exists()
    assert csv_out.exists()
    records = json.loads(json_out.read_text(encoding="utf-8"))
    assert len(records) == 2
    assert all("x" in record and "y" in record for record in records)
    assert records[0]["vibe"] == "peak_time_house"


def test_sync_vibes_to_file_rewrites_existing_comment(tmp_path: Path, monkeypatch) -> None:
    class FakeFrame:
        def __init__(self, text: str) -> None:
            self.desc = ""
            self.text = [text]

    class FakeAudio:
        def __init__(self) -> None:
            self.frames = [FakeFrame("prefix [TS: old_vibe] suffix")]
            self.saved = False

        def getall(self, kind: str):
            return self.frames

        def add(self, frame) -> None:
            self.frames.append(frame)

        def save(self, path, v2_version: int) -> None:
            self.saved = True

    fake_audio = FakeAudio()
    mp3_path = tmp_path / "track.mp3"
    mp3_path.write_bytes(b"")

    monkeypatch.setattr(sync_vibes, "ID3", lambda path=None: fake_audio)

    changed = sync_vibes.sync_vibes_to_file(mp3_path, ["peak_time_house", "warm_dancefloor"], dry_run=False)

    assert changed is True
    assert fake_audio.saved is True
    assert "peak_time_house | warm_dancefloor" in fake_audio.frames[0].text[0]


def test_apply_corrections_upserts_track_curation(tmp_path: Path, monkeypatch) -> None:
    class FakeFrame:
        def __init__(self, text: str) -> None:
            self.text = [text]

    class FakeAudio:
        def __init__(self) -> None:
            self.frames = [FakeFrame("[TS: peak_time_house | warm_dancefloor]")]

        def getall(self, kind: str):
            return self.frames

    cursor = _DummyCursor()
    mp3_path = tmp_path / "track.mp3"
    mp3_path.write_bytes(b"")

    monkeypatch.setattr(human_correction, "read_database_config", lambda: DatabaseConfig(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role",
        database_url="postgresql://example",
        owner_user_id="owner",
    ))
    monkeypatch.setattr(human_correction, "_load_files", lambda: [
        {
            "audio_file_id": "track-1",
            "path": str(mp3_path),
            "producer_vibes_json": ["peak_time_house"],
            "human_vibes_json": [],
            "pinned": False,
        }
    ])
    monkeypatch.setattr(human_correction, "open_database", _dummy_database)
    monkeypatch.setattr(human_correction, "dict_cursor", lambda conn: _DummyCursorContext(cursor))
    monkeypatch.setattr(human_correction, "ID3", lambda path=None: FakeAudio())

    changed = human_correction.apply_corrections(music_dir=tmp_path, execute=True)

    assert changed == 1
    assert cursor.executed, "expected a track_curation upsert"
    sql, params = cursor.executed[0]
    assert "insert into public.track_curation" in sql.lower()
    assert params[0] == "owner"
    assert params[1] == "track-1"
    assert json.loads(params[2]) == ["peak_time_house", "warm_dancefloor"]
