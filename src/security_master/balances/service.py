"""Write and read ``account_balances`` rows: manual marks and listings.

Functions here flush but never commit; the caller owns the transaction. No
error message or log line built here contains a balance value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from security_master.storage.balance_models import AccountBalance

from .rules import (
    SOURCE_IBKR_FLEX,
    SOURCE_MANUAL_MARK,
    SUPPORTED_CURRENCY,
    BalanceRuleError,
    check_range,
    format_money,
    quantize_cents,
    validate_account_key,
    validate_source,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy.orm import Session

    from .registry import AccountRegistry, RegisteredAccount

# Sources an operator may record by hand. ibkr_flex is written only by the
# nightly totals job so the label always means "computed from the broker file".
MANUAL_SOURCES = (SOURCE_MANUAL_MARK, "simplefin", "plaid")

_MAX_ENTERED_BY = 100
_MAX_NOTE = 500


@dataclass(frozen=True)
class BalanceRow:
    """One registry account with its balance, or ``None`` fields when unmarked."""

    account_key: str
    display_name: str
    entity_id: str
    category: str
    value: str | None
    currency: str | None
    as_of: date | None
    source: str | None
    entered_by: str | None

    def as_dict(self) -> dict[str, str | None]:
        """Serialize for JSON output with the value as a decimal string.

        Returns:
            A flat mapping of strings (or None); dates are ISO 8601.
        """
        return {
            "account_key": self.account_key,
            "display_name": self.display_name,
            "entity_id": self.entity_id,
            "category": self.category,
            "value": self.value,
            "currency": self.currency,
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "source": self.source,
            "entered_by": self.entered_by,
        }


def find_balance(
    session: Session, account_key: str, as_of: date
) -> AccountBalance | None:
    """Return the balance row for an account and as-of date, if any.

    Args:
        session: Active database session.
        account_key: The ``pp:``-prefixed account key.
        as_of: The as-of date.

    Returns:
        The matching row, or None.
    """
    return session.scalars(
        select(AccountBalance).where(
            AccountBalance.account_key == account_key,
            AccountBalance.as_of == as_of,
        )
    ).one_or_none()


def write_balance(
    session: Session,
    existing: AccountBalance | None,
    account: RegisteredAccount,
    *,
    value: Decimal,
    as_of: date,
    source: str,
    entered_by: str,
    note: str | None,
    now: datetime | None = None,
) -> AccountBalance:
    """Insert a balance row, or update ``existing`` in place, and flush.

    Registry fields (display name, entity, category) are snapshotted onto the row
    at write time. Currency is always USD in the MVP.

    Args:
        session: Active database session.
        existing: The row to overwrite, or None to insert.
        account: The registry entry the balance belongs to.
        value: The balance, already quantized to two places.
        as_of: The as-of date.
        source: The source label recorded on the row.
        entered_by: Who or what wrote the row.
        note: Optional free-text note.
        now: Override for the entry timestamp (tests); defaults to UTC now.

    Returns:
        The persisted row.
    """
    row = existing or AccountBalance(account_key=account.account_key, as_of=as_of)
    row.display_name = account.display_name
    row.entity_id = account.entity_id
    row.category = account.category
    row.source = source
    row.value = value
    row.currency = SUPPORTED_CURRENCY
    row.entered_by = entered_by
    row.entered_at = now or datetime.now(UTC)
    row.note = note
    session.add(row)
    session.flush()
    return row


def set_manual_balance(
    session: Session,
    registry: AccountRegistry,
    *,
    account_key: str,
    value: Decimal,
    as_of: date,
    source: str,
    note: str | None,
    entered_by: str,
    replace: bool = False,
    today: date | None = None,
    now: datetime | None = None,
) -> AccountBalance:
    """Record a manual balance mark, attributed to who entered it.

    Args:
        session: Active database session.
        registry: The account registry; the account must be mapped in it.
        account_key: The ``pp:``-prefixed account key.
        value: The balance in USD, at most two decimal places.
        as_of: The statement date the value is as of; not in the future.
        source: One of :data:`MANUAL_SOURCES`.
        note: Optional free-text note (at most 500 characters).
        entered_by: Who is entering the mark; recorded on the row.
        replace: Overwrite an existing row for the same account and date.
        today: Override for today's date (tests); defaults to UTC today.
        now: Override for the entry timestamp (tests).

    Returns:
        The persisted row.

    Raises:
        BalanceRuleError: When an input violates the field rules, the account
            already has a mark for that date and ``replace`` is False, or the
            account is not in the registry.
    """
    validate_account_key(account_key)
    validate_source(source)
    if source not in MANUAL_SOURCES:
        msg = f"source must be one of: {', '.join(MANUAL_SOURCES)}"
        raise BalanceRuleError(msg)
    account = _require_account(registry, account_key)
    if as_of > (today or datetime.now(UTC).date()):
        msg = "as-of date must not be in the future"
        raise BalanceRuleError(msg)
    value = check_range(quantize_cents(value))
    # Negative values are overdrafts, which only make sense for cash accounts.
    if value < 0 and account.category != "Cash":
        msg = "a negative value is only allowed for Cash accounts (overdraft)"
        raise BalanceRuleError(msg)
    who = entered_by.strip()
    if not who or len(who) > _MAX_ENTERED_BY:
        msg = f"entered-by must be 1 to {_MAX_ENTERED_BY} characters"
        raise BalanceRuleError(msg)
    clean_note = note.strip() if note else None
    if clean_note and len(clean_note) > _MAX_NOTE:
        msg = f"note must be at most {_MAX_NOTE} characters"
        raise BalanceRuleError(msg)

    existing = find_balance(session, account_key, as_of)
    if existing is not None and not replace:
        msg = (
            f"{account_key} already has a balance for {as_of.isoformat()}; "
            "pass --replace to correct it"
        )
        raise BalanceRuleError(msg)
    return write_balance(
        session,
        existing,
        account,
        value=value,
        as_of=as_of,
        source=source,
        entered_by=who,
        note=clean_note or None,
        now=now,
    )


def _require_account(registry: AccountRegistry, account_key: str) -> RegisteredAccount:
    """Return the registry entry or raise a rule error naming only the key.

    Args:
        registry: The account registry.
        account_key: The account key to look up.

    Returns:
        The registry entry.

    Raises:
        BalanceRuleError: When the key is not mapped.
    """
    account = registry.get(account_key)
    if account is None:
        msg = f"{account_key} is not in the account registry"
        raise BalanceRuleError(msg)
    return account


def list_balances(
    session: Session,
    registry: AccountRegistry,
    *,
    as_of: date | None = None,
) -> list[BalanceRow]:
    """List every mapped account with its balance.

    Without ``as_of`` each account shows its most recent row; with it, the row
    for exactly that date. Accounts with no matching row are still listed, with
    empty balance fields, so a missing mark is visible rather than silent.

    Args:
        session: Active database session.
        registry: The account registry; defines which accounts are listed.
        as_of: Optional exact as-of date filter.

    Returns:
        One row per registry account, sorted by account key.
    """
    rows: list[BalanceRow] = []
    for account in registry.accounts():
        query = select(AccountBalance).where(
            AccountBalance.account_key == account.account_key
        )
        if as_of is not None:
            query = query.where(AccountBalance.as_of == as_of)
        latest = session.scalars(
            query.order_by(AccountBalance.as_of.desc()).limit(1)
        ).first()
        rows.append(
            BalanceRow(
                account_key=account.account_key,
                display_name=account.display_name,
                entity_id=str(account.entity_id),
                category=account.category,
                value=format_money(latest.value) if latest else None,
                currency=latest.currency if latest else None,
                as_of=latest.as_of if latest else None,
                source=latest.source if latest else None,
                entered_by=latest.entered_by if latest else None,
            )
        )
    return rows


__all__ = [
    "MANUAL_SOURCES",
    "SOURCE_IBKR_FLEX",
    "BalanceRow",
    "find_balance",
    "list_balances",
    "set_manual_balance",
    "write_balance",
]
