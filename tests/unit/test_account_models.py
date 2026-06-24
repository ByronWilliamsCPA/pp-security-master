"""Unit tests for the AccountMapping ORM model."""

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
