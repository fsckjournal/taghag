from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Sequence

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.is_file():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()

class TrackResolutionError(RuntimeError):
    pass


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def find_track_paths(
    db_path: Path,
    *,
    title: str,
    artist: str,
    album: str | None = None,
) -> list[Path]:
    if not db_path.is_file():
        raise TrackResolutionError(f"database not found: {db_path}")

    predicates = [
        "lower(trim(ti.canonical_title)) = ?",
        "lower(trim(ti.canonical_artist)) = ?",
        "al.active = 1",
        "lower(af.path) LIKE '%.flac'",
    ]
    params = [_normalized(title), _normalized(artist)]
    if album:
        predicates.append("lower(trim(ti.canonical_album)) = ?")
        params.append(_normalized(album))

    query = f"""
        SELECT DISTINCT af.path
        FROM track_identity AS ti
        JOIN asset_link AS al ON al.identity_id = ti.id
        JOIN asset_file AS af ON af.id = al.asset_id
        WHERE {" AND ".join(predicates)}
        ORDER BY af.path
    """

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [Path(str(row[0])).expanduser() for row in rows if row and row[0]]


def resolve_track_path(
    db_path: Path,
    *,
    title: str,
    artist: str,
    album: str | None = None,
) -> Path:
    candidates = find_track_paths(
        db_path,
        title=title,
        artist=artist,
        album=album,
    )
    existing = [path.resolve() for path in candidates if path.is_file()]
    if not existing:
        detail = f"{artist} - {title}"
        if album:
            detail += f" ({album})"
        raise TrackResolutionError(f"no linked FLAC master found for {detail}")
    if len(existing) > 1:
        rendered = "\n".join(f"  {path}" for path in existing)
        raise TrackResolutionError(
            "now-playing metadata is ambiguous; no file was changed:\n" + rendered
        )
    return existing[0]


def build_taghag_command(file_path: Path, *, execute: bool, repo_root: Path) -> list[str]:
    executable = str(repo_root / "tools" / ".venv" / "bin" / "taghag-import")
    command = [executable, "cuecifer", "analyze-file", "--file", str(file_path)]
    if not execute:
        command.append("--dry-run")
    return command


def run_taghag(
    file_path: Path,
    *,
    execute: bool,
    repo_root: Path,
) -> int:
    command = build_taghag_command(file_path, execute=execute, repo_root=repo_root)
    print(f"Mode: {'execute' if execute else 'preview'}", flush=True)
    print(f"File: {file_path}", flush=True)
    return subprocess.run(command, cwd=repo_root, check=False).returncode


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve Roon now-playing metadata to one canonical FLAC master.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--artist", required=True)
    parser.add_argument("--album")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--execute", action="store_true", help="Apply tag changes. Default is preview only.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    raw_db = args.db or os.environ.get("TAGSLUT_DB")
    if not raw_db:
        print("TAGSLUT_DB is required", file=sys.stderr)
        return 2

    try:
        file_path = resolve_track_path(
            Path(raw_db).expanduser().resolve(),
            title=args.title,
            artist=args.artist,
            album=args.album,
        )
    except (sqlite3.Error, TrackResolutionError) as exc:
        print(f"Resolution failed: {exc}", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    return run_taghag(file_path, execute=args.execute, repo_root=repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
