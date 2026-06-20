"""Unit tests for :mod:`security_master.storage.schema_export`.

The generators are pure string producers (PostgreSQL DDL via a mock engine,
plus Mermaid/PlantUML/DBML text), and ``export_schema_files`` writes them to a
``schema_exports`` directory relative to the current working directory. Tests
run in a temporary directory so no repository files are touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from security_master.storage import schema_export

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.storage


def test_generate_postgres_ddl_emits_create_table() -> None:
    """The DDL generator compiles the ORM models into CREATE TABLE statements."""
    ddl = schema_export.generate_postgres_ddl()
    assert "CREATE TABLE" in ddl
    assert "securities_master" in ddl


def test_generate_mermaid_er_diagram_is_fenced_mermaid() -> None:
    """The Mermaid generator returns a fenced erDiagram block."""
    out = schema_export.generate_mermaid_er_diagram()
    assert "```mermaid" in out
    assert "erDiagram" in out


def test_generate_plantuml_er_diagram_is_plantuml() -> None:
    """The PlantUML generator returns a @startuml ... @enduml document."""
    out = schema_export.generate_plantuml_er_diagram()
    assert "@startuml" in out
    assert "@enduml" in out


def test_generate_dbdiagram_schema_is_dbml() -> None:
    """The dbdiagram.io generator returns DBML table definitions."""
    out = schema_export.generate_dbdiagram_schema()
    assert "Table" in out


def test_export_schema_files_writes_all_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """export_schema_files writes the four artifacts into schema_exports/."""
    monkeypatch.chdir(tmp_path)
    schema_export.export_schema_files()

    export_dir = tmp_path / "schema_exports"
    expected = {
        "security_master_schema.sql",
        "security_master_schema.dbml",
        "security_master_schema.md",
        "security_master_schema.puml",
    }
    written = {p.name for p in export_dir.iterdir()}
    assert expected <= written
    # Each artifact has content.
    for name in expected:
        assert (export_dir / name).read_text(encoding="utf-8").strip()
