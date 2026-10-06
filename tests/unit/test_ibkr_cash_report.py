"""Unit tests for the IBKR Flex CashReport parser and its import path."""

from __future__ import annotations

import logging
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
    # No chained exception may carry the raw text: either nothing was being
    # handled (NaN, Infinity) or the context is suppressed with ``from None``.
    assert info.value.__cause__ is None
    assert info.value.__context__ is None or info.value.__suppress_context__
    assert "U9990001" not in str(info.value)


@pytest.mark.parametrize(
    ("attrs", "fragment"),
    [
        ('currency="USD" endingCash="1.0000001"', "decimal places"),
        ('currency="USD" endingCash="1000000000000"', "range"),
        ('currency="USDX" endingCash="1"', "three-letter"),
        ('currency="U1D" endingCash="1"', "three-letter"),
    ],
)
def test_cash_report_values_must_fit_the_column(attrs: str, fragment: str) -> None:
    doc = (
        '<FlexQueryResponse><CashReportCurrency accountId="U9990001" '
        f'toDate="20260619" {attrs}/></FlexQueryResponse>'
    )
    with pytest.raises(ValueError, match=fragment):
        parse_ibkr_flex_records(doc)


def test_trailing_zeros_beyond_six_places_are_accepted() -> None:
    doc = (
        '<FlexQueryResponse><CashReportCurrency accountId="U9990001" '
        'currency="USD" toDate="20260619" endingCash="1.50000000"/>'
        "</FlexQueryResponse>"
    )
    (row,) = parse_ibkr_flex_records(doc).cash_report
    assert row.ending_cash == Decimal("1.5")


def test_lowercase_base_summary_is_also_skipped() -> None:
    doc = _DOC.replace('currency="BASE_SUMMARY"', 'currency="base_summary"')
    currencies = [r.currency for r in parse_ibkr_flex_records(doc).cash_report]
    assert currencies == ["USD", "EUR"]


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


def test_restated_cash_report_updates_the_row(
    sqlite_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """A later file with a different amount for the same key must win."""
    service = IBKRFlexImportService(sqlite_session)
    service.import_from_string(_DOC)
    caplog.set_level(logging.WARNING)
    restated = service.import_from_string(
        _DOC.replace(
            'currency="USD" fromDate="20260619"\n        toDate="20260619" '
            'startingCash="1.00" endingCash="1500.256789"',
            'currency="USD" fromDate="20260619"\n        toDate="20260619" '
            'startingCash="1.00" endingCash="1600.5"',
        )
    )
    assert (restated.cash_report_rows, restated.cash_report_updated) == (0, 1)
    assert restated.skipped == 1  # the unchanged EUR row
    stored = sqlite_session.query(InteractiveBrokersCashReport).all()
    assert len(stored) == 2
    usd = next(r for r in stored if r.currency == "USD")
    assert usd.ending_cash == Decimal("1600.5")
    assert usd.import_batch_id == restated.import_batch_id
    assert "ending_cash_changed" in caplog.text
    for secret in ("1600", "1500", "U9990001"):
        assert secret not in caplog.text


def test_conflicting_duplicate_in_one_document_is_refused(
    sqlite_session: Session,
) -> None:
    doc = (
        "<FlexQueryResponse>"
        '<CashReportCurrency accountId="U9990001" currency="USD" '
        'toDate="20260619" endingCash="1"/>'
        '<CashReportCurrency accountId="U9990001" currency="USD" '
        'toDate="20260619" endingCash="2"/>'
        "</FlexQueryResponse>"
    )
    with pytest.raises(ValueError, match="two different endingCash"):
        IBKRFlexImportService(sqlite_session).import_from_string(doc)
    sqlite_session.rollback()
    assert sqlite_session.query(InteractiveBrokersCashReport).count() == 0


def test_identical_duplicate_in_one_document_is_skipped(
    sqlite_session: Session,
) -> None:
    row = (
        '<CashReportCurrency accountId="U9990001" currency="USD" '
        'toDate="20260619" endingCash="1"/>'
    )
    doc = f"<FlexQueryResponse>{row}{row}</FlexQueryResponse>"
    summary = IBKRFlexImportService(sqlite_session).import_from_string(doc)
    assert (summary.cash_report_rows, summary.skipped) == (1, 1)
