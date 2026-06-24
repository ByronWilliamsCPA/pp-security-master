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
