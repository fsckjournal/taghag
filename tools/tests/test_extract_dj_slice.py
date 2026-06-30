from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from taghag_import.config import DatabaseConfig
from taghag_import.extract_dj_slice import extract_dj_slice


def _files_row(**overrides: object) -> tuple[object, ...]:
    row: dict[str, object] = {
        "path": "",
        "library": "MP3_LIBRARY",
        "zone": "accepted",
        "mtime": 0.0,
        "size": 0,
        "checksum": None,
        "streaminfo_md5": None,
        "sha256": None,
        "duration": 0.0,
        "bitrate": 0,
        "metadata_json": None,
        "canonical_title": None,
        "canonical_artist": None,
        "canonical_album": None,
        "canonical_isrc": None,
        "canonical_duration": None,
        "canonical_year": None,
        "canonical_release_date": None,
        "canonical_bpm": None,
        "canonical_key": None,
        "canonical_genre": None,
        "canonical_sub_genre": None,
        "canonical_label": None,
        "canonical_catalog_number": None,
        "canonical_mix_name": None,
        "canonical_explicit": None,
        "canonical_energy": None,
        "dj_set_role": None,
        "dj_subrole": None,
        "energy": None,
        "isrc": None,
        "fingerprint": None,
        "metadata_health_reason": None,
        "quality_rank": None,
        "duration_ref_ms": None,
        "duration_ref_source": None,
        "is_dj_material": None,
        "last_scanned_at": None,
    }
    row.update(overrides)
    return (
        row["path"],
        row["library"],
        row["zone"],
        row["mtime"],
        row["size"],
        row["checksum"],
        row["streaminfo_md5"],
        row["sha256"],
        row["duration"],
        row["bitrate"],
        row["metadata_json"],
        row["canonical_title"],
        row["canonical_artist"],
        row["canonical_album"],
        row["canonical_isrc"],
        row["canonical_duration"],
        row["canonical_year"],
        row["canonical_release_date"],
        row["canonical_bpm"],
        row["canonical_key"],
        row["canonical_genre"],
        row["canonical_sub_genre"],
        row["canonical_label"],
        row["canonical_catalog_number"],
        row["canonical_mix_name"],
        row["canonical_explicit"],
        row["canonical_energy"],
        row["dj_set_role"],
        row["dj_subrole"],
        row["energy"],
        row["isrc"],
        row["fingerprint"],
        row["metadata_health_reason"],
        row["quality_rank"],
        row["duration_ref_ms"],
        row["duration_ref_source"],
        row["is_dj_material"],
        row["last_scanned_at"],
    )


