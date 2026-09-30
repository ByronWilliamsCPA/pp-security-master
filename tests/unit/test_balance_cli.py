"""CLI tests: nightly-totals, balance set, balance list (made-up data only)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from security_master.balances import cli as balances_cli
from security_master.cli import app
from security_master.extractor import IBKRPositionsImportService
from security_master.storage.balance_models import AccountBalance
from security_master.storage.database import create_db_engine, create_tables

from .balance_support import EXAMPLE_SEED

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.unit,
    pytest.mark.storage,
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]

_CASH_XML = """<?xml version="1.0"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
  <CashReport>
    <CashReportCurrency accountId="U9990001" currency="USD" toDate="20260619"
        endingCash="49.65"/>
    <CashReportCurrency accountId="U9990001" currency="BASE_SUMMARY"
        toDate="20260619" endingCash="49.65"/>
    <CashReportCurrency accountId="U9990002" currency="USD" toDate="20260619"
        endingCash="0.50"/>
  </CashReport>
</FlexStatement></FlexStatements></FlexQueryResponse>
"""

_POSITIONS_XML = """<?xml version="1.0"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
  <OpenPositions>
    <OpenPosition accountId="U9990001" conid="1" symbol="AAA" description="ONE"
        position="10" positionValue="1000.10" currency="USD" reportDate="20260619"/>
    <OpenPosition accountId="U9990001" conid="2" symbol="BBB" description="TWO"
        position="5" positionValue="250.25" currency="USD" reportDate="20260619"/>
    <OpenPosition accountId="U9990002" conid="3" symbol="CCC" description="THREE"
        position="2" positionValue="20.00" currency="USD" reportDate="20260619"/>
  </OpenPositions>
