"""Unit tests for the ``pp-master`` CLI command bodies.

Each command builds its own database engine internally, so these tests
monkeypatch :func:`security_master.cli.create_db_engine` to return a shared
in-memory SQLite engine (``StaticPool`` keeps the single connection alive across
the sessions a command opens). Commands are driven through Click's
:class:`CliRunner`, which captures exit codes and output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from security_master import cli
from security_master.storage.database import create_tables, get_session_factory
from security_master.storage.pp_models import PPClientConfig

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine

pytestmark = [
    pytest.mark.patch,
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]

_MINI_PP = (
    '<?xml version="1.0"?><client><version>69</version>'
    "<baseCurrency>USD</baseCurrency><securities><security>"
    "<name>APPLE INC</name><currencyCode>USD</currencyCode>"
    "<isin>US0378331005</isin></security></securities></client>"
)

_MINI_IBKR = (
    '<?xml version="1.0"?><FlexQueryResponse><FlexStatements><FlexStatement>'
    '<Trades><Trade tradeDate="01/02/2024" buySell="BUY" proceeds="-1000.00" '
    'currency="USD" description="APPLE INC" symbol="AAPL" tradeID="T1" '
    'quantity="10" tradePrice="100" ibCommission="-1.00"/></Trades>'
    "</FlexStatement></FlexStatements></FlexQueryResponse>"
)


def _memory_engine() -> Engine:
    """Build a shared in-memory SQLite engine that survives multiple sessions.

    Returns:
        A SQLAlchemy Engine backed by a single shared in-memory connection.
    """
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_import_xml_command_reports_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """import-xml creates the schema, imports the file, and echoes a summary."""
    engine = _memory_engine()
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: engine)
    xml_file = tmp_path / "client.xml"
    xml_file.write_text(_MINI_PP, encoding="utf-8")

    result = CliRunner().invoke(
        cli.app,
        ["import-xml", str(xml_file), "--create-schema"],
    )

    assert result.exit_code == 0, result.output
    assert "Imported 1 securities" in result.output


def test_export_xml_command_writes_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """export-xml reads the active config and writes a backup to disk."""
    engine = _memory_engine()
    create_tables(engine)
    session = get_session_factory(engine)()
    session.add(
        PPClientConfig(
            version=69,
            base_currency="USD",
            config_name="default",
            is_active=True,
        ),
    )
    session.commit()
    session.close()
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: engine)

    out_file = tmp_path / "backup.xml"
    result = CliRunner().invoke(cli.app, ["export-xml", str(out_file)])

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    assert "Exported" in result.output


def test_import_xml_without_schema_rolls_back_on_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without --create-schema on an empty database, import fails and rolls back.

    Exercises the ``create_schema`` False branch and the except/rollback path.
    """
    engine = _memory_engine()  # no tables created
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: engine)
    xml_file = tmp_path / "client.xml"
    xml_file.write_text(_MINI_PP, encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["import-xml", str(xml_file)])

    assert result.exit_code != 0
    assert result.exception is not None


def test_import_broker_without_schema_errors_on_empty_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without --create-schema, import-broker errors against an empty database.

    Exercises the ``create_schema`` False branch of import-broker.
    """
    engine = _memory_engine()  # no tables created
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: engine)
    broker_file = tmp_path / "flex.xml"
    broker_file.write_text(_MINI_IBKR, encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["import-broker", str(broker_file)])

    assert result.exit_code != 0
    assert result.exception is not None


def test_import_broker_rejects_unknown_institution(tmp_path: Path) -> None:
    """import-broker fails fast for an unsupported institution."""
    broker_file = tmp_path / "x.xml"
    broker_file.write_text("<FlexQueryResponse/>", encoding="utf-8")

    result = CliRunner().invoke(
        cli.app,
        ["import-broker", str(broker_file), "--institution", "wells"],
    )

    assert result.exit_code != 0
    assert "Unsupported institution" in result.output


def test_import_broker_imports_ibkr_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """import-broker ingests an IBKR Flex file and echoes the trade count."""
    engine = _memory_engine()
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: engine)
    broker_file = tmp_path / "flex.xml"
    broker_file.write_text(_MINI_IBKR, encoding="utf-8")

    result = CliRunner().invoke(
        cli.app,
        ["import-broker", str(broker_file), "--create-schema"],
    )

    assert result.exit_code == 0, result.output
    assert "Imported 1 trade(s)" in result.output
