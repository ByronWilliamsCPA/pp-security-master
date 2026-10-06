"""Nightly IBKR totals: positions plus ending cash, one balance row per account.

For the latest ``ibkr_open_positions.report_date`` this sums each account's
``position_value`` plus its USD ending cash from ``ibkr_cash_report`` using
``Decimal`` and writes one ``account_balances`` row per account with source
``ibkr_flex``. The MVP is USD only: a non-USD row is rejected with a log line
and never converted.

Positions and cash arrive through two importers (``reconcile-positions`` loads
``OpenPosition`` snapshots, ``import-broker`` loads ``CashReport`` rows), and
the two are joined on an exact date: the cash rows must be dated the same day
as the latest position snapshot. Import both exports for the same statement
date, positions and cash in either order, before running the totals.

An account whose total cannot be computed exactly is withheld, not written
short. So is every registered IBKR account with no rows on the report date.
Every rejection is logged with the account key and a reason code; no log line
or message contains a balance or a full account number.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from enum import StrEnum
from itertools import chain
from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import func, select

from security_master.storage.position_models import (
    InteractiveBrokersCashReport,
    InteractiveBrokersOpenPosition,
)

from .rules import (
    IBKR_KEY_PREFIX,
    SOURCE_IBKR_FLEX,
    SUPPORTED_CURRENCY,
    BalanceRuleError,
    check_range,
    check_sign,
    ibkr_account_key,
    quantize_cents,
)
from .service import BalanceEntry, find_balance, write_balance

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date, datetime

    from sqlalchemy.orm import Session

    from .registry import AccountRegistry, RegisteredAccount

_LOGGER = logging.getLogger(__name__)

ENTERED_BY_NIGHTLY = "pp-master nightly-totals"

# Placeholder account keys for rejections that do not belong to one account.
UNDERIVABLE_KEY = "(underivable)"
RUN_KEY = "(run)"


class RejectReason(StrEnum):
    """Reason codes logged and recorded for each nightly-totals rejection."""

    BAD_ACCOUNT_NUMBER = "bad_account_number"
    AMBIGUOUS_SUFFIX = "ambiguous_suffix"
    UNMAPPED = "unmapped"
    NO_ROWS_ON_REPORT_DATE = "no_rows_on_report_date"
    CASH_DATE_AHEAD = "cash_date_ahead"
    MISSING_VALUE = "missing_value"
    INVALID_VALUE = "invalid_value"
    NON_USD_ROW = "non_usd_row"
    ACCOUNT_WITHHELD = "account_withheld"
    NO_USD_CASH_ROW = "no_usd_cash_row"
    OUT_OF_RANGE = "out_of_range"
    NEGATIVE_TOTAL = "negative_total"
    EXISTING_OTHER_SOURCE = "existing_other_source"


# Reason code for a rejected non-USD row; an account is only withheld when a
# separate account-level rejection follows it.
ROW_ONLY_REASON = RejectReason.NON_USD_ROW


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
    """An account (or row) withheld from the nightly totals, with the reason.

    ``account_key`` is a ``pp:`` key, or :data:`UNDERIVABLE_KEY` /
    :data:`RUN_KEY` when the rejection is not tied to one account.
    """

    account_key: str
    reason: RejectReason
    detail: str

    @property
    def withholds_account(self) -> bool:
        """Whether this rejection stopped a total from being written.

        Returns:
            False only for a dropped zero-valued non-USD row.
        """
        return self.reason != ROW_ONLY_REASON


@dataclass
class TotalsResult:
    """Outcome of one nightly totals run."""

    report_date: date | None = None
    inserted: int = 0
    updated: int = 0
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def accounts_withheld(self) -> int:
        """Count the distinct accounts (or run-level problems) withheld.

        Dropping a zero-valued non-USD row (``non_usd_row``) is logged but does
        not affect the total, so it is not counted. Several rejections for the
        same key count once; every un-keyable row is counted under one
        placeholder key, and so is a run-level date mismatch.

        Returns:
            Number of distinct keys with an account-level rejection.
        """
        return len({r.account_key for r in self.rejections if r.withholds_account})


class _Row(NamedTuple):
    """One position or cash amount for an account, with its currency."""

    currency: str
    value: Decimal | None


@dataclass
class _AccountData:
    """Raw rows collected for one derived account key."""

    account_numbers: set[str] = field(default_factory=set)
    positions: list[_Row] = field(default_factory=list)
    cash: list[_Row] = field(default_factory=list)


def _reject(
    result: TotalsResult, account_key: str, reason: RejectReason, detail: str
) -> None:
    """Record a rejection and emit its log line (no amounts, no account numbers).

    Args:
        result: The run result to append to.
        account_key: The ``pp:`` key, or a placeholder when none can be derived.
        reason: The machine-readable reason code.
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

    Positions and cash are matched on the exact same ``report_date``. Cash
    dated any other day is not read here, so a mismatched pair surfaces as
    ``no_usd_cash_row`` (or ``cash_date_ahead``), never as a short total.
    #ASSUME (external resource): the CashReport ``toDate`` equals the
    OpenPosition ``reportDate`` when both come from the same statement day.
    #VERIFY: test_cash_dated_a_day_later_is_not_joined, and compare the two
    dates on the first real pair of exports.

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
            _reject(result, UNDERIVABLE_KEY, RejectReason.BAD_ACCOUNT_NUMBER, str(exc))
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
            data.positions.append(_Row(currency.strip().upper(), value))
    for number, currency, cash in session.execute(
        select(
            InteractiveBrokersCashReport.account_number,
            InteractiveBrokersCashReport.currency,
            InteractiveBrokersCashReport.ending_cash,
        ).where(InteractiveBrokersCashReport.report_date == report_date)
    ):
        if (data := slot(number)) is not None:
            data.cash.append(_Row(currency.strip().upper(), cash))
    return by_key


