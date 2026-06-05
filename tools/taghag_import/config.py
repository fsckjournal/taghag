from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DatabaseConfig:
    supabase_url: str
    service_role_key: str
    schema: str = "public"
    actor_id: str | None = None


def read_database_config() -> DatabaseConfig:
    supabase_url = os.environ.get("TAGHAG_SUPABASE_URL", "").rstrip("/")
    service_role_key = os.environ.get("TAGHAG_SUPABASE_SERVICE_ROLE_KEY", "")
    schema = os.environ.get("TAGHAG_DB_SCHEMA", "public")
    actor_id = os.environ.get("TAGHAG_IMPORT_ACTOR_ID")

    if not supabase_url:
        raise RuntimeError("TAGHAG_SUPABASE_URL is required")
    if not service_role_key:
        raise RuntimeError("TAGHAG_SUPABASE_SERVICE_ROLE_KEY is required")

    return DatabaseConfig(
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        schema=schema,
        actor_id=actor_id,
    )
