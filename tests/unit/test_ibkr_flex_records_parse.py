"""Unit tests for the IBKR non-trade record parsers (cash/corp-action/transfer)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from security_master.extractor.ibkr_flex import parse_ibkr_flex_records

SAMPLE = (
    Path(__file__).resolve().parents[2] / "sample_data" / "IBKR_Flex_Records_sample.xml"
)


@pytest.fixture(scope="module")
def records():
    return parse_ibkr_flex_records(SAMPLE.read_text(encoding="utf-8"))


@pytest.mark.unit
@pytest.mark.extractor
def test_counts(records) -> None:
    assert len(records.trades) == 1
    assert len(records.cash_transactions) == 1
    assert len(records.corporate_actions) == 1
    assert len(records.transfers) == 1


@pytest.mark.unit
@pytest.mark.extractor
def test_cash_dividend(records) -> None:
    cash = records.cash_transactions[0]
    assert cash.transaction_id == "8000000010"
    assert cash.transaction_type == "Dividends"
    assert cash.dividend_type == "Ordinary Dividend"
    assert cash.amount == Decimal("25.50")
    assert cash.ex_date == date(2024, 5, 20)
    assert cash.transaction_date == date(2024, 6, 1)
    assert cash.figi == "BBG000000001"


@pytest.mark.unit
@pytest.mark.extractor
def test_corporate_action_merger(records) -> None:
    ca = records.corporate_actions[0]
    assert ca.transaction_id == "8000000020"
    assert ca.transaction_type == "TC"
    assert ca.quantity == Decimal(-4156)
    assert ca.proceeds == Decimal("122532.667322")
    assert ca.realized_pnl == Decimal("2535.167322")
    assert ca.transaction_date == date(2024, 1, 10)
    assert "MERGED" in ca.action_description


@pytest.mark.unit
@pytest.mark.extractor
def test_transfer_acats(records) -> None:
    tr = records.transfers[0]
    assert tr.transaction_id == "8000000030"
    assert tr.transaction_type == "ACATS"
    assert tr.direction == "IN"
    assert tr.amount == Decimal(675000)
    assert tr.symbol is None
    assert tr.security_name == "ACATS"
    assert tr.transaction_date == date(2024, 10, 13)


def _wrap(record_xml: str) -> str:
    """Wrap a single record element in a minimal Flex document."""
    return (
        "<FlexQueryResponse><FlexStatements><FlexStatement>"
        f"{record_xml}"
        "</FlexStatement></FlexStatements></FlexQueryResponse>"
    )


@pytest.mark.unit
@pytest.mark.extractor
def test_cash_missing_dates_raises() -> None:
    """A CashTransaction with neither settleDate nor reportDate raises."""
    xml = _wrap(
        '<CashTransactions><CashTransaction transactionID="1" '
        'type="Dividends" amount="1.00"/></CashTransactions>'
    )
    with pytest.raises(ValueError, match="missing settleDate and reportDate"):
        parse_ibkr_flex_records(xml)


@pytest.mark.unit
@pytest.mark.extractor
def test_cash_missing_transaction_id_raises() -> None:
    """A CashTransaction without transactionID raises a precise error."""
    xml = _wrap(
        '<CashTransactions><CashTransaction settleDate="06/01/2024" '
        'type="Dividends" amount="1.00"/></CashTransactions>'
    )
    with pytest.raises(ValueError, match="missing required attribute 'transactionID'"):
        parse_ibkr_flex_records(xml)


@pytest.mark.unit
@pytest.mark.extractor
def test_corp_action_missing_report_date_raises() -> None:
    """A CorporateAction without reportDate raises a precise error."""
    xml = _wrap(
        '<CorporateActions><CorporateAction transactionID="2" '
        'type="TC" amount="1.00"/></CorporateActions>'
    )
    with pytest.raises(
        ValueError, match="missing required date attribute 'reportDate'"
    ):
        parse_ibkr_flex_records(xml)


@pytest.mark.unit
@pytest.mark.extractor
def test_transfer_missing_dates_raises() -> None:
    """A Transfer with neither date nor settleDate raises."""
    xml = _wrap(
        '<Transfers><Transfer transactionID="3" type="ACATS" '
        'direction="IN"/></Transfers>'
    )
    with pytest.raises(ValueError, match="missing date and settleDate"):
        parse_ibkr_flex_records(xml)
