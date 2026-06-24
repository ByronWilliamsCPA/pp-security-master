"""Reconstruct Layer-1 net positions and reconcile them against a broker snapshot.

The reconstruction rule is load-bearing: net share quantity is the sum of ``quantity``
over the record types that MOVE SHARES (TRADE, CORP_ACTION, TRANSFER), scoped to one
account and bounded by ``transaction_date <= report_date``. CASH rows do not move shares
(dividends are cash; reinvested distributions already exist as separate TRADE rows). This
is what nets a cash-merger corporate action to zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from security_master.storage.position_models import InteractiveBrokersOpenPosition
from security_master.storage.transaction_models import InteractiveBrokersTransaction

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

# #CRITICAL (data integrity): the share-moving record-type set is exactly these three.
# Changing it changes every reconciliation result.
# #VERIFY: pinned by test_position_reconciliation (DBJA/BMBCX anchors + CASH-excluded).
_SHARE_MOVING: tuple[str, ...] = ("TRADE", "CORP_ACTION", "TRANSFER")

# Default absolute drift tolerance in shares: tight enough to flag a real fractional
# gap (BMBCX is 166 shares), loose enough to absorb sub-share rounding noise.
DEFAULT_TOLERANCE = Decimal("0.0001")


@dataclass(frozen=True)
class ReconciliationRow:
    """One security's reconstructed-vs-reported comparison."""

    isin: str | None
    conid: str | None
    symbol: str | None
    reconstructed_qty: Decimal
    reported_qty: Decimal | None
    drift: Decimal
    status: str


@dataclass
class _ReconAgg:
    """Accumulator for one identity key during reconstruction."""

    qty: Decimal
    isin: str | None
    conid: str | None
    symbol: str | None


def reconstruct_net_positions(
    session: Session,
    account_number: str,
    as_of: date,
) -> dict[str, _ReconAgg]:
    """Reconstruct net share quantity per identity key from Layer-1 records.

    Args:
        session: Active SQLAlchemy session.
        account_number: Account to scope reconstruction to.
        as_of: Inclusive upper bound on ``transaction_date``.

    Returns:
        Mapping of identity key ``COALESCE(isin, conid)`` to its accumulator.
    """
    rows = (
        session.query(InteractiveBrokersTransaction)
        .filter(
            InteractiveBrokersTransaction.record_type.in_(_SHARE_MOVING),
            InteractiveBrokersTransaction.account_number == account_number,
            InteractiveBrokersTransaction.transaction_date <= as_of,
        )
        .all()
    )
    agg: dict[str, _ReconAgg] = {}
    for row in rows:
        # #EDGE (data integrity): COALESCE(isin, conid) splits one security into
        # two keys if some share-moving rows carry ISIN and others carry only
        # conid. Real IBKR rows for a security share the same ISIN, so they net
        # correctly; a mixed-key history is the unhandled edge.
        # #VERIFY: test_isin_grouping_ignores_conid_presence pins the real shape
        # (a TRADE with ISIN nets a CORP_ACTION that also carries ISIN + conid).
        key = row.isin or row.conid
        if key is None:
            continue
        qty = row.quantity if row.quantity is not None else Decimal(0)
        if key not in agg:
            agg[key] = _ReconAgg(Decimal(0), row.isin, row.conid, row.symbol)
        agg[key].qty += qty
    return agg


def _status(
    reconstructed: Decimal,
    reported: Decimal | None,
    tolerance: Decimal,
) -> str:
    """Classify one security's drift into the four-way status taxonomy.

    Args:
        reconstructed: Net reconstructed quantity (0 when no share-moving rows).
        reported: Snapshot quantity, or None when the snapshot omits the security.
        tolerance: Absolute share tolerance for the MATCHED band.

    Returns:
        One of MATCHED, DRIFT, RECONSTRUCTED_ONLY, REPORTED_ONLY.
    """
    if reported is None:
        return "MATCHED" if abs(reconstructed) <= tolerance else "RECONSTRUCTED_ONLY"
    if abs(reconstructed - reported) <= tolerance:
        return "MATCHED"
    return "DRIFT"


def reconcile_positions(
    session: Session,
    account_number: str,
    as_of: date,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> list[ReconciliationRow]:
    """Reconcile reconstructed Layer-1 positions against the persisted snapshot.

    Args:
        session: Active SQLAlchemy session.
        account_number: Account to reconcile.
        as_of: Snapshot ``report_date``; bounds reconstruction and selects the
            snapshot rows to compare against.
        tolerance: Absolute share tolerance for the MATCHED band.

    Returns:
        One :class:`ReconciliationRow` per identity key in the union of the
        reconstructed and reported sets. A REPORTED_ONLY row (snapshot present, no
        share-moving rows) has ``reconstructed_qty`` 0.
    """
    recon = reconstruct_net_positions(session, account_number, as_of)
    snapshot_rows = (
        session.query(InteractiveBrokersOpenPosition)
        .filter(
            InteractiveBrokersOpenPosition.account_number == account_number,
            InteractiveBrokersOpenPosition.report_date == as_of,
        )
        .all()
    )
    reported: dict[str, InteractiveBrokersOpenPosition] = {}
    for snap in snapshot_rows:
        # conid is NOT NULL on the snapshot (idempotency key), so the identity
        # key is always present: isin preferred, conid fallback. No None guard is
        # needed here, unlike reconstruct_net_positions where the transaction's
        # conid is nullable.
        key = snap.isin or snap.conid
        reported[key] = snap

    results: list[ReconciliationRow] = []
    for key in {*recon.keys(), *reported.keys()}:
        agg = recon.get(key)
        snap = reported.get(key)
        reconstructed_qty = agg.qty if agg is not None else Decimal(0)
        reported_qty = snap.position if snap is not None else None
        drift = reconstructed_qty - (
            reported_qty if reported_qty is not None else Decimal(0)
        )
        # REPORTED_ONLY: snapshot present but no share-moving rows reconstructed.
        status = (
            "REPORTED_ONLY"
            if agg is None and snap is not None
            else _status(reconstructed_qty, reported_qty, tolerance)
        )
        if snap is not None:
            isin, conid, symbol = snap.isin, snap.conid, snap.symbol
        elif agg is not None:
            isin, conid, symbol = agg.isin, agg.conid, agg.symbol
        else:
            isin = conid = symbol = None
        results.append(
            ReconciliationRow(
                isin=isin,
                conid=conid,
                symbol=symbol,
                reconstructed_qty=reconstructed_qty,
                reported_qty=reported_qty,
                drift=drift,
                status=status,
            )
        )
    results.sort(key=lambda r: r.isin or r.conid or "")
    return results
