"""Unit tests for the IBKR open-position snapshot ORM model."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from security_master.extractor.ibkr_positions import IBKRPositionsImportService
from security_master.storage.position_models import InteractiveBrokersOpenPosition

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = [
    pytest.mark.storage,
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]


def test_open_position_round_trip(sqlite_session: Session) -> None:
    row = InteractiveBrokersOpenPosition(
        account_number="U1",
        report_date=date(2026, 6, 19),
        conid="111",
        symbol="BMBCX",
        isin="US000000BMBC",
        security_name="BMBCX FUND",
        position=Decimal("2520.119"),
        currency="USD",
        side="Long",
        import_batch_id="ibkr-pos-test",
    )
    sqlite_session.add(row)
    sqlite_session.commit()

    fetched = sqlite_session.query(InteractiveBrokersOpenPosition).one()
    assert fetched.position == Decimal("2520.119")
    assert fetched.report_date == date(2026, 6, 19)
    assert fetched.isin == "US000000BMBC"
    assert fetched.side == "Long"


_POS_DOC = """<?xml version="1.0"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
  <OpenPositions>
    <OpenPosition accountId="U1" conid="111" symbol="BMBCX" isin="US000000BMBC"
        description="BMBCX FUND" position="2520.119" currency="USD"
        side="Long" reportDate="20260619"/>
  </OpenPositions>
</FlexStatement></FlexStatements></FlexQueryResponse>
"""


def test_persist_is_idempotent_on_account_date_conid(sqlite_session: Session) -> None:
    service = IBKRPositionsImportService(sqlite_session)
    first = service.import_from_string(_POS_DOC)
    second = service.import_from_string(_POS_DOC)
    assert first.positions == 1
    assert second.positions == 0
    assert second.skipped == 1
    assert sqlite_session.query(InteractiveBrokersOpenPosition).count() == 1
