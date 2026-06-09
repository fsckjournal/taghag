from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import execute_values

from .config import DatabaseConfig, read_database_config


DJ_SLICE_CODEC = "mp3"
DJ_SLICE_QUERY = """
    select
        path,
        library,
        zone,
        mtime,
        size,
        checksum,
        streaminfo_md5,
        sha256,
        duration,
        bitrate,
        metadata_json,
        canonical_title,
        canonical_artist,
        canonical_album,
        canonical_isrc,
        canonical_duration,
        canonical_year,
        canonical_release_date,
        canonical_bpm,
        canonical_key,
        canonical_genre,
        canonical_sub_genre,
        canonical_label,
        canonical_catalog_number,
        canonical_mix_name,
        canonical_explicit,
        canonical_energy,
        dj_set_role,
        dj_subrole,
        energy,
        isrc,
        fingerprint,
        metadata_health_reason,
        quality_rank,
        duration_ref_ms,
        duration_ref_source,
        is_dj_material,
        last_scanned_at
    from files
    where lower(path) like '%.mp3'
    order by path
"""


@dataclass(frozen=True)
class SourceTrackRow:
    path: str
    file_key: str
    group_key: str
    size_bytes: int | None
    duration_s: float | None
    bitrate_kbps: int | None
    codec: str
    metadata: dict[str, Any]
    metadata_score: int

    def audio_file_row(self, owner_user_id: str, *, last_seen_at: datetime) -> dict[str, object]:
        return {
            "owner_user_id": owner_user_id,
            "file_key": self.file_key,
            "path": self.path,
            "filename": Path(self.path).name,
            "size_bytes": self.size_bytes,
            "duration_s": self.duration_s,
            "bitrate_kbps": self.bitrate_kbps,
            "codec": self.codec,
            "last_seen_at": last_seen_at,
        }

    def dj_tag_row(self, owner_user_id: str) -> dict[str, object]:
        meta = self.metadata
        return {
            "owner_user_id": owner_user_id,
            "artist": meta.get("artist"),
            "title": meta.get("title"),
            "album": meta.get("album"),
            "label": meta.get("label"),
            "catalog_number": meta.get("catalog_number"),
            "release_date": meta.get("release_date"),
            "year": meta.get("year"),
            "bpm": meta.get("bpm"),
            "musical_key": meta.get("musical_key"),
            "canonical_genre": meta.get("canonical_genre"),
            "canonical_subgenre": meta.get("canonical_subgenre"),
            "isrc": meta.get("isrc"),
            "rating": meta.get("rating"),
            "energy": meta.get("energy"),
            "role": meta.get("role"),
            "notes": meta.get("notes"),
            "manual_override": meta.get("manual_override", False),
        }


@dataclass(frozen=True)
class ExtractionSummary:
    source_rows: int
    eligible_rows: int
    skipped_rows: int
    skipped_missing_identity: int
    skipped_file_key_conflicts: int
    inserted_audio_files: int
    inserted_dj_tags: int


def _sqlite_connect_readonly(path: str | Path) -> sqlite3.Connection:
    sqlite_path = Path(path).expanduser().resolve()
    if not sqlite_path.exists():
        raise FileNotFoundError(sqlite_path)
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _psycopg2_connect(config: DatabaseConfig):
    if not config.database_url:
        raise RuntimeError(
            "TAGHAG_DB_POSTGRES_URL, DB_POSTGRES_URL, or DATABASE_URL is required for extract_dj_slice"
        )
    return psycopg2.connect(config.database_url)


def _normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_isrc(value: object | None) -> str | None:
    text = _normalize_text(value)
    return text.upper() if text else None


