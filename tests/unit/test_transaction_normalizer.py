"""Unit tests for the pure IBKR Layer-1 -> Layer-2 mapping function."""

from datetime import date
from decimal import Decimal

import pytest

from security_master.storage.transaction_models import InteractiveBrokersTransaction

pytestmark = [pytest.mark.storage]


def _l1(record_type: str, **kw) -> InteractiveBrokersTransaction:
    defaults = {
        "record_type": record_type,
        "transaction_date": date(2024, 1, 2),
        "security_name": "ACME",
        "isin": "US0000000001",
        "symbol": "ACME",
        "transaction_type": "BUY",
        "quantity": Decimal(10),
        "amount": Decimal("1000.00"),
        "currency": "USD",
        "account_name": "IBKR",
        "account_number": "U13052577",
        "import_batch_id": "b",
    }
    defaults.update(kw)
    return InteractiveBrokersTransaction(**defaults)


def test_trade_buy_maps_to_buy_positive_magnitude() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(_l1("TRADE", transaction_type="BUY", quantity=Decimal(10)))
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "BUY"
    assert out.quantity == Decimal(10)


def test_trade_sell_maps_to_sell_positive_magnitude() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1("TRADE", transaction_type="SELL", quantity=Decimal(-10))
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "SELL"
    assert out.quantity == Decimal(10)


def test_cash_dividend_maps_to_div_no_quantity() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CASH", transaction_type="Dividends", quantity=None, amount=Decimal("12.50")
        )
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "DIV"
    assert out.quantity is None


def test_cash_fee_is_skipped() -> None:
    from security_master.storage.transaction_normalizer import (
        SkipReason,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CASH",
            transaction_type="Other Fees",
            quantity=None,
            amount=Decimal("-2.00"),
        )
    )
    assert isinstance(out, SkipReason)
    assert out.reason == "fee_interest"


def test_corp_action_cash_merger_maps_to_sell_carrying_proceeds() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CORP_ACTION",
            transaction_type="TC",
            action_description="DBJA cash merger",
            quantity=Decimal(-4156),
            proceeds=Decimal("41560.00"),
            amount=Decimal("41560.00"),
        )
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "SELL"
    assert out.quantity == Decimal(4156)
    assert out.net_amount == Decimal("41560.00")
    assert "corp-action:merger" in out.notes


def test_transfer_in_maps_by_direction() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1("TRANSFER", transaction_type="ACATS", direction="IN", quantity=Decimal(5))
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "TRANSFER_IN"
    assert out.quantity == Decimal(5)


def test_transfer_out_maps_by_direction() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "TRANSFER",
            transaction_type="ACATS",
            direction="OUT",
            quantity=Decimal(-5),
        )
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "TRANSFER_OUT"
    assert out.quantity == Decimal(5)


def test_cash_deposit_combined_label_positive_is_deposit() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CASH",
            transaction_type="Deposits/Withdrawals",
            quantity=None,
            amount=Decimal("5000.00"),
        )
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "DEPOSIT"


def test_cash_withdrawal_combined_label_negative_is_withdrawal() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CASH",
            transaction_type="Deposits/Withdrawals",
            quantity=None,
            amount=Decimal("-3000.00"),
        )
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "WITHDRAWAL"


def test_transfer_unknown_direction_falls_back_and_notes_raw() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "TRANSFER",
            transaction_type="ACATS",
            direction="OUTBOUND",
            quantity=Decimal(-5),
        )
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "TRANSFER_OUT"  # by sign
    assert any("unknown-transfer-direction:OUTBOUND" in n for n in out.notes)


def test_every_canonical_type_is_a_view_case_key() -> None:
    """Each type the normalizer can emit must be a CASE key in the export view,
    or the export view would emit it to PP untranslated (the DIV-not-DIVIDEND trap).
    """
    from security_master.storage.transaction_normalizer import CANONICAL_TYPES
    from security_master.storage.views import VIEW_TRANSACTIONS_FOR_PP_EXPORT

    view_sql = str(VIEW_TRANSACTIONS_FOR_PP_EXPORT.text)
    for ttype in CANONICAL_TYPES:
        assert f"= '{ttype}'" in view_sql, f"{ttype} missing from export view CASE"