def _ambiguous_keys(session: Session) -> set[str]:
    """Return keys that more than one account number maps to, on any date.

    Checking only the report date would let an account that appears on another
    date with the same last four inherit the key, entity, and history of a
    different account.

    Args:
        session: Active database session.

    Returns:
        Every ``pp:ibkr:<suffix>`` key derived from two or more account numbers
        across all position and cash rows.
    """
    numbers: dict[str, set[str]] = {}
    for column in (
        InteractiveBrokersOpenPosition.account_number,
        InteractiveBrokersCashReport.account_number,
    ):
        for number in session.scalars(select(column).distinct()):
            try:
                key = ibkr_account_key(number)
            except BalanceRuleError:
                continue  # rejected with a reason when it is on the report date
            numbers.setdefault(key, set()).add(number)
    return {key for key, found in numbers.items() if len(found) > 1}


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
    for section, rows, kept in (
        ("position", data.positions, positions),
        ("cash", data.cash, cash),
    ):
        for currency, value in rows:
            if value is None:
                _reject(
                    result,
                    key,
                    RejectReason.MISSING_VALUE,
                    f"{section} row has no value",
                )
                return None
            if not value.is_finite():
                _reject(
                    result,
                    key,
                    RejectReason.INVALID_VALUE,
                    f"{section} row is not finite",
                )
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
            kept.append(value)
    if withheld:
        _reject(
            result,
            key,
            RejectReason.ACCOUNT_WITHHELD,
            "a non-zero non-USD balance would leave the USD total short",
        )
        return None
    if not cash:
        _reject(
            result,
            key,
            RejectReason.NO_USD_CASH_ROW,
            "no USD cash report row dated the same day as the positions; "
            "import the CashReport for that date",
        )
        return None
    return positions, cash


