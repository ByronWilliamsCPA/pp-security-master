"""Unit tests for the ``pp-master`` CLI command bodies.

Each command builds its own database engine internally, so these tests
monkeypatch :func:`security_master.cli.create_db_engine` to return a shared
in-memory SQLite engine (``StaticPool`` keeps the single connection alive across
the sessions a command opens). Commands are driven through Click's
:class:`CliRunner`, which captures exit codes and output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from security_master import cli
from security_master.external.ibkr_flex_web import IBKRFlexWebClient
from security_master.external.settings import ExternalAPISettings
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
    # Pin the expected failure: an empty database raises OperationalError
    # ("no such table"), driving the command's except/rollback path. A bare
    # `is not None` check would also pass on an unrelated TypeError/ImportError.
    assert isinstance(result.exception, OperationalError)


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
    # Pin the expected failure: an empty database raises OperationalError
    # ("no such table"), driving the command's except/rollback path. A bare
    # `is not None` check would also pass on an unrelated TypeError/ImportError.
    assert isinstance(result.exception, OperationalError)


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


def test_import_broker_reports_per_type_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """import-broker echoes counts for every IBKR record type."""
    from pathlib import Path

    engine = _memory_engine()
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: engine)
    sample = (
        Path(__file__).resolve().parents[2]
        / "sample_data"
        / "IBKR_Flex_Records_sample.xml"
    )

    result = CliRunner().invoke(
        cli.app,
        ["import-broker", str(sample), "--create-schema"],
    )

    assert result.exit_code == 0, result.output
    assert "1 trade(s)" in result.output
    assert "1 cash transaction(s)" in result.output
    assert "1 corporate action(s)" in result.output
    assert "1 transfer(s)" in result.output


_FLEX_WITH_POSITIONS = (
    '<?xml version="1.0"?><FlexQueryResponse><FlexStatements><FlexStatement>'
    '<Trades><Trade tradeDate="01/02/2024" buySell="BUY" proceeds="-1000.00" '
    'currency="USD" description="APPLE INC" symbol="AAPL" tradeID="T1" '
    'quantity="10" tradePrice="100" ibCommission="-1.00"/></Trades>'
    '<OpenPositions><OpenPosition accountId="U1" conid="265598" symbol="AAPL" '
    'isin="US0378331005" description="APPLE INC" position="10" markPrice="110" '
    'positionValue="1100" currency="USD" assetCategory="STK" side="Long" '
    'reportDate="20240102"/></OpenPositions>'
    "</FlexStatement></FlexStatements></FlexQueryResponse>"
)


def _fake_flex_client(body: str) -> IBKRFlexWebClient:
    """Build a Flex client whose transport serves a canned two-step exchange."""
    envelope = (
        "<FlexStatementResponse><Status>Success</Status>"
        "<ReferenceCode>42</ReferenceCode>"
        "<Url>https://gdcdyn.interactivebrokers.com/GetStatement</Url>"
        "</FlexStatementResponse>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("SendRequest"):
            return httpx.Response(200, text=envelope)
        return httpx.Response(200, text=body)

    return IBKRFlexWebClient(
        token="fake-token",  # noqa: S106  # test token
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _s: None,
    )


def _flex_settings(tmp_path: Path, **overrides: object) -> ExternalAPISettings:
    values: dict[str, object] = {
        "ibkr_flex_token": "fake-token",
        "ibkr_flex_query_id": "123456",
        "ibkr_flex_raw_dir": tmp_path / "data" / "raw" / "ibkr",
        **overrides,
    }
    return ExternalAPISettings(_env_file=None, **values)  # type: ignore[arg-type]


def test_fetch_ibkr_flex_archives_and_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch-ibkr-flex saves the statement, imports trades and positions."""
    engine = _memory_engine()
    # Keep the in-memory database alive across both runs; dispose() would drop it.
    monkeypatch.setattr(engine, "dispose", lambda *_a, **_k: None)
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: engine)
    monkeypatch.setattr(cli, "ExternalAPISettings", lambda: _flex_settings(tmp_path))
    monkeypatch.setattr(
        cli, "_build_flex_client", lambda _s: _fake_flex_client(_FLEX_WITH_POSITIONS)
    )

    result = CliRunner().invoke(cli.app, ["fetch-ibkr-flex", "--create-schema"])

    assert result.exit_code == 0, result.output
    saved = list((tmp_path / "data" / "raw" / "ibkr").glob("*/flex_123456_*.xml"))
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == _FLEX_WITH_POSITIONS
    assert "Imported 1 trade(s)" in result.output
    assert "Imported 1 position snapshot row(s)" in result.output

    rerun = CliRunner().invoke(cli.app, ["fetch-ibkr-flex"])
    assert rerun.exit_code == 0, rerun.output
    assert "skipped 1 existing" in rerun.output


