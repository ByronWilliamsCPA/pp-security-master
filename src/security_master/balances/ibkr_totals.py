"""Nightly IBKR totals: positions plus ending cash, one balance row per account.

For the latest ``ibkr_open_positions.report_date`` this sums each account's
``position_value`` plus its USD ending cash from ``ibkr_cash_report`` using
``Decimal`` and writes one ``account_balances`` row per account with source
``ibkr_flex``. The MVP is USD only: a non-USD row is rejected with a log line
and never converted.

An account whose total cannot be computed exactly is withheld, not written
short. Every rejection is logged with the account key and a reason code; no log
line or message contains a balance or a full account number.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from itertools import chain
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from security_master.storage.position_models import (
    InteractiveBrokersCashReport,
    InteractiveBrokersOpenPosition,
)

from .rules import (
    SOURCE_IBKR_FLEX,
    SUPPORTED_CURRENCY,
    BalanceRuleError,
    check_range,
    ibkr_account_key,
    quantize_cents,
)
from .service import find_balance, write_balance

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date, datetime

    from sqlalchemy.orm import Session

    from .registry import AccountRegistry

_LOGGER = logging.getLogger(__name__)

ENTERED_BY_NIGHTLY = "pp-master nightly-totals"

# Reason code for a rejected non-USD row; an account is only withheld when a
# separate account-level rejection follows it.
ROW_ONLY_REASON = "non_usd_row"


def sum_account_total(
    position_values: Iterable[Decimal], cash_values: Iterable[Decimal]
) -> Decimal:
    """Sum positions plus cash exactly, then round once to cents.

    Addition runs in a 60-digit context so no intermediate sum is rounded; the
    only rounding is the final half-up quantization to two places. Values must
    be finite Decimals (callers reject NaN and infinities beforehand).

    Args:
        position_values: Position market values in one currency.
        cash_values: Ending cash values in the same currency.

    Returns:
        The total quantized to two decimal places.
    """
    with localcontext() as ctx:
        ctx.prec = 60
        total = sum(chain(position_values, cash_values), Decimal(0))
    return quantize_cents(total)


@dataclass(frozen=True)
class Rejection:
    """An account (or row) withheld from the nightly totals, with the reason."""

    account_key: str
    reason: str
    detail: str


@dataclass
class TotalsResult:
    """Outcome of one nightly totals run."""

    report_date: date | None = None
    inserted: int = 0
    updated: int = 0
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def accounts_withheld(self) -> int:
        """Count rejections that stopped an account's total from being written.

        Dropping a zero-valued non-USD row (``non_usd_row``) is logged but does
        not affect the total, so it is not counted here.

        Returns:
            Number of account-level rejections.
        """
        return sum(1 for r in self.rejections if r.reason != ROW_ONLY_REASON)


@dataclass
class _AccountData:
    """Raw rows collected for one derived account key."""

    account_numbers: set[str] = field(default_factory=set)
    positions: list[tuple[str, Decimal | None]] = field(default_factory=list)
    cash: list[tuple[str, Decimal]] = field(default_factory=list)


def _reject(result: TotalsResult, account_key: str, reason: str, detail: str) -> None:
    """Record a rejection and emit its log line (no amounts, no account numbers).

    Args:
        result: The run result to append to.
        account_key: The ``pp:`` key, or a placeholder when none can be derived.
        reason: Short machine-readable reason code.
        detail: Human-readable explanation without balances.
    """
    result.rejections.append(Rejection(account_key, reason, detail))
    _LOGGER.warning(
        "balance rejected: account=%s reason=%s detail=%s", account_key, reason, detail
    )


def _collect(
    session: Session, report_date: date, result: TotalsResult
) -> dict[str, _AccountData]:
    """Group the report date's position and cash rows by derived account key.

    Args:
        session: Active database session.
        report_date: The report date to total.
        result: The run result, used to record un-keyable rows.

    Returns:
        Raw rows per ``pp:ibkr:<suffix>`` key.
    """
    by_key: dict[str, _AccountData] = {}

    def slot(account_number: str) -> _AccountData | None:
        try:
            key = ibkr_account_key(account_number)
        except BalanceRuleError as exc:
            _reject(result, "(underivable)", "bad_account_number", str(exc))
            return None
        data = by_key.setdefault(key, _AccountData())
        data.account_numbers.add(account_number)
        return data

    for number, currency, value in session.execute(
        select(
            InteractiveBrokersOpenPosition.account_number,
            InteractiveBrokersOpenPosition.currency,
            InteractiveBrokersOpenPosition.position_value,
        ).where(InteractiveBrokersOpenPosition.report_date == report_date)
    ):
        if (data := slot(number)) is not None:
            data.positions.append((currency.strip().upper(), value))
    for number, currency, cash in session.execute(
        select(
            InteractiveBrokersCashReport.account_number,
            InteractiveBrokersCashReport.currency,
            InteractiveBrokersCashReport.ending_cash,
        ).where(InteractiveBrokersCashReport.report_date == report_date)
    ):
        if (data := slot(number)) is not None:
            data.cash.append((currency.strip().upper(), cash))
    return by_key


def _usd_values(
    key: str,
    data: _AccountData,
    result: TotalsResult,
) -> tuple[list[Decimal], list[Decimal]] | None:
    """Filter an account's rows to exact USD values, or reject the account.

    Args:
        key: The account key, for log lines.
        data: The account's raw rows.
        result: The run result to record rejections on.

    Returns:
        ``(position_values, cash_values)`` in USD, or None when the account is
        withheld.
    """
    positions: list[Decimal] = []
    cash: list[Decimal] = []
    withheld = False
    for section, rows in (("position", data.positions), ("cash", data.cash)):
        for currency, value in rows:
            if value is None:
                _reject(result, key, "missing_value", f"{section} row has no value")
                return None
            if not value.is_finite():
                _reject(result, key, "invalid_value", f"{section} row is not finite")
                return None
            if currency != SUPPORTED_CURRENCY:
                # MVP is USD only: never convert. A zero row contributes nothing,
                # so it is dropped; a non-zero one would leave the total short.
                _reject(
                    result,
                    key,
                    ROW_ONLY_REASON,
                    f"{section} row in {currency}; USD only, not converted",
                )
                withheld = withheld or value != 0
                continue
            (positions if section == "position" else cash).append(value)
    if withheld:
        _reject(
            result,
            key,
            "account_withheld",
            "a non-zero non-USD balance would leave the USD total short",
        )
        return None
    if not cash:
        _reject(result, key, "no_usd_cash_row", "no USD cash report row on this date")
        return None
    return positions, cash


def compute_nightly_totals(
    session: Session,
    registry: AccountRegistry,
    *,
    now: datetime | None = None,
) -> TotalsResult:
    """Total every IBKR account for the latest report date and write the rows.

    Flushes writes but does not commit; the caller owns the transaction.

    Args:
        session: Active database session.
        registry: The account registry; unmapped accounts are rejected.
        now: Override for the entry timestamp (tests).

    Returns:
        A :class:`TotalsResult` with counts, the report date, and rejections.
    """
    result = TotalsResult()
    result.report_date = session.scalar(
        select(func.max(InteractiveBrokersOpenPosition.report_date))
    )
    if result.report_date is None:
        return result

    by_key = _collect(session, result.report_date, result)
    for key in sorted(by_key):
        data = by_key[key]
        # #CRITICAL (data integrity): two accounts sharing a last-four suffix
        # would merge into one total. #VERIFY: test_suffix_collision_is_rejected.
        if len(data.account_numbers) > 1:
            _reject(
                result, key, "ambiguous_suffix", "two accounts share this key suffix"
            )
            continue
        account = registry.get(key)
        if account is None:
            _reject(result, key, "unmapped", "account is not in the registry")
            continue
        values = _usd_values(key, data, result)
        if values is None:
            continue
        total = sum_account_total(*values)
        try:
            check_range(total)
        except BalanceRuleError as exc:
            _reject(result, key, "out_of_range", str(exc))
            continue
        # Negative totals are only valid as overdrafts on Cash accounts.
        if total < 0 and account.category != "Cash":
            _reject(
                result,
                key,
                "negative_total",
                "total is negative for a non-Cash account",
            )
            continue
        existing = find_balance(session, key, result.report_date)
        if existing is not None and existing.source != SOURCE_IBKR_FLEX:
            _reject(
                result,
                key,
                "existing_other_source",
                f"a {existing.source} balance already exists for this date",
            )
            continue
        write_balance(
            session,
            existing,
            account,
            value=total,
            as_of=result.report_date,
            source=SOURCE_IBKR_FLEX,
            entered_by=ENTERED_BY_NIGHTLY,
            note=None,
            now=now,
        )
        if existing is None:
            result.inserted += 1
        else:
            result.updated += 1
    return result