def _json_object(value: object | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_int(value: object | None) -> int | None:
    text = _normalize_text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _parse_float(value: object | None) -> float | None:
    text = _normalize_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _parse_bool(value: object | None) -> bool:
    if isinstance(value, bool):
        return value
    text = _normalize_text(value)
    if text is None:
        return False
    return text.casefold() in {"1", "true", "t", "yes", "y", "on"}


def _parse_release_date(value: object | None) -> date | None:
    text = _normalize_text(value)
    if text is None:
        return None
    if len(text) == 4 and text.isdigit():
        return date(int(text), 1, 1)
    text = text.replace("T", " ")
    try:
        return date.fromisoformat(text.split(" ", 1)[0])
    except ValueError:
        return None


def _parse_year(value: object | None) -> int | None:
    text = _normalize_text(value)
    if text is None:
        return None
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _field_score(*values: object | None) -> int:
    score = 0
    for value in values:
        if _normalize_text(value):
            score += 1
    return score


def _file_key_from_row(row: sqlite3.Row) -> str:
    sha256 = _normalize_text(row["sha256"])
    if sha256:
        return f"sha256:{sha256}"
    checksum = _normalize_text(row["checksum"])
    if checksum:
        return f"checksum:{checksum}"
    return f"path:{Path(str(row['path'])).expanduser()}"


def _metadata_isrc(row: sqlite3.Row, metadata: dict[str, Any]) -> str | None:
    return _normalize_isrc(
        row["canonical_isrc"]
        or metadata.get("isrc")
        or row["isrc"]
    )


def _group_key(row: sqlite3.Row, metadata: dict[str, Any]) -> str | None:
    isrc = _metadata_isrc(row, metadata)
    if isrc:
        return f"isrc:{isrc}"
    fingerprint = _normalize_text(row["fingerprint"])
    if fingerprint:
        return f"chromaprint:{fingerprint}"
    return None


def _canonical_metadata(row: sqlite3.Row, metadata: dict[str, Any]) -> dict[str, Any]:
    title = _normalize_text(row["canonical_title"] or metadata.get("title"))
    artist = _normalize_text(row["canonical_artist"] or metadata.get("artist"))
    album = _normalize_text(row["canonical_album"] or metadata.get("album"))
    label = _normalize_text(row["canonical_label"] or metadata.get("label"))
    catalog_number = _normalize_text(
        row["canonical_catalog_number"] or metadata.get("catalog_number")
    )
    release_date = _parse_release_date(row["canonical_release_date"] or metadata.get("date"))
    year = _parse_year(row["canonical_year"] or metadata.get("year") or metadata.get("date"))
    bpm = _parse_float(row["canonical_bpm"] or metadata.get("bpm"))
    musical_key = _normalize_text(row["canonical_key"] or metadata.get("key"))
    canonical_genre = _normalize_text(row["canonical_genre"] or metadata.get("genre"))
    canonical_subgenre = _normalize_text(row["canonical_sub_genre"] or metadata.get("subgenre"))
    isrc = _metadata_isrc(row, metadata)
    rating = _parse_int(metadata.get("rating"))
    energy = _normalize_text(row["energy"] or row["canonical_energy"] or metadata.get("energy"))
    role = _normalize_text(row["dj_set_role"] or row["dj_subrole"] or metadata.get("role"))
    notes = _normalize_text(
        metadata.get("notes")
        or metadata.get("comment")
        or row["metadata_health_reason"]
    )
    manual_override = _parse_bool(
        metadata.get("manual_override")
        or metadata.get("override")
        or row["metadata_json"] and _json_object(row["metadata_json"]).get("manual_override")
    )
    return {
        "artist": artist,
        "title": title,
        "album": album,
        "label": label,
        "catalog_number": catalog_number,
        "release_date": release_date,
        "year": year,
        "bpm": bpm,
        "musical_key": musical_key,
        "canonical_genre": canonical_genre,
        "canonical_subgenre": canonical_subgenre,
        "isrc": isrc,
        "rating": rating,
        "energy": energy,
        "role": role,
        "notes": notes,
        "manual_override": manual_override,
    }


def _row_score(row: sqlite3.Row, metadata: dict[str, Any]) -> int:
    return _field_score(
        row["canonical_title"],
        row["canonical_artist"],
        row["canonical_album"],
        row["canonical_label"],
        row["canonical_catalog_number"],
        row["canonical_release_date"],
        row["canonical_year"],
        row["canonical_bpm"],
        row["canonical_key"],
        row["canonical_genre"],
        row["canonical_sub_genre"],
        row["canonical_isrc"],
        row["isrc"],
        metadata.get("title"),
        metadata.get("artist"),
        metadata.get("album"),
        metadata.get("label"),
        metadata.get("catalog_number"),
        metadata.get("date"),
        metadata.get("year"),
        metadata.get("bpm"),
        metadata.get("key"),
        metadata.get("genre"),
        metadata.get("subgenre"),
        metadata.get("isrc"),
    )


def _source_tracks(rows: Iterable[sqlite3.Row]) -> tuple[list[SourceTrackRow], dict[str, int]]:
    grouped: dict[str, list[SourceTrackRow]] = defaultdict(list)
    skipped_missing_identity = 0

    for row in rows:
        metadata = _json_object(row["metadata_json"])
        group_key = _group_key(row, metadata)
        if group_key is None:
            skipped_missing_identity += 1
            continue

        file_key = _file_key_from_row(row)
        source_row = SourceTrackRow(
            path=str(row["path"]),
            file_key=file_key,
            group_key=group_key,
            size_bytes=_parse_int(row["size"]),
            duration_s=_parse_float(row["duration"]),
            bitrate_kbps=_parse_int(row["bitrate"] / 1000 if row["bitrate"] not in (None, "") else None),
            codec=DJ_SLICE_CODEC,
            metadata=_canonical_metadata(row, metadata),
            metadata_score=_row_score(row, metadata),
        )
        grouped[group_key].append(source_row)

    deduped: list[SourceTrackRow] = []
    seen_file_keys: dict[str, str] = {}
    skipped_file_key_conflicts = 0

    for group_key in sorted(grouped):
        rows_for_group = sorted(
            grouped[group_key],
            key=lambda item: (
                -item.metadata_score,
                item.file_key,
                item.path,
            ),
        )
        for item in rows_for_group:
            other_group = seen_file_keys.get(item.file_key)
            if other_group is not None:
                if other_group != group_key:
                    skipped_file_key_conflicts += 1
                continue
            seen_file_keys[item.file_key] = group_key
            deduped.append(item)

    return deduped, {
        "skipped_missing_identity": skipped_missing_identity,
        "skipped_file_key_conflicts": skipped_file_key_conflicts,
    }


def _chunked(items: list[dict[str, object]], size: int = 500) -> Iterable[list[dict[str, object]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _upsert_audio_files(
    cursor,
    rows: list[dict[str, object]],
) -> dict[str, str]:
    if not rows:
        return {}
    sql = """
        insert into public.audio_file (
            owner_user_id,
            file_key,
            path,
            filename,
            size_bytes,
            duration_s,
            bitrate_kbps,
            codec,
            last_seen_at
        )
        values %s
        on conflict (owner_user_id, file_key)
        do update set
            path = excluded.path,
            filename = excluded.filename,
            size_bytes = excluded.size_bytes,
            duration_s = excluded.duration_s,
            bitrate_kbps = excluded.bitrate_kbps,
            codec = excluded.codec,
            last_seen_at = excluded.last_seen_at,
            updated_at = now()
        returning id, file_key
    """
    results: list[tuple[object, ...]] = []
    for chunk in _chunked(rows):
        results.extend(
            execute_values(
                cursor,
                sql,
                [
                    (
                        row["owner_user_id"],
                        row["file_key"],
                        row["path"],
                        row["filename"],
                        row["size_bytes"],
                        row["duration_s"],
                        row["bitrate_kbps"],
                        row["codec"],
                        row["last_seen_at"],
                    )
                    for row in chunk
                ],
                fetch=True,
            )
            or []
        )
    return {str(file_key): str(audio_file_id) for audio_file_id, file_key in results}


def _upsert_dj_tags(cursor, rows: list[dict[str, object]]) -> int:
    if not rows:
        return 0
    sql = """
        insert into public.dj_tag (
            owner_user_id,
            audio_file_id,
            artist,
            title,
            album,
            label,
            catalog_number,
            release_date,
            year,
            bpm,
            musical_key,
            canonical_genre,
            canonical_subgenre,
            isrc,
            rating,
            energy,
            role,
            notes,
            manual_override
        )
        values %s
        on conflict (owner_user_id, audio_file_id)
        do update set
            artist = excluded.artist,
            title = excluded.title,
            album = excluded.album,
            label = excluded.label,
            catalog_number = excluded.catalog_number,
            release_date = excluded.release_date,
            year = excluded.year,
            bpm = excluded.bpm,
            musical_key = excluded.musical_key,
            canonical_genre = excluded.canonical_genre,
            canonical_subgenre = excluded.canonical_subgenre,
            isrc = excluded.isrc,
            rating = excluded.rating,
            energy = excluded.energy,
            role = excluded.role,
            notes = excluded.notes,
            manual_override = excluded.manual_override,
            updated_at = now()
    """
    inserted = 0
    for chunk in _chunked(rows):
        execute_values(
            cursor,
            sql,
            [
                (
                    row["owner_user_id"],
                    row["audio_file_id"],
                    row["artist"],
                    row["title"],
                    row["album"],
                    row["label"],
                    row["catalog_number"],
                    row["release_date"],
                    row["year"],
                    row["bpm"],
                    row["musical_key"],
                    row["canonical_genre"],
                    row["canonical_subgenre"],
                    row["isrc"],
                    row["rating"],
                    row["energy"],
                    row["role"],
                    row["notes"],
                    row["manual_override"],
                )
                for row in chunk
            ],
        )
        inserted += len(chunk)
    return inserted


def extract_dj_slice(
    sqlite_db_path: str | Path,
    *,
    config: DatabaseConfig | None = None,
    sqlite_conn: sqlite3.Connection | None = None,
    pg_conn=None,
) -> ExtractionSummary:
    config = config or read_database_config()
    owned_sqlite = sqlite_conn is None
    owned_pg = pg_conn is None
    sqlite_conn = sqlite_conn or _sqlite_connect_readonly(sqlite_db_path)
    try:
        sqlite_conn.row_factory = sqlite3.Row
    except Exception:
        pass
    pg_conn = pg_conn or _psycopg2_connect(config)

    try:
        rows = list(sqlite_conn.execute(DJ_SLICE_QUERY))
        source_rows, skipped = _source_tracks(rows)
        owner_user_id = config.owner_user_id
        if owner_user_id is None:
            raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

        audio_rows = [
            source_row.audio_file_row(owner_user_id, last_seen_at=datetime.now(timezone.utc))
            for source_row in source_rows
        ]

        source_by_file_key = {row.file_key: row for row in source_rows}

        try:
            pg_conn.autocommit = False
        except Exception:
            pass

        try:
            with pg_conn.cursor() as cursor:
                file_key_to_id = _upsert_audio_files(cursor, audio_rows)
                tag_rows = []
                for file_key, audio_file_id in file_key_to_id.items():
                    source_row = source_by_file_key[file_key]
                    tag_row = source_row.dj_tag_row(owner_user_id)
                    tag_row["audio_file_id"] = audio_file_id
                    tag_rows.append(tag_row)
                inserted_dj_tags = _upsert_dj_tags(cursor, tag_rows)
            pg_conn.commit()
        except Exception:
            pg_conn.rollback()
            raise

        inserted_audio_files = len(audio_rows)
        eligible_rows = len(source_rows)
        skipped_rows = len(rows) - eligible_rows
        return ExtractionSummary(
            source_rows=len(rows),
            eligible_rows=eligible_rows,
            skipped_rows=skipped_rows,
            skipped_missing_identity=skipped["skipped_missing_identity"],
            skipped_file_key_conflicts=skipped["skipped_file_key_conflicts"],
            inserted_audio_files=inserted_audio_files,
            inserted_dj_tags=inserted_dj_tags,
        )
    finally:
        if owned_sqlite:
            sqlite_conn.close()
        if owned_pg:
            pg_conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill the Taghag DJ slice from music_v3.db")
    parser.add_argument(
        "--sqlite-db",
        required=True,
        help="Path to the legacy music_v3.db SQLite database",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a compact summary after completion",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = extract_dj_slice(args.sqlite_db)
    if args.verbose:
        print(
            "read={read} eligible={eligible} inserted_audio_file={audio} inserted_dj_tag={tag} "
            "skipped={skipped} skipped_missing_identity={missing} skipped_file_key_conflicts={conflicts}".format(
                read=summary.source_rows,
                eligible=summary.eligible_rows,
                audio=summary.inserted_audio_files,
                tag=summary.inserted_dj_tags,
                skipped=summary.skipped_rows,
                missing=summary.skipped_missing_identity,
                conflicts=summary.skipped_file_key_conflicts,
            )
        )
    else:
        print(
            f"read={summary.source_rows} inserted={summary.inserted_audio_files} skipped={summary.skipped_rows}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
