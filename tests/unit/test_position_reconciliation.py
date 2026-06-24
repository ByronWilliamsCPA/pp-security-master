"""Unit tests for the Layer-1 position reconstruction rule and status taxonomy."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from security_master.storage.position_models import InteractiveBrokersOpenPosition
from security_master.storage.position_reconciliation import reconcile_positions
from security_master.storage.transaction_models import InteractiveBrokersTransaction

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = [
    pytest.mark.storage,
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]

_ACCOUNT = "U1"
_AS_OF = date(2026, 6, 19)


def _txn(
    record_type: str, isin: str, qty: str, when: date, **kw
) -> InteractiveBrokersTransaction:
    return InteractiveBrokersTransaction(
        record_type=record_type,
        transaction_date=when,
        security_name=isin,
        isin=isin,
        transaction_type=kw.get("ttype", "BUY"),
        quantity=Decimal(qty),
        amount=Decimal(0),
        currency="USD",
        account_name="IBKR",
        account_number=kw.get("account", _ACCOUNT),
        import_batch_id="b",
    )


def _snapshot(isin: str, qty: str, conid: str) -> InteractiveBrokersOpenPosition:
    return InteractiveBrokersOpenPosition(
        account_number=_ACCOUNT,
        report_date=_AS_OF,
        conid=conid,
        isin=isin,
        security_name=isin,
        position=Decimal(qty),
        currency="USD",
        import_batch_id="b",
    )


def _by_isin(rows) -> dict:
    return {r.isin: r for r in rows}


def test_dbja_merger_reconstructs_to_zero_and_is_matched(
    sqlite_session: Session,
) -> None:
    """DBJA: +4156 buy then -4156 corp action nets to 0; absent from snapshot -> MATCHED."""
    sqlite_session.add(_txn("TRADE", "US000000DBJA", "4156", date(2023, 1, 2)))
    sqlite_session.add(
        _txn("CORP_ACTION", "US000000DBJA", "-4156", date(2024, 1, 10), ttype="TC")
    )
    sqlite_session.commit()

    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    dbja = rows["US000000DBJA"]
    assert dbja.reconstructed_qty == Decimal(0)
    assert dbja.reported_qty is None
    assert dbja.status == "MATCHED"


def test_bmbcx_reconstructs_short_and_is_drift(sqlite_session: Session) -> None:
    """BMBCX: reconstructed 2354.069 vs reported 2520.119 -> DRIFT, drift -166.05."""
    sqlite_session.add(_txn("TRADE", "US000000BMBC", "2354.069", date(2023, 1, 3)))
    sqlite_session.add(_snapshot("US000000BMBC", "2520.119", "111"))
    sqlite_session.commit()

    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    bmbcx = rows["US000000BMBC"]
    assert bmbcx.reconstructed_qty == Decimal("2354.069")
    assert bmbcx.reported_qty == Decimal("2520.119")
    assert bmbcx.drift == Decimal("-166.05")
    assert bmbcx.status == "DRIFT"


def test_cash_rows_do_not_move_shares(sqlite_session: Session) -> None:
    """A CASH dividend row must not change the reconstructed quantity."""
    sqlite_session.add(_txn("TRADE", "US000000AAAA", "100", date(2023, 1, 2)))
    sqlite_session.add(
        _txn("CASH", "US000000AAAA", "9999", date(2023, 6, 1), ttype="Dividends")
    )
    sqlite_session.add(_snapshot("US000000AAAA", "100", "333"))
    sqlite_session.commit()

    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    assert rows["US000000AAAA"].reconstructed_qty == Decimal(100)
    assert rows["US000000AAAA"].status == "MATCHED"


def test_transfer_moves_shares(sqlite_session: Session) -> None:
    """A TRANSFER carries a share quantity and is included in reconstruction."""
    sqlite_session.add(
        _txn("TRANSFER", "US000000BBBB", "50", date(2023, 1, 2), ttype="ACATS")
    )
    sqlite_session.add(_snapshot("US000000BBBB", "50", "444"))
    sqlite_session.commit()

    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    assert rows["US000000BBBB"].reconstructed_qty == Decimal(50)
    assert rows["US000000BBBB"].status == "MATCHED"


def test_transactions_after_report_date_are_excluded(sqlite_session: Session) -> None:
    """A trade dated after the snapshot report_date must not count."""
    sqlite_session.add(_txn("TRADE", "US000000CCCC", "10", date(2023, 1, 2)))
    sqlite_session.add(_txn("TRADE", "US000000CCCC", "5", date(2026, 7, 1)))
    sqlite_session.add(_snapshot("US000000CCCC", "10", "555"))
    sqlite_session.commit()

    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    assert rows["US000000CCCC"].reconstructed_qty == Decimal(10)
    assert rows["US000000CCCC"].status == "MATCHED"


def test_other_account_is_excluded(sqlite_session: Session) -> None:
    """A trade in a different account must not contribute to this account's net."""
    sqlite_session.add(
        _txn("TRADE", "US000000DDDD", "10", date(2023, 1, 2), account="U2")
    )
    sqlite_session.add(_snapshot("US000000DDDD", "0.0001", "666"))
    sqlite_session.commit()

    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    assert rows["US000000DDDD"].status == "REPORTED_ONLY"


