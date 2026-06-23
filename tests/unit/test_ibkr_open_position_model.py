"""Unit tests for the IBKR open-position snapshot ORM model."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

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
