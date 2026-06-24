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
