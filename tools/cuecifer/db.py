from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

from taghag_import.config import DatabaseConfig, read_database_config


def load_database_config() -> DatabaseConfig:
    return read_database_config()


def connect_database(config: DatabaseConfig | None = None):
    config = config or load_database_config()
    if not config.database_url:
        raise RuntimeError(
            "TAGHAG_DB_POSTGRES_URL, DB_POSTGRES_URL, or DATABASE_URL is required for Cuecifer DB access"
        )
    return psycopg2.connect(config.database_url)


@contextmanager
def open_database(config: DatabaseConfig | None = None) -> Iterator[object]:
    conn = connect_database(config)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dict_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)

