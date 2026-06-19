from __future__ import annotations

import re
from pathlib import Path


APP_TABLES = (
    "import_run",
    "audio_file",
    "audio_observation",
    "dj_tag",
    "tag_evidence",
    "quality_check",
    "crate",
    "crate_track",
    "saved_view",
)

# cleanroom-audit: allow-start
FORBIDDEN_SCHEMA_TERMS = (
    "flac_track",
    "asset_file",
    "track_identity",
    "asset_link",
    "preferred_asset",
    "move_plan",
    "move_execution",
    "provenance_event",
    "AAC_LIBRARY",
    "M4A derivative",
    "AAC-first",
)
# cleanroom-audit: allow-end

FORBIDDEN_STORAGE_TERMS = (
    "storage",
    "bucket",
    "upload_path",
    "storage_path",
    "object_path",
    "object_id",
    "bucket_id",
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def migration_path(root: Path | None = None) -> Path:
    if root is None:
        root = Path(__file__).parent.parent.parent
    return root / "supabase" / "migrations" / "20260606000000_initial_audio_metadata_schema.sql"


def read_migration(root: Path | None = None) -> str:
    return migration_path(root).read_text(encoding="utf-8")


def created_public_tables(sql: str) -> list[str]:
    return re.findall(r"\bcreate\s+table\s+public\.([a-z0-9_]+)\b", sql, flags=re.IGNORECASE)


def has_updated_at_trigger(sql: str, table: str) -> bool:
    pattern = rf"\bcreate\s+trigger\s+set_{re.escape(table)}_updated_at\b"
    return re.search(pattern, sql, flags=re.IGNORECASE) is not None


def has_rls_enabled(sql: str, table: str) -> bool:
    pattern = rf"\balter\s+table\s+public\.{re.escape(table)}\s+enable\s+row\s+level\s+security\b"
    return re.search(pattern, sql, flags=re.IGNORECASE) is not None


def contains_unique_isrc(sql: str) -> bool:
    return re.search(r"\bunique\b[^;\n]*\bisrc\b|\bisrc\b[^;\n]*\bunique\b", sql, flags=re.IGNORECASE) is not None
