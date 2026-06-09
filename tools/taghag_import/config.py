from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DatabaseConfig:
    supabase_url: str
    service_role_key: str
    database_url: str | None = None
    schema: str = "public"
    owner_user_id: str | None = None


def read_database_config() -> DatabaseConfig:
    supabase_url = os.environ.get("TAGHAG_SUPABASE_URL", "").rstrip("/")
    service_role_key = os.environ.get("TAGHAG_SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get(
        "TAGHAG_SUPABASE_SECRET_KEY", ""
    )
    database_url = (
        os.environ.get("TAGHAG_DB_POSTGRES_URL", "")
        or os.environ.get("DB_POSTGRES_URL", "")
        or os.environ.get("DATABASE_URL", "")
    ).strip()
    schema = os.environ.get("TAGHAG_DB_SCHEMA", "public")
    owner_user_id = os.environ.get("TAGHAG_OWNER_USER_ID")

    if not supabase_url:
        raise RuntimeError("TAGHAG_SUPABASE_URL is required")
    if not service_role_key:
        raise RuntimeError("TAGHAG_SUPABASE_SERVICE_ROLE_KEY or TAGHAG_SUPABASE_SECRET_KEY is required")
    if not owner_user_id:
        raise RuntimeError("TAGHAG_OWNER_USER_ID is required")

    return DatabaseConfig(
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        database_url=database_url or None,
        schema=schema,
        owner_user_id=owner_user_id,
    )