def _check_cash_date(session: Session, report_date: date, result: TotalsResult) -> None:
    """Flag cash imported for a later date than the newest position snapshot.

    Totals are always computed for the newest position date. When cash has
    already arrived for a later day, the run would otherwise silently re-total
    the older day and exit 0, hiding that the positions import is behind.

    Args:
        session: Active database session.
        report_date: The newest position report date (the date being totalled).
        result: The run result to record the run-level rejection on.
    """
    latest_cash: date | None = session.scalar(
        select(func.max(InteractiveBrokersCashReport.report_date))
    )
    if latest_cash is not None and latest_cash > report_date:
        _reject(
            result,
            RUN_KEY,
            RejectReason.CASH_DATE_AHEAD,
            "cash is imported for a later date than the newest position "
            "snapshot; import positions for that date and re-run",
        )


def _total_account(
    session: Session,
    result: TotalsResult,
    report_date: date,
    account: RegisteredAccount,
    values: tuple[list[Decimal], list[Decimal]],
    now: datetime | None,
) -> None:
    """Check one account's total against the rules and write it, or reject it.

    Args:
        session: Active database session.
        result: The run result to update.
        report_date: The date being totalled (the row's as-of date).
        account: The account's registry entry.
        values: The account's USD ``(position_values, cash_values)``.
        now: Override for the entry timestamp (tests).
    """
    key = account.account_key
    total = sum_account_total(*values)
    try:
        check_range(total)
    except BalanceRuleError as exc:
        _reject(result, key, RejectReason.OUT_OF_RANGE, str(exc))
        return
    try:
        check_sign(total, account.category)
    except BalanceRuleError:
        _reject(
            result,
            key,
            RejectReason.NEGATIVE_TOTAL,
            "total is negative for a non-Cash account",
        )
        return
    existing = find_balance(session, key, report_date)
    if existing is not None and existing.source != SOURCE_IBKR_FLEX:
        _reject(
            result,
            key,
            RejectReason.EXISTING_OTHER_SOURCE,
            f"a {existing.source} balance already exists for this date",
        )
        return
    write_balance(
        session,
        existing,
        account,
        BalanceEntry(
            value=total,
            as_of=report_date,
            source=SOURCE_IBKR_FLEX,
            entered_by=ENTERED_BY_NIGHTLY,
        ),
        now=now,
    )
    if existing is None:
        result.inserted += 1
    else:
        result.updated += 1


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
    report_date: date | None = session.scalar(
        select(func.max(InteractiveBrokersOpenPosition.report_date))
    )
    result = TotalsResult(report_date=report_date)
    if report_date is None:
        return result

    _check_cash_date(session, report_date, result)
    by_key = _collect(session, report_date, result)
    ambiguous = _ambiguous_keys(session)
    for key in sorted(by_key):
        data = by_key[key]
        # #CRITICAL (data integrity): two accounts sharing a last-four suffix
        # would merge into one total, on this date or across dates.
        # #VERIFY: test_suffix_collision_is_rejected_not_merged and
        # test_suffix_collision_on_another_date_is_rejected.
        if key in ambiguous or len(data.account_numbers) > 1:
            _reject(
                result,
                key,
                RejectReason.AMBIGUOUS_SUFFIX,
                "two accounts share this key suffix",
            )
            continue
        account = registry.get(key)
        if account is None:
            _reject(
                result, key, RejectReason.UNMAPPED, "account is not in the registry"
            )
            continue
        values = _usd_values(key, data, result)
        if values is not None:
            _total_account(session, result, report_date, account, values, now)
    # A registered IBKR account with no rows at all would otherwise be skipped
    # silently, and the run would exit 0 with that account's total missing.
    for account in registry.accounts():
        if account.account_key.startswith(IBKR_KEY_PREFIX) and (
            account.account_key not in by_key
        ):
            _reject(
                result,
                account.account_key,
                RejectReason.NO_ROWS_ON_REPORT_DATE,
                "registered IBKR account has no position or cash rows on this date",
            )
    return result
