"""CLI smoke test for normalize-transactions against an in-memory schema."""

from datetime import date
from decimal import Decimal

import pytest
from click.testing import CliRunner

pytestmark = [pytest.mark.extractor]


def test_normalize_transactions_cli_reports_summary(monkeypatch) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from security_master import cli
    from security_master.storage import (  # noqa: F401
        account_models,
        entity,
        pp_models,
        transaction_models,
    )
    from security_master.storage.models import Base
    from security_master.storage.transaction_models import InteractiveBrokersTransaction

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    seed = factory()
    seed.add(
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
    seed.commit()
    seed.close()

    monkeypatch.setattr(cli, "create_db_engine", lambda _url: engine)
    monkeypatch.setattr(cli, "get_session_factory", lambda _engine: factory)

    result = CliRunner().invoke(cli.app, ["normalize-transactions"])
    assert result.exit_code == 0, result.output
    assert "normalized 1" in result.output
