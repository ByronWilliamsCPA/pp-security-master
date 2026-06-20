"""Unit tests for the pure IBKR Flex parse stage (no database, no network)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from security_master.extractor.ibkr_flex import (
    ParsedTrade,
    _none_if_empty,
    parse_ibkr_flex,
)

SAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "sample_data" / "IBKR_Flex_Trades_sample.xml"
)

EXPECTED_TRADE_COUNT = 67


@pytest.fixture(scope="module")
def sample_xml() -> str:
    """Read the IBKR Flex sample fixture once per module.

    Returns:
        The raw XML content of the sanitized IBKR Flex sample.
    """
    return SAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed(sample_xml: str) -> list[ParsedTrade]:
    """Parse the sample once per module for assertion reuse.

    Args:
        sample_xml: Raw XML content from the sample fixture.

    Returns:
        The full list of parsed trades in document order.
    """
    return parse_ibkr_flex(sample_xml)


@pytest.mark.unit
@pytest.mark.extractor
def test_parses_all_trades(parsed: list[ParsedTrade]) -> None:
    """All 67 Trade elements in the sample are parsed."""
    assert len(parsed) == EXPECTED_TRADE_COUNT


@pytest.mark.unit
@pytest.mark.extractor
def test_document_order_preserved(parsed: list[ParsedTrade]) -> None:
    """Trades are returned in document order; the first element is BUFF."""
    first = parsed[0]
    assert first.symbol == "BUFF"
    assert first.trade_id == "1000000001"


@pytest.mark.unit
@pytest.mark.extractor
def test_dbja_trade_field_mapping(parsed: list[ParsedTrade]) -> None:
    """The DBJA trade maps every required field to the expected value.

    Note: the DBJA record is the seventh Trade in document order, not the
    first. Its real tradePrice in the sample is 28.86 (the brief's "first
    trade ... 28.87" does not match the fixture; the fixture is the source
    of truth). We locate DBJA by symbol rather than by index.
    """
    dbja = next(t for t in parsed if t.symbol == "DBJA")

    assert dbja.symbol == "DBJA"
    assert dbja.isin == "US45782C1365"
    assert dbja.cusip == "45782C136"
    assert dbja.quantity == Decimal(100)
    assert dbja.price == Decimal("28.86")
    assert dbja.transaction_type == "BUY"
    assert dbja.transaction_date == date(2023, 10, 16)
    assert dbja.settlement_date == date(2023, 10, 18)
    assert dbja.amount == Decimal(-2886)
    assert dbja.currency == "USD"
    assert dbja.commission == Decimal(-1)
    assert dbja.ib_commission == Decimal(-1)
    assert dbja.account_name == "Interactive Brokers"
    assert dbja.account_number == "U0000000"
    assert dbja.trade_id == "1000000007"
    assert dbja.asset_class == "STK"
    assert dbja.sec_type == "ETF"


@pytest.mark.unit
@pytest.mark.extractor
def test_optional_fields_empty_become_none(parsed: list[ParsedTrade]) -> None:
    """Empty IBKR attributes (e.g. strike, expiry, putCall) map to None.

    These are empty strings in the sample; the model columns are Date and
    Numeric, which would raise if handed "". Verify the helper kept them None.
    """
    dbja = next(t for t in parsed if t.symbol == "DBJA")
    assert dbja.strike is None
    assert dbja.expiry is None
    assert dbja.put_call is None
    assert dbja.underlying_symbol is None
    assert dbja.execution_id is None  # ibExecID is empty in the sample


@pytest.mark.unit
@pytest.mark.extractor
def test_security_name_present_and_bounded(parsed: list[ParsedTrade]) -> None:
    """security_name is non-empty and never exceeds the 255-char column."""
    for trade in parsed:
        assert trade.security_name
        assert len(trade.security_name) <= 255


@pytest.mark.unit
@pytest.mark.extractor
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", None),
        ("   ", None),
        (None, None),
        ("value", "value"),
        ("  trimmed  ", "trimmed"),
        ("0", "0"),
    ],
)
def test_none_if_empty(raw: str | None, expected: str | None) -> None:
    """Empty and whitespace-only strings become None; real values pass through.

    Args:
        raw: Input value to normalize.
        expected: Expected normalized output.
    """
    assert _none_if_empty(raw) == expected