def test_fetch_ibkr_flex_no_import_only_archives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--no-import saves the file without touching the database."""

    def _no_db(*_a: object, **_k: object) -> Engine:
        msg = "database must not be used with --no-import"
        raise AssertionError(msg)

    monkeypatch.setattr(cli, "create_db_engine", _no_db)
    monkeypatch.setattr(cli, "ExternalAPISettings", lambda: _flex_settings(tmp_path))
    monkeypatch.setattr(
        cli, "_build_flex_client", lambda _s: _fake_flex_client(_MINI_IBKR)
    )

    result = CliRunner().invoke(
        cli.app, ["fetch-ibkr-flex", "--query-id", "777", "--no-import"]
    )

    assert result.exit_code == 0, result.output
    assert list((tmp_path / "data" / "raw" / "ibkr").glob("*/flex_777_*.xml"))


def test_fetch_ibkr_flex_requires_query_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without --query-id or IBKR_FLEX_QUERY_ID the command stops early."""
    settings = _flex_settings(tmp_path, ibkr_flex_query_id=None)
    monkeypatch.setattr(cli, "ExternalAPISettings", lambda: settings)

    result = CliRunner().invoke(cli.app, ["fetch-ibkr-flex"])

    assert result.exit_code != 0
    assert "No Flex Query ID" in result.output


def test_fetch_ibkr_flex_requires_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing token is a clear configuration error, not a crash."""
    settings = _flex_settings(tmp_path, ibkr_flex_token=None)
    monkeypatch.setattr(cli, "ExternalAPISettings", lambda: settings)

    result = CliRunner().invoke(cli.app, ["fetch-ibkr-flex"])

    assert result.exit_code != 0
    assert "IBKR_FLEX_TOKEN is not set" in result.output


def test_fetch_ibkr_flex_rejects_half_date_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--from-date without --to-date is a usage error."""
    monkeypatch.setattr(cli, "ExternalAPISettings", lambda: _flex_settings(tmp_path))

    result = CliRunner().invoke(
        cli.app, ["fetch-ibkr-flex", "--from-date", "2026-01-01"]
    )

    assert result.exit_code != 0
    assert "together" in result.output


def test_fetch_ibkr_flex_expired_token_shows_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IBKR error 1012 surfaces with a rotation hint and no traceback."""
    expired = (
        "<FlexStatementResponse><Status>Fail</Status><ErrorCode>1012</ErrorCode>"
        "<ErrorMessage>Token has expired.</ErrorMessage></FlexStatementResponse>"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=expired)

    client = IBKRFlexWebClient(
        token="fake-token",  # noqa: S106  # test token
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _s: None,
    )
    monkeypatch.setattr(cli, "ExternalAPISettings", lambda: _flex_settings(tmp_path))
    monkeypatch.setattr(cli, "_build_flex_client", lambda _s: client)

    result = CliRunner().invoke(cli.app, ["fetch-ibkr-flex"])

    assert result.exit_code == 1
    assert "[1012] Token has expired." in result.output
    assert "generate a new one" in result.output
