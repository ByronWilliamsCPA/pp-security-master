"""Integration tests for the IBKR Flex import service against real Postgres.

Skipped unless PPSM_TEST_DATABASE_URL or DATABASE_URL points at a reachable
PostgreSQL instance. The suite creates the schema, imports the sample, and
verifies idempotency by re-importing and confirming the row count is stable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from collections.abc import Generator

from security_master.extractor.ibkr_flex import IBKRFlexImportService

# Importing transaction_models registers InteractiveBrokersTransaction on
# Base.metadata so create_all() builds the target table. Base is re-exported
# from storage, but the transaction tables live in this module.
from security_master.storage.models import Base
from security_master.storage.transaction_models import InteractiveBrokersTransaction

SAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "sample_data" / "IBKR_Flex_Trades_sample.xml"
)

EXPECTED_TRADE_COUNT = 67


def _database_url() -> str | None:
    """Resolve the test database URL from the environment.

    Returns:
        The configured PostgreSQL URL, or None when neither env var is set.
    """
    return os.getenv("PPSM_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")


# The autouse conftest fixture sets DATABASE_URL to a test_user DSN that is not
# a running server, so prefer PPSM_TEST_DATABASE_URL and require it explicitly.
_DB_URL = os.getenv("PPSM_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.skipif(
        _DB_URL is None,
        reason="PPSM_TEST_DATABASE_URL not set; skipping real-Postgres test",
    ),
]


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide a session against a freshly created schema, rolled back after.

    Creates the ORM tables, yields a session, then rolls back and drops the
    IBKR table so the test leaves no committed residue behind.

    Yields:
        An active SQLAlchemy session bound to the test database.
    """
    url = _DB_URL
    assert url is not None  # guaranteed by skipif above
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    sess = Session(bind=connection)
    try:
        yield sess
    finally:
        sess.close()
        connection.close()
        # Drop only the table this suite populates to keep teardown isolated.
        InteractiveBrokersTransaction.__table__.drop(bind=engine, checkfirst=True)
        engine.dispose()


def _row_count(sess: Session) -> int:
    """Count rows in the IBKR transactions table.

    Args:
        sess: Active session to query.

    Returns:
        Number of rows in transactions_interactive_brokers.
    """
    return sess.execute(
        select(func.count()).select_from(InteractiveBrokersTransaction)
    ).scalar_one()


def test_import_persists_all_trades(session: Session) -> None:
    """Importing the sample inserts exactly 67 rows."""
    service = IBKRFlexImportService(session)
    summary = service.import_from_file(SAMPLE_PATH)

    assert summary.trades == EXPECTED_TRADE_COUNT
    assert _row_count(session) == EXPECTED_TRADE_COUNT


def test_reimport_is_idempotent(session: Session) -> None:
    """Re-importing the same file inserts nothing and keeps the count at 67."""
    service = IBKRFlexImportService(session)
    first = service.import_from_file(SAMPLE_PATH)
    assert first.trades == EXPECTED_TRADE_COUNT

    second = service.import_from_file(SAMPLE_PATH)
    assert second.trades == 0
    assert second.skipped == EXPECTED_TRADE_COUNT
    assert _row_count(session) == EXPECTED_TRADE_COUNT


def test_imported_row_fields(session: Session) -> None:
    """A spot-checked row (DBJA) persists with the expected mapped values."""
    service = IBKRFlexImportService(session)
    service.import_from_file(SAMPLE_PATH)

    dbja = session.execute(
        select(InteractiveBrokersTransaction).where(
            InteractiveBrokersTransaction.trade_id == "1000000007"
        )
    ).scalar_one()

    assert dbja.symbol == "DBJA"
    assert dbja.isin == "US45782C1365"
    assert dbja.transaction_type == "BUY"
    assert dbja.account_name == "Interactive Brokers"
    assert dbja.asset_class == "STK"
    assert dbja.created_at is not None  # Python-side default applied