</FlexStatement></FlexStatements></FlexQueryResponse>
"""


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'balances.db'}"


def _invoke(url: str, *args: str) -> object:
    return CliRunner().invoke(
        app,
        [*args, "--database-url", url, "--registry-path", str(EXAMPLE_SEED)],
    )


def _seed_ibkr(url: str, tmp_path: Path, positions: str = _POSITIONS_XML) -> None:
    cash_file = tmp_path / "cash.xml"
    cash_file.write_text(_CASH_XML, encoding="utf-8")
    imported = CliRunner().invoke(
        app, ["import-broker", str(cash_file), "--database-url", url, "--create-schema"]
    )
    assert imported.exit_code == 0, imported.output
    assert "2 cash report row(s)" in imported.output
    engine = create_db_engine(url)
    with Session(engine) as session:
        IBKRPositionsImportService(session).import_from_string(positions)
    engine.dispose()


def _rows(url: str) -> dict[str, AccountBalance]:
    engine = create_db_engine(url)
    with Session(engine) as session:
        rows = {r.account_key: r for r in session.query(AccountBalance)}
        session.expunge_all()
    engine.dispose()
    return rows


def test_list_returns_every_mapped_account_from_ibkr_and_manual_marks(
    url: str, tmp_path: Path
) -> None:
    _seed_ibkr(url, tmp_path)
    totals = _invoke(url, "nightly-totals")
    assert totals.exit_code == 0, totals.output
    assert "2026-06-19" in totals.output
    assert "wrote 2" in totals.output

    marked = _invoke(
        url,
        "balance",
        "set",
        "--account",
        "pp:bank:0003",
        "--value",
        "-12.30",
        "--as-of",
        "2026-06-18",
        "--source",
        "manual_mark",
        "--note",
        "statement page 1",
        "--entered-by",
        "example.operator",
    )
    assert marked.exit_code == 0, marked.output

    listed = _invoke(url, "balance", "list", "--format", "json")
    assert listed.exit_code == 0, listed.output
    data = {r["account_key"]: r for r in json.loads(listed.output)}
    assert sorted(data) == ["pp:bank:0003", "pp:ibkr:0001", "pp:ibkr:0002"]
    assert data["pp:ibkr:0001"]["value"] == "1300.00"
    assert data["pp:ibkr:0002"]["value"] == "20.50"
    assert data["pp:bank:0003"]["value"] == "-12.30"
    for row in data.values():
        assert isinstance(row["value"], str)
        assert row["currency"] == "USD"
    assert data["pp:ibkr:0001"]["source"] == "ibkr_flex"
    assert data["pp:ibkr:0001"]["as_of"] == "2026-06-19"
    assert data["pp:bank:0003"]["source"] == "manual_mark"
    assert data["pp:bank:0003"]["entered_by"] == "example.operator"
    assert data["pp:ibkr:0002"]["category"] == "Retirement"

    table = _invoke(url, "balance", "list")
    assert table.exit_code == 0
    assert "1300.00" in table.output
    assert "Example Joint Checking" in table.output


def test_list_shows_unmarked_accounts_with_null_value(url: str) -> None:
    listed = _invoke(url, "balance", "list", "--format", "json", "--create-schema")
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)
    assert len(rows) == 3
    assert all(r["value"] is None and r["as_of"] is None for r in rows)


def test_list_as_of_filters_to_an_exact_date(url: str) -> None:
    for as_of, value in (("2026-06-01", "10.00"), ("2026-06-10", "20.00")):
        result = _invoke(
            url,
            "balance",
            "set",
            "--account",
            "pp:ibkr:0001",
            "--value",
            value,
            "--as-of",
            as_of,
            "--entered-by",
            "example.operator",
            "--create-schema",
        )
        assert result.exit_code == 0, result.output
    latest = json.loads(_invoke(url, "balance", "list", "--format", "json").output)
    older = json.loads(
        _invoke(
            url, "balance", "list", "--format", "json", "--as-of", "2026-06-01"
        ).output
    )
    by_key = lambda rows: {r["account_key"]: r for r in rows}  # noqa: E731
    assert by_key(latest)["pp:ibkr:0001"]["value"] == "20.00"
    assert by_key(older)["pp:ibkr:0001"]["value"] == "10.00"
    assert by_key(older)["pp:ibkr:0002"]["value"] is None


def _set(url: str, *extra: str, value: str = "100.50", as_of: str = "2026-06-18"):
    return _invoke(
        url,
        "balance",
        "set",
        "--account",
        "pp:ibkr:0001",
        "--value",
        value,
        "--as-of",
        as_of,
        "--create-schema",
        *extra,
    )


def test_set_records_who_entered_the_mark_and_does_not_echo_the_value(
    url: str,
) -> None:
    result = _set(url, "--entered-by", "  example.operator ", "--note", "  memo  ")
    assert result.exit_code == 0, result.output
    assert "100.50" not in result.output
    assert "example.operator" in result.output
    row = _rows(url)["pp:ibkr:0001"]
    assert row.value == Decimal("100.50")
    assert row.entered_by == "example.operator"
    assert row.note == "memo"
    assert row.source == "manual_mark"
    assert row.currency == "USD"
    assert row.as_of == date(2026, 6, 18)
    assert row.entered_at is not None
    assert row.category == "Investments"
    assert str(row.entity_id) == "11111111-1111-4111-8111-111111111111"


def test_set_defaults_entered_by_to_the_os_user(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(balances_cli.getpass, "getuser", lambda: "os.user.example")
    assert _set(url).exit_code == 0
    assert _rows(url)["pp:ibkr:0001"].entered_by == "os.user.example"


def test_set_refuses_to_record_an_anonymous_mark(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(balances_cli.getpass, "getuser", lambda: "")
    result = _set(url)
    assert result.exit_code != 0
    assert "entered-by" in result.output
    assert _rows(url) == {}


def test_set_requires_replace_to_overwrite_then_updates_attribution(url: str) -> None:
    assert _set(url, "--entered-by", "first.person").exit_code == 0
    clash = _set(url, "--entered-by", "second.person", value="200.00")
    assert clash.exit_code != 0
    assert "--replace" in clash.output
    assert "200.00" not in clash.output
    assert _rows(url)["pp:ibkr:0001"].value == Decimal("100.50")

    fixed = _set(url, "--entered-by", "second.person", "--replace", value="200.00")
    assert fixed.exit_code == 0, fixed.output
    row = _rows(url)["pp:ibkr:0001"]
    assert (row.value, row.entered_by) == (Decimal("200.00"), "second.person")
    assert len(_rows(url)) == 1


@pytest.mark.parametrize("bad", ["1e3", "12.345", "NaN", "1,000.00", "abc"])
def test_set_rejects_malformed_values_without_echoing_them(url: str, bad: str) -> None:
    engine = create_db_engine(url)
    create_tables(engine)
    engine.dispose()
    result = _set(url, "--entered-by", "example.operator", value=bad)
    assert result.exit_code != 0
    assert bad not in result.output.replace("--value", "")
    assert _rows(url) == {}


def test_set_rejects_future_dates(url: str) -> None:
    tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    result = _set(url, "--entered-by", "example.operator", as_of=tomorrow)
    assert result.exit_code != 0
    assert "future" in result.output


def test_negative_values_are_only_for_cash_accounts(url: str) -> None:
    denied = _set(url, "--entered-by", "example.operator", value="-5.00")
    assert denied.exit_code != 0
    assert "Cash" in denied.output
    allowed = _invoke(
        url,
        "balance",
        "set",
        "--account",
        "pp:bank:0003",
        "--value",
        "-5.00",
        "--as-of",
        "2026-06-18",
        "--entered-by",
        "example.operator",
    )
    assert allowed.exit_code == 0, allowed.output
    assert _rows(url)["pp:bank:0003"].value == Decimal("-5.00")


def test_set_rejects_unmapped_accounts_and_bad_sources(url: str) -> None:
    unmapped = _invoke(
        url,
        "balance",
        "set",
        "--account",
        "pp:ibkr:9999",
        "--value",
        "1.00",
        "--as-of",
        "2026-06-18",
        "--entered-by",
        "example.operator",
        "--create-schema",
    )
    assert unmapped.exit_code != 0
    assert "not in the account registry" in unmapped.output

    for source in ("ibkr_flex", "bogus"):
        result = _set(url, "--entered-by", "example.operator", "--source", source)
        assert result.exit_code != 0
    assert _rows(url) == {}


def test_missing_registry_configuration_is_a_clean_error(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PP_ACCOUNT_REGISTRY_PATH", raising=False)
    result = CliRunner().invoke(app, ["balance", "list", "--database-url", url])
    assert result.exit_code != 0
    assert "PP_ACCOUNT_REGISTRY_PATH" in result.output
    assert "Traceback" not in result.output


def test_nightly_totals_exits_nonzero_and_logs_when_an_account_is_withheld(
    url: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    eur = _POSITIONS_XML.replace(
        'position="2" positionValue="20.00" currency="USD"',
        'position="2" positionValue="20.00" currency="EUR"',
    )
    _seed_ibkr(url, tmp_path, positions=eur)
    caplog.set_level(logging.INFO)
    result = _invoke(url, "nightly-totals")
    assert result.exit_code == 1
    assert "withheld 1 account(s)" in result.output
    assert "non_usd_row" in caplog.text
    assert "EUR" in caplog.text
    for secret in ("1300", "20.00", "49.65", "U999000"):
        assert secret not in caplog.text
        assert secret not in result.output
    assert list(_rows(url)) == ["pp:ibkr:0001"]


def test_nightly_totals_without_positions_is_an_error(url: str) -> None:
    engine = create_db_engine(url)
    create_tables(engine)
    engine.dispose()
    result = _invoke(url, "nightly-totals")
    assert result.exit_code != 0
    assert "nothing to total" in result.output
