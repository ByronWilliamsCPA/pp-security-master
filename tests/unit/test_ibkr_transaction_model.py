"""Unit test: the IBKR transaction model carries the new record-type columns."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from security_master.storage.transaction_models import InteractiveBrokersTransaction


@pytest.mark.unit
@pytest.mark.database
def test_non_trade_columns_round_trip(sqlite_session) -> None:
    row = InteractiveBrokersTransaction(
        record_type="CORP_ACTION",
        transaction_date=date(2024, 1, 10),
        transaction_id="8000000020",
        action_id="700000020",
        action_description="MRGR MERGED(Acquisition)",
        security_name="MRGR",
        transaction_type="TC",
        quantity=Decimal(-4156),
        amount=Decimal("-122532.67"),
        proceeds=Decimal("122532.667322"),
        realized_pnl=Decimal("2535.167322"),
        figi="BBG000000099",
        conid="222222",
        currency="USD",
        account_name="Interactive Brokers",
        import_batch_id="test-batch",
    )
    sqlite_session.add(row)
    sqlite_session.commit()
    fetched = sqlite_session.query(InteractiveBrokersTransaction).one()
    assert fetched.record_type == "CORP_ACTION"
    assert fetched.proceeds == Decimal("122532.667322")
    assert fetched.action_description == "MRGR MERGED(Acquisition)"