def test_resolve_security_isin_then_symbol(sqlite_session) -> None:
    from security_master.storage.models import SecurityMaster
    from security_master.storage.transaction_normalizer import resolve_security

    sqlite_session.add(SecurityMaster(name="Acme", isin="US0000000001", symbol="ACME"))
    sqlite_session.add(SecurityMaster(name="Beta", isin=None, symbol="BETA"))
    sqlite_session.commit()

    by_isin = resolve_security(sqlite_session, isin="US0000000001", symbol="ZZZ")
    by_symbol = resolve_security(sqlite_session, isin=None, symbol="BETA")
    unresolved = resolve_security(sqlite_session, isin=None, symbol="NOPE")
    assert by_isin is not None
    assert by_symbol is not None
    assert unresolved is None


def test_resolve_account_mapped_and_unmapped(sqlite_session) -> None:
    from security_master.storage.account_models import AccountMapping
    from security_master.storage.transaction_normalizer import (
        UNMAPPED_GROUP,
        resolve_account,
    )

    sqlite_session.add(
        AccountMapping(account_number="U1", pp_group="Taxable", pp_account="IBKR")
    )
    sqlite_session.commit()

    assert resolve_account(sqlite_session, "U1") == ("Taxable", "IBKR", True)
    assert resolve_account(sqlite_session, "U9") == (UNMAPPED_GROUP, "U9", False)
    assert resolve_account(sqlite_session, None) == (UNMAPPED_GROUP, "UNKNOWN", False)


def test_normalize_all_writes_resolved_and_flagged_rows(sqlite_session) -> None:
    from security_master.storage.account_models import AccountMapping
    from security_master.storage.models import SecurityMaster
    from security_master.storage.transaction_models import ConsolidatedTransaction
    from security_master.storage.transaction_normalizer import TransactionNormalizer

    sqlite_session.add(SecurityMaster(name="Acme", isin="US0000000001", symbol="ACME"))
    sqlite_session.add(
        AccountMapping(
            account_number="U13052577", pp_group="Taxable", pp_account="IBKR"
        )
    )
    sqlite_session.add(_l1("TRADE", transaction_type="BUY", quantity=Decimal(10)))
    sqlite_session.add(
        _l1("CASH", transaction_type="Other Fees", quantity=None, amount=Decimal(-2))
    )
    sqlite_session.commit()

    summary = TransactionNormalizer(sqlite_session).normalize_all()

    rows = sqlite_session.query(ConsolidatedTransaction).all()
    assert summary.normalized == 1
    assert summary.skipped == 1
    assert summary.flagged == 0
    assert summary.skipped_by == {"fee_interest": 1}
    assert len(rows) == 1
    assert rows[0].transaction_type == "BUY"
    assert rows[0].security_master_id is not None
    assert rows[0].pp_group == "Taxable"
    assert rows[0].has_validation_issues is False


def test_normalize_all_flags_unresolved_and_unmapped(sqlite_session) -> None:
    from security_master.storage.transaction_models import ConsolidatedTransaction
    from security_master.storage.transaction_normalizer import TransactionNormalizer

    sqlite_session.add(
        _l1(
            "TRADE",
            transaction_type="BUY",
            isin=None,
            symbol="GHOST",
            quantity=Decimal(3),
        )
    )
    sqlite_session.commit()

    summary = TransactionNormalizer(sqlite_session).normalize_all()

    row = sqlite_session.query(ConsolidatedTransaction).one()
    assert row.security_master_id is None
    assert row.pp_group == "Unmapped"
    assert row.has_validation_issues is True
    assert "unresolved-security" in (row.validation_notes or "")
    assert "unmapped-account" in (row.validation_notes or "")
    assert summary.normalized == 1
    assert summary.flagged == 1


def _layer2_net_shares(rows) -> Decimal:
    """Mirror the holdings-view CASE: +qty for inflow types, -qty for outflow."""
    from security_master.storage.transaction_normalizer import _INFLOW, _OUTFLOW

    total = Decimal(0)
    for r in rows:
        if r.quantity is None:
            continue
        if r.transaction_type in _INFLOW:
            total += r.quantity
        elif r.transaction_type in _OUTFLOW:
            total -= r.quantity
    return total


