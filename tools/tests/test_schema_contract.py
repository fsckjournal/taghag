from __future__ import annotations

from taghag_import.schema_contract import (
    APP_TABLES,
    FORBIDDEN_SCHEMA_TERMS,
    FORBIDDEN_STORAGE_TERMS,
    contains_unique_isrc,
    created_public_tables,
    has_rls_enabled,
    has_updated_at_trigger,
    migration_path,
    read_migration,
)


def test_canonical_migration_path_exists() -> None:
    assert migration_path().is_file()


def test_migration_creates_exactly_canonical_app_tables() -> None:
    sql = read_migration()

    assert created_public_tables(sql) == list(APP_TABLES)


def test_migration_rejects_legacy_schema_terms() -> None:
    sql = read_migration()

    for term in FORBIDDEN_SCHEMA_TERMS:
        assert term not in sql


def test_migration_rejects_storage_and_upload_terms() -> None:
    sql = read_migration()

    for term in FORBIDDEN_STORAGE_TERMS:
        assert term not in sql


def test_migration_has_no_anon_policies_or_isrc_identity() -> None:
    sql = read_migration()

    assert "to anon" not in sql.lower()
    assert not contains_unique_isrc(sql)


def test_migration_enables_rls_for_every_app_table() -> None:
    sql = read_migration()

    missing = [table for table in APP_TABLES if not has_rls_enabled(sql, table)]

    assert missing == []


def test_migration_adds_updated_at_trigger_for_every_app_table() -> None:
    sql = read_migration()

    missing = [table for table in APP_TABLES if not has_updated_at_trigger(sql, table)]

    assert missing == []
