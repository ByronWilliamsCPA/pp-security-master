"""Feed the normalizer, then assert v_transactions_for_pp_export labels rows.

Requires PostgreSQL (the view uses CONCAT). Skips when PPSM_TEST_DATABASE_URL /
DATABASE_URL is unset or unreachable, mirroring
tests/integration/test_ibkr_flex_import.py.

The conftest ``setup_test_environment`` autouse fixture always sets DATABASE_URL
to a localhost value, so "is the URL set" cannot gate this test; probe
reachability instead and skip (not error) when no database answers.
"""

import os
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

pytestmark = [pytest.mark.integration, pytest.mark.database]


def _url() -> str | None:
    return os.getenv("PPSM_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")


def test_export_view_returns_pp_labels_when_fed() -> None:
    from security_master.storage import (  # noqa: F401
        account_models,
        entity,
        pp_models,
        transaction_models,
    )
    from security_master.storage.account_models import AccountMapping
    from security_master.storage.models import Base, SecurityMaster
    from security_master.storage.transaction_models import InteractiveBrokersTransaction
    from security_master.storage.transaction_normalizer import TransactionNormalizer
    from security_master.storage.views import create_all_views, drop_all_views

    url = _url()
    if url is None:
        pytest.skip("No PostgreSQL test database configured")

    engine = create_engine(url)
    try:
        engine.connect().close()
    except OperationalError:
        engine.dispose()
        pytest.skip(
            "PostgreSQL not reachable at the configured URL; "
            "integration test requires a live database"
        )

    # Destructive-target guard: this test runs Base.metadata.drop_all on the
    # resolved URL. The reachability probe protects against an ABSENT database,
    # not a present-but-wrong one. The conftest autouse fixture always sets
    # DATABASE_URL to a localhost value, so a developer pointing it at a real
    # database would otherwise have every table wiped. Refuse to drop unless the
    # database name marks it disposable (CI and conftest both use "test_db").
    db_name = (engine.url.database or "").lower()
    if "test" not in db_name:
        engine.dispose()
        pytest.skip(
            f"refusing to run destructive drop_all against non-test database "
            f"'{engine.url.database}'; point PPSM_TEST_DATABASE_URL at a "
            f"disposable test database (name must contain 'test')"
        )

    # Drop views before tables: views depend on tables so table drop fails when
    # views exist (e.g. left behind by a previous interrupted run).
    drop_all_views(engine)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    create_all_views(engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add(
            AccountMapping(account_number="U1", pp_group="Taxable", pp_account="IBKR")
        )
        session.add(SecurityMaster(name="Acme", isin="US0000000001", symbol="ACME"))
        session.add(
            InteractiveBrokersTransaction(
                record_type="TRADE",
                transaction_date=date(2024, 1, 2),
                security_name="ACME",
                isin="US0000000001",
                symbol="ACME",
                transaction_type="BUY",
                quantity=Decimal(10),
                amount=Decimal(1000),
                currency="USD",
                account_name="IBKR",
                account_number="U1",
                import_batch_id="b",
            )
        )
        session.commit()

        TransactionNormalizer(session).normalize_all()

        rows = session.execute(
            text(
                "SELECT transaction_type, pp_transaction_type "
                "FROM v_transactions_for_pp_export"
            )
        ).all()
        labels = {r[0]: r[1] for r in rows}
        assert labels.get("BUY") == "Kauf"
    finally:
        # Close the session first to release any open transaction before
        # dropping views and tables. An open session holds locks that block
        # DROP VIEW, causing a deadlock in the cleanup sequence.
        session.close()
        drop_all_views(engine)
        Base.metadata.drop_all(engine)
        engine.dispose()
