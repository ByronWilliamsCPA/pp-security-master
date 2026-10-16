"""Shared helpers for the account-balance tests (made-up data only)."""

from __future__ import annotations

from datetime import date
from itertools import count
from pathlib import Path
from typing import TYPE_CHECKING

from security_master.balances.registry import load_registry
from security_master.storage.position_models import (
    InteractiveBrokersCashReport,
    InteractiveBrokersOpenPosition,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy.orm import Session

    from security_master.balances.registry import AccountRegistry

EXAMPLE_SEED = (
    Path(__file__).resolve().parents[2] / "seeds" / "account_registry.example.yaml"
)

# Made-up IBKR account ids whose last four map to the example seed keys.
ACCT_INVEST = "U9990001"  # pp:ibkr:0001, Investments
ACCT_IRA = "U9990002"  # pp:ibkr:0002, Retirement
REPORT_DATE = date(2026, 6, 19)

_conids = count(1000)


def example_registry() -> AccountRegistry:
    """Load the shipped made-up example registry.

    Returns:
        The validated example registry.
    """
    return load_registry(EXAMPLE_SEED)


def add_position(
    session: Session,
    account: str,
    value: Decimal | None,
    *,
    currency: str = "USD",
    report_date: date = REPORT_DATE,
) -> None:
    """Stage one open-position snapshot row with a unique conid.

    Args:
        session: Active session.
        account: Made-up IBKR account id.
        value: Position market value, or None.
        currency: Position currency.
        report_date: Snapshot date.
    """
    conid = str(next(_conids))
    session.add(
        InteractiveBrokersOpenPosition(
            account_number=account,
            report_date=report_date,
            conid=conid,
            security_name=f"EXAMPLE SECURITY {conid}",
            position=1,
            position_value=value,
            currency=currency,
            import_batch_id="test-batch",
        )
    )


def add_cash(
    session: Session,
    account: str,
    ending_cash: Decimal,
    *,
    currency: str = "USD",
    report_date: date = REPORT_DATE,
) -> None:
    """Stage one CashReport ending-cash row.

    Args:
        session: Active session.
        account: Made-up IBKR account id.
        ending_cash: Ending cash in ``currency``.
        currency: Cash currency.
        report_date: Report date.
    """
    session.add(
        InteractiveBrokersCashReport(
            account_number=account,
            report_date=report_date,
            currency=currency,
            ending_cash=ending_cash,
            import_batch_id="test-batch",
        )
    )
