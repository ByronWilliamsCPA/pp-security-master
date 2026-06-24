"""Pure IBKR Layer-1 -> Layer-2 mapping and idempotent persistence.

The mapping function ``normalize_ibkr_row`` is pure (no I/O) so the gate-critical
vocabulary can be unit-tested against synthetic Layer-1 rows. The canonical
``transaction_type`` vocabulary is exactly the set the export view
``v_transactions_for_pp_export`` recognizes in its CASE; any other value would be
emitted to Portfolio Performance untranslated.

#CRITICAL (data integrity): Layer-2 ``quantity`` is stored as a POSITIVE magnitude
with direction carried by ``transaction_type``. The holdings view derives net
shares as +qty for inflow types and -qty for outflow types; storing signed
quantity would double-negate every sell.
#VERIFY: the reconciliation-invariant test asserts Layer-2 net shares equal the
SP2 reconstruction for the DBJA/dividend anchors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from security_master.storage.transaction_models import (
        InteractiveBrokersTransaction,
    )

SOURCE_TABLE_IBKR = "transactions_interactive_brokers"
SOURCE_INSTITUTION_IBKR = "ibkr"
# Consumed by the persistence service (account resolution) in a later task.
UNMAPPED_GROUP = "Unmapped"
UNKNOWN_ACCOUNT = "UNKNOWN"

# The 7 literals v_transactions_for_pp_export keys on (storage/views.py CASE).
CANONICAL_TYPES: frozenset[str] = frozenset(
    {"BUY", "SELL", "DIV", "DEPOSIT", "WITHDRAWAL", "TRANSFER_IN", "TRANSFER_OUT"}
)
_INFLOW: frozenset[str] = frozenset({"BUY", "DEPOSIT", "TRANSFER_IN"})
_OUTFLOW: frozenset[str] = frozenset({"SELL", "WITHDRAWAL", "TRANSFER_OUT"})


@dataclass(frozen=True)
class NormalizedRow:
    """The broker-agnostic field values for one Layer-2 row, pre-resolution."""

    transaction_type: str
    transaction_date: date
    security_name: str
    isin: str | None
    symbol: str | None
    quantity: Decimal | None
    price: Decimal | None
    gross_amount: Decimal
    net_amount: Decimal
    fees_total: Decimal | None
    currency: str
    settlement_date: date | None
    account_number: str | None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkipReason:
    """A Layer-1 row deliberately not represented in Layer-2, with a reason."""

    reason: str


def _fees_total(row: InteractiveBrokersTransaction) -> Decimal | None:
    parts = [
        row.commission,
        row.fees,
        row.ib_commission,
        row.regulatory_fees,
        row.exchange_fees,
    ]
    present = [abs(p) for p in parts if p is not None]
    if not present:
        return None
    return sum(present, Decimal(0))


def _amounts(row: InteractiveBrokersTransaction) -> tuple[Decimal, Decimal]:
    # #ASSUME (financial): net = abs(amount); gross = abs(proceeds) when present,
    # else abs(amount). SP3 does not reconcile price/value beyond classification.
    # #VERIFY: anchor tests assert the merger row carries non-zero proceeds.
    net = abs(row.amount)
    gross = abs(row.proceeds) if row.proceeds is not None else net
    return gross, net


def _base(
    row: InteractiveBrokersTransaction,
    transaction_type: str,
    quantity: Decimal | None,
    notes: list[str],
) -> NormalizedRow:
    gross, net = _amounts(row)
    return NormalizedRow(
        transaction_type=transaction_type,
        transaction_date=row.transaction_date,
        security_name=row.security_name,
        isin=row.isin,
        symbol=row.symbol,
        quantity=quantity,
        price=row.price,
        gross_amount=gross,
        net_amount=net,
        fees_total=_fees_total(row),
        currency=row.currency,
        settlement_date=row.settlement_date,
        account_number=row.account_number,
        notes=notes,
    )


def _normalize_trade(row: InteractiveBrokersTransaction) -> NormalizedRow | SkipReason:
    qty = row.quantity if row.quantity is not None else Decimal(0)
    ttype = "BUY" if qty >= 0 else "SELL"
    return _base(row, ttype, abs(qty), [])


def _normalize_cash(row: InteractiveBrokersTransaction) -> NormalizedRow | SkipReason:
    label = f"{row.transaction_type or ''} {row.dividend_type or ''}".lower()
    if "reinvest" in label:
        # Cash that funds a reinvested distribution; the purchase TRADE row carries
        # the shares. A DIV row carries no quantity, so including it would not
        # double-count shares either; this skip keeps the cash record out per spec.
        return SkipReason("reinvestment_funding")
    if "dividend" in label or "payment in lieu" in label:
        return _base(row, "DIV", None, [])
    if "deposit" in label or "withdrawal" in label:
        # IBKR often uses a single combined "Deposits/Withdrawals" type, so the
        # direction comes from the amount sign, not the label text.
        ttype = "WITHDRAWAL" if row.amount < 0 else "DEPOSIT"
        return _base(row, ttype, None, [])
    if any(k in label for k in ("interest", "fee", "tax")):
        return SkipReason("fee_interest")
    return SkipReason("unknown_cash_type")


def _normalize_corp_action(
    row: InteractiveBrokersTransaction,
) -> NormalizedRow | SkipReason:
    label = f"{row.transaction_type or ''} {row.action_description or ''}".lower()
    # Order matters: a split is a skip; the merger check below maps to SELL.
    if "split" in label:
        return SkipReason("split")
    qty = row.quantity if row.quantity is not None else Decimal(0)
    if "merger" in label or row.transaction_type == "TC":
        # Cash merger: remove shares (SELL) and carry the cash proceeds.
        return _base(row, "SELL", abs(qty), ["corp-action:merger"])
    # #ASSUME (data integrity): a non-merger share-delta corporate action (spin-off,
    # bonus shares, warrant distribution) is represented with the TRANSFER vocabulary
    # so the holdings view's net-share math still applies. This labels it a transfer
    # rather than a corporate action in PP, an accepted SP3 simplification.
    # #VERIFY: net shares for such rows still reconcile via the Task 7 invariant test.
    ttype = "TRANSFER_IN" if qty >= 0 else "TRANSFER_OUT"
    return _base(row, ttype, abs(qty), ["corp-action:other"])


def _normalize_transfer(
    row: InteractiveBrokersTransaction,
) -> NormalizedRow | SkipReason:
    qty = row.quantity if row.quantity is not None else Decimal(0)
    direction = (row.direction or "").upper()
    notes: list[str] = []
    if direction == "IN":
        return _base(row, "TRANSFER_IN", abs(qty), notes)
    if direction == "OUT":
        return _base(row, "TRANSFER_OUT", abs(qty), notes)
    if direction != "":
        # Unrecognized direction literal: fall back to sign, preserve the raw
        # value for observability.
        notes.append(f"unknown-transfer-direction:{row.direction}")
    ttype = "TRANSFER_IN" if qty >= 0 else "TRANSFER_OUT"
    return _base(row, ttype, abs(qty), notes)


def normalize_ibkr_row(
    row: InteractiveBrokersTransaction,
) -> NormalizedRow | SkipReason:
    """Map one IBKR Layer-1 row to broker-agnostic Layer-2 field values.

    Args:
        row: A persisted ``InteractiveBrokersTransaction`` (Layer 1).

    Returns:
        A :class:`NormalizedRow` to persist, or a :class:`SkipReason` when the row
        is deliberately not represented in Layer 2 (fee/interest, reinvestment
        funding, split, or an unrecognized subtype).
    """
    handlers = {
        "TRADE": _normalize_trade,
        "CASH": _normalize_cash,
        "CORP_ACTION": _normalize_corp_action,
        "TRANSFER": _normalize_transfer,
    }
    handler = handlers.get(row.record_type)
    if handler is None:
        return SkipReason(f"unknown_record_type:{row.record_type}")
    return handler(row)
