"""Unit tests for the account_balances model constraints."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError

from security_master.balances.rules import CATEGORIES
from security_master.storage.balance_models import AccountBalance

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = [
    pytest.mark.unit,
    pytest.mark.storage,
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]

_ENTITY = uuid.UUID("11111111-1111-4111-8111-111111111111")


def _row(**overrides: object) -> AccountBalance:
    fields: dict[str, object] = {
        "account_key": "pp:ibkr:0001",  # pragma: allowlist secret -- account key
        "display_name": "Example Brokerage Account",
        "entity_id": _ENTITY,
        "category": "Investments",
        "source": "manual_mark",
        "value": Decimal("100.10"),
        "currency": "USD",
        "as_of": date(2026, 6, 19),
        "entered_by": "tester",
        "entered_at": datetime(2026, 6, 20, tzinfo=UTC),
    }
    fields.update(overrides)
    return AccountBalance(**fields)


def test_valid_row_round_trips_as_decimal(sqlite_session: Session) -> None:
    sqlite_session.add(_row())
    sqlite_session.commit()
    stored = sqlite_session.query(AccountBalance).one()
    assert stored.value == Decimal("100.10")
    assert isinstance(stored.value, Decimal)
    assert stored.entity_id == _ENTITY
    assert "100.10" not in repr(stored)


def test_entity_id_is_required(sqlite_session: Session) -> None:
    sqlite_session.add(_row(entity_id=None))
    with pytest.raises(IntegrityError):
        sqlite_session.commit()


def test_unique_on_account_and_as_of(sqlite_session: Session) -> None:
    sqlite_session.add(_row())
    sqlite_session.commit()
    sqlite_session.add(_row(value=Decimal("5.00")))
    with pytest.raises(IntegrityError):
        sqlite_session.commit()


def test_same_account_on_a_different_date_is_allowed(sqlite_session: Session) -> None:
    sqlite_session.add(_row())
    sqlite_session.add(_row(as_of=date(2026, 6, 20)))
    sqlite_session.commit()
    assert sqlite_session.query(AccountBalance).count() == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"account_key": "ibkr:0001"},  # pragma: allowlist secret -- account key
        {"category": "Stocks"},
        {"currency": "US"},
    ],
)
def test_check_constraints_reject_bad_rows(
    sqlite_session: Session, overrides: dict[str, object]
) -> None:
    sqlite_session.add(_row(**overrides))
    with pytest.raises(IntegrityError):
        sqlite_session.commit()


def _category_list(source: str) -> list[str]:
    """Return the quoted names inside the single ``category IN (...)`` clause."""
    joined = re.sub(r'"\s*\n\s*"', "", source)
    matches = re.findall(r"category IN \(([^)]*)\)", joined)
    assert len(matches) == 1, matches
    return re.findall(r"'([^']*)'", matches[0])


def test_model_and_migration_category_lists_match() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "sql"
        / "versions"
        / "a1c4e7b90d21_account_balances.py"
    ).read_text(encoding="utf-8")
    expected = list(CATEGORIES)
    assert _category_list(migration) == expected
    (model_check,) = (
        c
        for c in AccountBalance.__table__.constraints
        if isinstance(c, CheckConstraint) and c.name == "ck_account_balances_category"
    )
    assert _category_list(str(model_check.sqltext)) == expected