def test_reconciliation_invariant_matches_sp2(sqlite_session) -> None:
    """Net shares from Layer-2 (view CASE) == SP2 _SHARE_MOVING sum from Layer-1.

    Anchors: DBJA merger nets to 0; a dividend injects no shares.
    """
    from security_master.storage.position_reconciliation import (
        reconstruct_net_positions,
    )
    from security_master.storage.transaction_models import ConsolidatedTransaction
    from security_master.storage.transaction_normalizer import TransactionNormalizer

    isin = "US000DBJA001"
    sqlite_session.add(
        _l1(
            "TRADE",
            isin=isin,
            symbol="DBJA",
            transaction_type="BUY",
            quantity=Decimal(4156),
        )
    )
    sqlite_session.add(
        _l1(
            "CORP_ACTION",
            isin=isin,
            symbol="DBJA",
            transaction_type="TC",
            action_description="cash merger",
            quantity=Decimal(-4156),
            proceeds=Decimal(41560),
            amount=Decimal(41560),
        )
    )
    sqlite_session.add(
        _l1(
            "CASH",
            isin=isin,
            symbol="DBJA",
            transaction_type="Dividends",
            quantity=None,
            amount=Decimal(50),
        )
    )
    sqlite_session.commit()

    TransactionNormalizer(sqlite_session).normalize_all()

    l2_rows = (
        sqlite_session.query(ConsolidatedTransaction)
        .filter(ConsolidatedTransaction.isin == isin)
        .all()
    )
    # reconstruct_net_positions(session, account_number, as_of: date) returns
    # dict[str, _ReconAgg] keyed by COALESCE(isin, conid); the value has a .qty.
    l1_net = reconstruct_net_positions(sqlite_session, "U13052577", date(2024, 12, 31))
    agg = l1_net.get(isin)
    assert _layer2_net_shares(l2_rows) == Decimal(0)
    assert (agg.qty if agg is not None else Decimal(0)) == Decimal(0)


def test_normalize_all_is_idempotent(sqlite_session) -> None:
    from security_master.storage.transaction_models import ConsolidatedTransaction
    from security_master.storage.transaction_normalizer import TransactionNormalizer

    sqlite_session.add(_l1("TRADE", transaction_type="BUY", quantity=Decimal(10)))
    sqlite_session.commit()

    TransactionNormalizer(sqlite_session).normalize_all()
    count_first = sqlite_session.query(ConsolidatedTransaction).count()
    TransactionNormalizer(sqlite_session).normalize_all()
    count_second = sqlite_session.query(ConsolidatedTransaction).count()

    assert count_first == 1
    assert count_second == 1


def test_normalize_all_preserves_export_flags_on_rerun(sqlite_session) -> None:
    from security_master.storage.transaction_models import ConsolidatedTransaction
    from security_master.storage.transaction_normalizer import TransactionNormalizer

    sqlite_session.add(_l1("TRADE", transaction_type="BUY", quantity=Decimal(10)))
    sqlite_session.commit()
    TransactionNormalizer(sqlite_session).normalize_all()

    row = sqlite_session.query(ConsolidatedTransaction).one()
    row.exported_to_pp = True
    row.export_batch_id = "exp-1"
    sqlite_session.commit()

    TransactionNormalizer(sqlite_session).normalize_all()
    row = sqlite_session.query(ConsolidatedTransaction).one()
    assert row.exported_to_pp is True
    assert row.export_batch_id == "exp-1"


def test_corp_action_split_is_skipped() -> None:
    from security_master.storage.transaction_normalizer import (
        SkipReason,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CORP_ACTION",
            transaction_type="FS",
            action_description="10:1 split",
            quantity=Decimal(90),
        )
    )
    assert isinstance(out, SkipReason)
    assert out.reason == "split"


def test_corp_action_other_share_delta_maps_to_transfer_by_sign() -> None:
    from security_master.storage.transaction_normalizer import (
        NormalizedRow,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CORP_ACTION",
            transaction_type="SO",
            action_description="spin-off shares",
            quantity=Decimal(7),
        )
    )
    assert isinstance(out, NormalizedRow)
    assert out.transaction_type == "TRANSFER_IN"
    assert out.quantity == Decimal(7)
    assert "corp-action:other" in out.notes


def test_cash_reinvestment_is_skipped() -> None:
    from security_master.storage.transaction_normalizer import (
        SkipReason,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CASH",
            transaction_type="Dividend Reinvestment",
            quantity=None,
            amount=Decimal(25),
        )
    )
    assert isinstance(out, SkipReason)
    assert out.reason == "reinvestment_funding"


def test_cash_unknown_type_is_skipped() -> None:
    from security_master.storage.transaction_normalizer import (
        SkipReason,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(
        _l1(
            "CASH",
            transaction_type="Mystery Adjustment",
            quantity=None,
            amount=Decimal(1),
        )
    )
    assert isinstance(out, SkipReason)
    assert out.reason == "unknown_cash_type"


def test_unknown_record_type_is_skipped() -> None:
    from security_master.storage.transaction_normalizer import (
        SkipReason,
        normalize_ibkr_row,
    )

    out = normalize_ibkr_row(_l1("MYSTERY", transaction_type="X", quantity=Decimal(1)))
    assert isinstance(out, SkipReason)
    assert out.reason.startswith("unknown_record_type")
