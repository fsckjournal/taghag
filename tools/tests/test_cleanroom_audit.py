from __future__ import annotations

from pathlib import Path

from audit_cleanroom import scan


def test_cleanroom_audit_passes_clean_project(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "ok.py").write_text("print('hello')\n", encoding="utf-8")

    assert scan(tmp_path, ("tools",)) == []


def test_cleanroom_audit_fails_for_forbidden_python_import(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    # cleanroom-audit: allow-start
    (tools / "bad.py").write_text("from tagslut.foo import bar\n", encoding="utf-8")
    # cleanroom-audit: allow-end

    findings = scan(tmp_path, ("tools",))

    assert len(findings) == 1
    # cleanroom-audit: allow-start
    assert findings[0].term == "from tagslut"
    # cleanroom-audit: allow-end


def test_cleanroom_audit_fails_for_forbidden_sql_schema_name(tmp_path: Path) -> None:
    migrations = tmp_path / "supabase" / "migrations"
    migrations.mkdir(parents=True)
    # cleanroom-audit: allow-start
    (migrations / "bad.sql").write_text("create table asset_file (id uuid);\n", encoding="utf-8")
    # cleanroom-audit: allow-end

    findings = scan(tmp_path, ("supabase",))

    assert len(findings) == 1
    # cleanroom-audit: allow-start
    assert findings[0].term == "asset_file"
    # cleanroom-audit: allow-end


def test_cleanroom_audit_allows_marked_warning_blocks(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "warning.md").write_text(
        "\n".join(
            [
                "cleanroom-audit: allow-start",
                # cleanroom-audit: allow-start
                "historical warning about track_identity",
                # cleanroom-audit: allow-end
                "cleanroom-audit: allow-end",
            ]
        ),
        encoding="utf-8",
    )

    assert scan(tmp_path, ("docs",)) == []