def _build_legacy_files_db(path: Path) -> Path:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            create table files (
                path text,
                library text,
                zone text,
                mtime real,
                size integer,
                checksum text,
                streaminfo_md5 text,
                sha256 text,
                duration real,
                bitrate integer,
                metadata_json text,
                canonical_title text,
                canonical_artist text,
                canonical_album text,
                canonical_isrc text,
                canonical_duration real,
                canonical_year integer,
                canonical_release_date text,
                canonical_bpm real,
                canonical_key text,
                canonical_genre text,
                canonical_sub_genre text,
                canonical_label text,
                canonical_catalog_number text,
                canonical_mix_name text,
                canonical_explicit integer,
                canonical_energy text,
                dj_set_role text,
                dj_subrole text,
                energy text,
                isrc text,
                fingerprint text,
                metadata_health_reason text,
                quality_rank integer,
                duration_ref_ms integer,
                duration_ref_source text,
                is_dj_material integer,
                last_scanned_at text
            )
            """
        )
        conn.executemany(
            """
            insert into files (
                path, library, zone, mtime, size, checksum, streaminfo_md5, sha256, duration, bitrate,
                metadata_json, canonical_title, canonical_artist, canonical_album, canonical_isrc,
                canonical_duration, canonical_year, canonical_release_date, canonical_bpm, canonical_key,
                canonical_genre, canonical_sub_genre, canonical_label, canonical_catalog_number,
                canonical_mix_name, canonical_explicit, canonical_energy, dj_set_role, dj_subrole, energy,
                isrc, fingerprint, metadata_health_reason, quality_rank, duration_ref_ms, duration_ref_source,
                is_dj_material, last_scanned_at
            ) values (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                _files_row(
                    path="/music/dup-a.flac",
                    mtime=1.0,
                    size=12345,
                    checksum="checksum-a",
                    duration=300.0,
                    bitrate=320000,
                    metadata_json=json.dumps(
                        {
                            "artist": "Artist A",
                            "title": "Title A",
                            "album": "Album A",
                            "label": "Label A",
                            "catalog_number": "CAT-A",
                            "date": "2024-01-05",
                            "bpm": "124",
                            "key": "Am",
                            "genre": "House",
                            "subgenre": "Deep",
                            "isrc": "USABC2400001",
                        }
                    ),
                    canonical_title="Title A",
                    canonical_artist="Artist A",
                    canonical_album="Album A",
                    canonical_duration=300.0,
                    canonical_year=2024,
                    canonical_release_date="2024-01-05",
                    canonical_bpm=124.0,
                    canonical_key="Am",
                    canonical_genre="House",
                    canonical_sub_genre="Deep",
                    canonical_label="Label A",
                    canonical_catalog_number="CAT-A",
                ),
                _files_row(
                    path="/music/dup-b.flac",
                    mtime=2.0,
                    size=23456,
                    checksum="checksum-b",
                    duration=301.0,
                    bitrate=319725,
                    metadata_json=json.dumps(
                        {
                            "artist": "Artist A",
                            "title": "Title B",
                            "album": "Album A",
                            "label": "Label A",
                            "catalog_number": "CAT-A",
                            "date": "2024-01-05",
                            "bpm": "124",
                            "key": "Am",
                            "genre": "House",
                            "isrc": "USABC2400001",
                        }
                    ),
                    canonical_title="Title B",
                    canonical_artist="Artist A",
                    canonical_album="Album A",
                    canonical_isrc="USABC2400001",
                    canonical_duration=301.0,
                    canonical_year=2024,
                    canonical_release_date="2024-01-05",
                    canonical_bpm=124.0,
                    canonical_key="Am",
                    canonical_genre="House",
                    canonical_label="Label A",
                    canonical_catalog_number="CAT-A",
                ),
                _files_row(
                    path="/music/fallback.flac",
                    mtime=3.0,
                    size=34567,
                    sha256="sha256-fallback",
                    duration=215.0,
                    bitrate=256000,
                    metadata_json=json.dumps(
                        {
                            "artist": "Artist C",
                            "title": "Fallback",
                            "album": "Album C",
                            "date": "2025",
                            "isrc": "GBXYZ2500001",
                        }
                    ),
                ),
                _files_row(
                    path="/music/skipped.flac",
                    mtime=4.0,
                    size=45678,
                    duration=200.0,
                    bitrate=192000,
                    metadata_json=json.dumps({"artist": "No ID", "title": "Skipped"}),
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return path


class FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[tuple[object, ...]]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.autocommit = True
        self.cursors: list[FakeCursor] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        cursor = FakeCursor()
        self.cursors.append(cursor)
        return cursor

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def test_extract_dj_slice_groups_by_isrc_and_injects_owner_id(tmp_path: Path, monkeypatch) -> None:
    sqlite_db = _build_legacy_files_db(tmp_path / "music_v3.db")
    pg_conn = FakeConnection()
    file_id_map = {
        "checksum:checksum-a": "audio-1",
        "checksum:checksum-b": "audio-2",
        "sha256:sha256-fallback": "audio-3",
    }

    def fake_execute_values(cursor, sql, values, fetch=False, **kwargs):  # type: ignore[no-untyped-def]
        cursor.calls.append((sql, list(values)))
        if "insert into public.audio_file" in sql:
            return [(file_id_map[row[1]], row[1]) for row in values]
        if "insert into public.dj_tag" in sql:
            return []
        raise AssertionError(f"unexpected SQL: {sql}")

    monkeypatch.setattr("taghag_import.extract_dj_slice.execute_values", fake_execute_values)

    summary = extract_dj_slice(
        sqlite_db,
        config=DatabaseConfig(
            supabase_url="https://example.supabase.co",
            secret_key="service-key",
            database_url="postgresql://example",
            owner_user_id="00000000-0000-0000-0000-000000000001",
        ),
        sqlite_conn=sqlite3.connect(f"file:{sqlite_db}?mode=ro", uri=True),
        pg_conn=pg_conn,
    )

    assert summary.source_rows == 4
    assert summary.eligible_rows == 3
    assert summary.skipped_rows == 1
    assert summary.skipped_missing_identity == 1
    assert summary.skipped_file_key_conflicts == 0
    assert summary.inserted_audio_files == 3
    assert summary.inserted_dj_tags == 3
    assert pg_conn.commits == 1
    assert pg_conn.rollbacks == 0

    audio_call = next(call for cursor in pg_conn.cursors for call in cursor.calls if "audio_file" in call[0])
    tag_call = next(call for cursor in pg_conn.cursors for call in cursor.calls if "dj_tag" in call[0])

    assert len(audio_call[1]) == 3
    assert all(row[0] == "00000000-0000-0000-0000-000000000001" for row in audio_call[1])
    assert {row[1] for row in audio_call[1]} == {
        "checksum:checksum-a",
        "checksum:checksum-b",
        "sha256:sha256-fallback",
    }
    assert len(tag_call[1]) == 3
    assert all(row[0] == "00000000-0000-0000-0000-000000000001" for row in tag_call[1])
    assert {row[13] for row in tag_call[1]} == {"USABC2400001", "GBXYZ2500001"}
    assert {row[18] for row in tag_call[1]} == {False}


def test_extract_dj_slice_requires_ro_sqlite(tmp_path: Path) -> None:
    sqlite_db = _build_legacy_files_db(tmp_path / "music_v3.db")
    with pytest.raises(FileNotFoundError):
        extract_dj_slice(
            tmp_path / "missing.db",
            config=DatabaseConfig(
                supabase_url="https://example.supabase.co",
                secret_key="service-key",
                database_url="postgresql://example",
                owner_user_id="00000000-0000-0000-0000-000000000001",
            ),
            pg_conn=FakeConnection(),
        )
