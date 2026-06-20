from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from bridge import TrackResolutionError, build_tagslut_command, resolve_track_path


def _create_db(path: Path, files: list[Path]) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE track_identity (
                id INTEGER PRIMARY KEY,
                canonical_title TEXT,
                canonical_artist TEXT,
                canonical_album TEXT
            );
            CREATE TABLE asset_file (
                id INTEGER PRIMARY KEY,
                path TEXT NOT NULL
            );
            CREATE TABLE asset_link (
                asset_id INTEGER NOT NULL,
                identity_id INTEGER NOT NULL,
                active INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO track_identity VALUES (1, 'Track Title', 'Track Artist', 'Track Album')"
        )
        for index, file_path in enumerate(files, start=1):
            conn.execute("INSERT INTO asset_file VALUES (?, ?)", (index, str(file_path)))
            conn.execute("INSERT INTO asset_link VALUES (?, 1, 1)", (index,))


def test_resolve_track_path_requires_one_existing_flac(tmp_path: Path) -> None:
    track = tmp_path / "track.flac"
    track.write_bytes(b"flac")
    db = tmp_path / "music_v3.db"
    _create_db(db, [track])

    assert resolve_track_path(
        db,
        title="Track Title",
        artist="Track Artist",
        album="Track Album",
    ) == track.resolve()


def test_resolve_track_path_rejects_ambiguous_matches(tmp_path: Path) -> None:
    tracks = [tmp_path / "one.flac", tmp_path / "two.flac"]
    for track in tracks:
        track.write_bytes(b"flac")
    db = tmp_path / "music_v3.db"
    _create_db(db, tracks)

    with pytest.raises(TrackResolutionError, match="ambiguous"):
        resolve_track_path(db, title="Track Title", artist="Track Artist")


def test_tagslut_command_is_preview_only_by_default(tmp_path: Path) -> None:
    track = tmp_path / "track.flac"

    assert build_tagslut_command(track, execute=False)[-1] == "--dry-run"
    assert "--dry-run" not in build_tagslut_command(track, execute=True)
