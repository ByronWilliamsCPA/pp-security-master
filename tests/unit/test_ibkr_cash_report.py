"""Unit tests for the IBKR Flex CashReport parser and its import path."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from security_master.extractor.ibkr_flex import (
    IBKRFlexImportService,
    parse_ibkr_flex_records,
)
from security_master.storage.position_models import InteractiveBrokersCashReport

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = [
    pytest.mark.extractor,
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]

_DOC = """<?xml version="1.0"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
  <CashReport>
    <CashReportCurrency accountId="U9990001" currency="USD" fromDate="20260619"
        toDate="20260619" startingCash="1.00" endingCash="1500.256789"/>
    <CashReportCurrency accountId="U9990001" currency="EUR" fromDate="20260619"
        toDate="20260619" endingCash="0"/>
    <CashReportCurrency accountId="U9990001" currency="BASE_SUMMARY"
        fromDate="20260619" toDate="20260619" endingCash="1500.256789"/>
  </CashReport>
</FlexStatement></FlexStatements></FlexQueryResponse>
"""


def test_cash_report_parses_per_currency_rows() -> None:
    rows = parse_ibkr_flex_records(_DOC).cash_report
    assert [(r.currency, r.ending_cash) for r in rows] == [
        ("USD", Decimal("1500.256789")),
        ("EUR", Decimal(0)),
    ]
    assert rows[0].report_date == date(2026, 6, 19)
    assert rows[0].account_number == "U9990001"


def test_cash_report_skips_base_summary() -> None:
    """The roll-up row would double count cash if it were stored."""
    currencies = [r.currency for r in parse_ibkr_flex_records(_DOC).cash_report]
    assert "BASE_SUMMARY" not in currencies


def test_cash_report_falls_back_to_report_date() -> None:
    doc = (
        '<FlexQueryResponse><CashReportCurrency accountId="U9990001" '
        'currency="usd" reportDate="20260620" endingCash="5"/></FlexQueryResponse>'
    )
    (row,) = parse_ibkr_flex_records(doc).cash_report
    assert row.report_date == date(2026, 6, 20)
    assert row.currency == "USD"


@pytest.mark.parametrize(
    ("attrs", "fragment"),
    [
        ('currency="USD" toDate="20260619" endingCash="1"', "accountId"),
        ('accountId="U9990001" toDate="20260619" endingCash="1"', "currency"),
        ('accountId="U9990001" currency="USD" endingCash="1"', "reportDate"),
        ('accountId="U9990001" currency="USD" toDate="20260619"', "endingCash"),
    ],
)
def test_cash_report_missing_attribute_raises(attrs: str, fragment: str) -> None:
    doc = f"<FlexQueryResponse><CashReportCurrency {attrs}/></FlexQueryResponse>"
    with pytest.raises(ValueError, match=fragment):
        parse_ibkr_flex_records(doc)


@pytest.mark.parametrize("bad", ["12.3.4", "abc", "NaN", "Infinity", "-Infinity"])
def test_bad_ending_cash_raises_without_echoing_the_amount(bad: str) -> None:
    doc = (
        '<FlexQueryResponse><CashReportCurrency accountId="U9990001" '
        f'currency="USD" toDate="20260619" endingCash="{bad}"/></FlexQueryResponse>'
    )
    with pytest.raises(ValueError, match="endingCash") as info:
        parse_ibkr_flex_records(doc)
    assert bad not in str(info.value)
    assert info.value.__cause__ is None
    assert "U9990001" not in str(info.value)


def test_cash_report_import_is_idempotent(sqlite_session: Session) -> None:
    service = IBKRFlexImportService(sqlite_session)
    first = service.import_from_string(_DOC)
    second = service.import_from_string(_DOC)
    assert first.cash_report_rows == 2
    assert second.cash_report_rows == 0
    assert second.skipped == 2
    stored = sqlite_session.query(InteractiveBrokersCashReport).all()
    assert len(stored) == 2
    usd = next(r for r in stored if r.currency == "USD")
    assert usd.ending_cash == Decimal("1500.256789")
    assert "1500" not in repr(usd)
