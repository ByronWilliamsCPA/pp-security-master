"""Unit tests for the AccountMapping ORM model."""

from datetime import date
from decimal import Decimal

import pytest

from security_master.storage.account_models import AccountMapping

pytestmark = [pytest.mark.storage]


def test_account_mapping_persists_and_reads_back(sqlite_session) -> None:
    sqlite_session.add(
        AccountMapping(
            account_number="U13052577",
            pp_group="Taxable",
            pp_account="IBKR Brokerage",
        )
    )
    sqlite_session.commit()

    row = (
        sqlite_session.query(AccountMapping).filter_by(account_number="U13052577").one()
    )
    assert row.pp_group == "Taxable"
    assert row.pp_account == "IBKR Brokerage"
    assert row.legal_entity_id is None
    assert row.created_at is not None


def _consolidated(**kw):
    from security_master.storage.transaction_models import ConsolidatedTransaction

    defaults = {
        "source_institution": "ibkr",
        "source_transaction_id": 1,
        "source_table": "transactions_interactive_brokers",
        "transaction_date": date(2024, 1, 2),
        "security_name": "ACME",
        "pp_group": "Taxable",
        "pp_account": "IBKR",
        "transaction_type": "BUY",
        "gross_amount": Decimal("100.00"),
        "net_amount": Decimal("100.00"),
        "currency": "USD",
    }
    defaults.update(kw)
    return ConsolidatedTransaction(**defaults)


def test_consolidated_unique_on_source_table_and_id(sqlite_session) -> None:
    from sqlalchemy.exc import IntegrityError

    sqlite_session.add(_consolidated(source_transaction_id=42))
    sqlite_session.commit()
    sqlite_session.add(_consolidated(source_transaction_id=42))
    with pytest.raises(IntegrityError):
        sqlite_session.commit()
    sqlite_session.rollback()
