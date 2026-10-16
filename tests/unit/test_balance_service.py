"""Service-level tests for manual marks and listings (made-up data only).

The CLI rejects some inputs before the service sees them (``click.Choice`` for
the source, ``parse_money`` for the value), so these call the public service
functions directly to prove their own guards.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from security_master.balances.registry import parse_registry
from security_master.balances.rules import BalanceRuleError
from security_master.balances.service import (
    BalanceEntry,
    list_balances,
    set_manual_balance,
    write_balance,
)
from security_master.storage.balance_models import AccountBalance

from .balance_support import example_registry

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

_TODAY = date(2026, 6, 20)
_KEY = "pp:ibkr:0001"  # pragma: allowlist secret -- account key
_UNKNOWN_KEY = "pp:ibkr:0009"  # pragma: allowlist secret -- account key


def _mark(session: Session, **overrides: Any) -> AccountBalance:
    fields: dict[str, Any] = {
        "account_key": _KEY,
        "value": Decimal("10.00"),
        "as_of": date(2026, 6, 19),
        "source": "manual_mark",
        "note": None,
        "entered_by": "example.operator",
        "today": _TODAY,
    }
    fields.update(overrides)
    return set_manual_balance(session, example_registry(), **fields)


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"source": "ibkr_flex"}, "source must be one of"),
        ({"value": Decimal("1.005")}, "two decimal places"),
        ({"value": Decimal("NaN")}, "finite"),
        ({"value": Decimal("Infinity")}, "finite"),
        ({"value": Decimal("1e16")}, "range"),
        ({"value": Decimal("-1.00")}, "Cash"),
        ({"entered_by": "x" * 101}, "entered-by"),
        ({"entered_by": "   "}, "entered-by"),
        ({"note": "n" * 501}, "note"),
        ({"as_of": date(2026, 6, 21)}, "future"),
        ({"account_key": _UNKNOWN_KEY}, "not in the account registry"),
    ],
)
def test_service_guards_reject_bad_input(
    sqlite_session: Session, overrides: dict[str, Any], fragment: str
) -> None:
    with pytest.raises(BalanceRuleError, match=fragment):
        _mark(sqlite_session, **overrides)
    assert sqlite_session.query(AccountBalance).count() == 0


def test_boundaries_are_accepted(sqlite_session: Session) -> None:
    row = _mark(
        sqlite_session,
        as_of=_TODAY,
        entered_by="x" * 100,
        note="n" * 500,
        value=Decimal("1.5"),
    )
    assert row.value == Decimal("1.50")
    assert row.as_of == _TODAY


def test_write_balance_enforces_the_value_rules(sqlite_session: Session) -> None:
    account = example_registry().get(_KEY)
    assert account is not None
    for bad, fragment in ((Decimal("-1.00"), "Cash"), (Decimal("0.001"), "two")):
        entry = BalanceEntry(
            value=bad, as_of=_TODAY, source="manual_mark", entered_by="x"
        )
        with pytest.raises(BalanceRuleError, match=fragment):
            write_balance(sqlite_session, None, account, entry)
    assert sqlite_session.query(AccountBalance).count() == 0


def test_list_reports_the_snapshot_recorded_on_the_row(sqlite_session: Session) -> None:
    """A later registry rename must not rewrite what an old row says."""
    _mark(sqlite_session)
    sqlite_session.commit()
    renamed = parse_registry(
        """
accounts:
  - account_key: "pp:ibkr:0001"  # pragma: allowlist secret -- account key
    entity_id: "22222222-2222-4222-8222-222222222222"
    display_name: "Renamed Example Account"
    category: "Retirement"
  - account_key: "pp:ibkr:0002"  # pragma: allowlist secret -- account key
    entity_id: "22222222-2222-4222-8222-222222222222"
    display_name: "Unmarked Example Account"
    category: "Retirement"
"""
    )
    rows = {r.account_key: r for r in list_balances(sqlite_session, renamed)}
    marked = rows[_KEY]
    assert marked.display_name == "Example Brokerage Account"
    assert marked.category == "Investments"
    assert marked.entity_id == "11111111-1111-4111-8111-111111111111"
    unmarked = rows["pp:ibkr:0002"]
    assert unmarked.display_name == "Unmarked Example Account"
    assert unmarked.value is None


def test_replace_updates_attribution_and_timestamp(sqlite_session: Session) -> None:
    first = datetime(2026, 6, 20, 1, tzinfo=UTC)
    second = datetime(2026, 6, 20, 2, tzinfo=UTC)
    _mark(sqlite_session, now=first)
    row = _mark(
        sqlite_session,
        value=Decimal("12.00"),
        entered_by="second.operator",
        replace=True,
        now=second,
    )
    assert (row.value, row.entered_by) == (Decimal("12.00"), "second.operator")
    assert row.entered_at == second
