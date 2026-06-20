"""Unit tests for the Security Master CLI (no database required).

Exercises the Click command surface (help text, argument validation) without
touching a database, so these run in the fast unit tier.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from security_master.cli import app


@pytest.mark.unit
def test_cli_exposes_both_commands() -> None:
    """The top-level group lists import-xml and export-xml."""
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "import-xml" in result.output
    assert "export-xml" in result.output


@pytest.mark.unit
def test_import_xml_help_documents_options() -> None:
    """import-xml advertises its config and schema options."""
    result = CliRunner().invoke(app, ["import-xml", "--help"])
    assert result.exit_code == 0
    assert "--config-name" in result.output
    assert "--create-schema" in result.output


@pytest.mark.unit
def test_import_xml_rejects_missing_file() -> None:
    """A missing input path fails before any database work."""
    result = CliRunner().invoke(app, ["import-xml", "/no/such/file.xml"])
    assert result.exit_code != 0


@pytest.mark.unit
def test_export_xml_help() -> None:
    """export-xml advertises its config option."""
    result = CliRunner().invoke(app, ["export-xml", "--help"])
    assert result.exit_code == 0
    assert "--config-name" in result.output
