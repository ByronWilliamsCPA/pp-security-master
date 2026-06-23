"""Unit tests for the IBKR <OpenPosition> snapshot parser."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from security_master.extractor.ibkr_positions import (
    parse_ibkr_open_positions,
)

pytestmark = [pytest.mark.extractor]

_DOC = """<?xml version="1.0"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
  <OpenPositions>
    <OpenPosition accountId="U1" conid="111" symbol="BMBCX" isin="US000000BMBC"
        cusip="00000BMBC" figi="BBG000000BMB" description="BMBCX FUND"
        position="2520.119" markPrice="11" positionValue="27721.31"
        costBasisMoney="23540.69" costBasisPrice="10" currency="USD"
        assetCategory="STK" subCategory="ETF" side="Long" reportDate="20260619"/>
    <OpenPosition accountId="U1" conid="222" symbol="--" isin="--"
        description="CASH BALANCE" position="0" currency="USD" reportDate="20260619"/>
  </OpenPositions>
</FlexStatement></FlexStatements></FlexQueryResponse>
"""


def test_parses_open_positions_faithfully() -> None:
    positions = parse_ibkr_open_positions(_DOC)
    assert len(positions) == 2
    bmbcx = positions[0]
    assert bmbcx.account_number == "U1"
    assert bmbcx.report_date == date(2026, 6, 19)
    assert bmbcx.conid == "111"
    assert bmbcx.isin == "US000000BMBC"
    assert bmbcx.position == Decimal("2520.119")
    assert bmbcx.side == "Long"
    assert bmbcx.currency == "USD"


def test_normalizes_dash_sentinels_to_none() -> None:
    positions = parse_ibkr_open_positions(_DOC)
    cash = positions[1]
    assert cash.symbol is None
    assert cash.isin is None
    assert cash.position == Decimal(0)


def test_missing_required_attribute_raises() -> None:
    doc = (
        '<FlexQueryResponse><OpenPosition accountId="U1" symbol="X"'
        ' position="1" currency="USD" reportDate="20260619"/></FlexQueryResponse>'
    )
    with pytest.raises(ValueError, match="conid"):
        parse_ibkr_open_positions(doc)