def test_reconstructed_only_nonzero_is_flagged(sqlite_session: Session) -> None:
    """Reconstructed non-zero with no snapshot row -> RECONSTRUCTED_ONLY."""
    sqlite_session.add(_txn("TRADE", "US000000EEEE", "7", date(2023, 1, 2)))
    sqlite_session.commit()

    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    assert rows["US000000EEEE"].reconstructed_qty == Decimal(7)
    assert rows["US000000EEEE"].reported_qty is None
    assert rows["US000000EEEE"].status == "RECONSTRUCTED_ONLY"


def test_multi_record_type_aggregation_nets(sqlite_session: Session) -> None:
    """TRADE + TRANSFER + CORP_ACTION for one key sum correctly."""
    sqlite_session.add(_txn("TRADE", "US000000FFFF", "100", date(2023, 1, 2)))
    sqlite_session.add(
        _txn("TRANSFER", "US000000FFFF", "50", date(2023, 2, 2), ttype="ACATS")
    )
    sqlite_session.add(
        _txn("CORP_ACTION", "US000000FFFF", "-30", date(2023, 3, 2), ttype="FS")
    )
    sqlite_session.add(_snapshot("US000000FFFF", "120", "777"))
    sqlite_session.commit()

    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    assert rows["US000000FFFF"].reconstructed_qty == Decimal(120)
    assert rows["US000000FFFF"].status == "MATCHED"


def test_drift_at_tolerance_boundary_and_configurable_tolerance(
    sqlite_session: Session,
) -> None:
    """Drift exactly equal to tolerance is MATCHED; a tighter tolerance flags it."""
    sqlite_session.add(_txn("TRADE", "US000000GGGG", "100.0000", date(2023, 1, 2)))
    sqlite_session.add(_snapshot("US000000GGGG", "100.0001", "888"))
    sqlite_session.commit()

    # Default tolerance 0.0001: |drift| == 0.0001 -> MATCHED (uses <=).
    rows = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))
    assert rows["US000000GGGG"].status == "MATCHED"

    # Tighter tolerance -> the same drift is now DRIFT.
    rows_tight = _by_isin(
        reconcile_positions(
            sqlite_session, _ACCOUNT, _AS_OF, tolerance=Decimal("0.00009")
        )
    )
    assert rows_tight["US000000GGGG"].status == "DRIFT"


def test_reported_only_drift_is_negative_reported(sqlite_session: Session) -> None:
    """A snapshot with no share-moving rows is REPORTED_ONLY with drift = -reported."""
    sqlite_session.add(_snapshot("US000000HHHH", "42", "999"))
    sqlite_session.commit()

    row = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))[
        "US000000HHHH"
    ]
    assert row.status == "REPORTED_ONLY"
    assert row.reconstructed_qty == Decimal(0)
    assert row.drift == Decimal(-42)


def test_isin_grouping_ignores_conid_presence(sqlite_session: Session) -> None:
    """Real IBKR shape: trade keyed by isin nets with a corp action carrying isin AND conid."""
    sqlite_session.add(_txn("TRADE", "US000000DBJA", "4156", date(2023, 1, 2)))
    corp = _txn("CORP_ACTION", "US000000DBJA", "-4156", date(2024, 1, 10), ttype="TC")
    corp.conid = "463451348"
    sqlite_session.add(corp)
    sqlite_session.commit()

    row = _by_isin(reconcile_positions(sqlite_session, _ACCOUNT, _AS_OF))[
        "US000000DBJA"
    ]
    assert row.reconstructed_qty == Decimal(0)
    assert row.status == "MATCHED"
