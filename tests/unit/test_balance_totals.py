"""Tests for the nightly IBKR totals: exact-to-the-cent sums and rejections."""

from __future__ import annotations

import logging
import random
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from security_master.balances.ibkr_totals import (
    ENTERED_BY_NIGHTLY,
    compute_nightly_totals,
    sum_account_total,
)
from security_master.balances.rules import format_money
from security_master.storage.balance_models import AccountBalance

from .balance_support import (
    ACCT_INVEST,
    ACCT_IRA,
    REPORT_DATE,
    add_cash,
    add_position,
    example_registry,
)

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

_MICRO = 1_000_000
_CENT_IN_MICRO = 10_000


def _oracle_cents(values: list[Decimal]) -> Decimal:
    """Independent reference: integer micro-units, one half-up rounding to cents.

    Shares no code with the implementation (no Decimal arithmetic, no context):
    every value becomes an exact integer number of millionths.
    """
    micro = sum(int(v.scaleb(6)) for v in values)
    quotient, remainder = divmod(abs(micro), _CENT_IN_MICRO)
    if remainder * 2 >= _CENT_IN_MICRO:
        quotient += 1
    return Decimal(quotient if micro >= 0 else -quotient).scaleb(-2)


_AMOUNT = st.decimals(
    min_value=Decimal("-1e12"),
    max_value=Decimal("1e12"),
    places=6,
    allow_nan=False,
    allow_infinity=False,
)


@given(positions=st.lists(_AMOUNT, max_size=40), cash=st.lists(_AMOUNT, max_size=5))
def test_total_is_exact_to_the_cent_over_random_positions_and_cash(
    positions: list[Decimal], cash: list[Decimal]
) -> None:
    total = sum_account_total(positions, cash)
    expected = _oracle_cents([*positions, *cash])
    assert total == expected
    assert total.as_tuple().exponent == -2
    assert format_money(total) == format(expected, "f")


@given(
    cents=st.lists(st.integers(min_value=-(10**14), max_value=10**14), max_size=60),
)
def test_cent_valued_inputs_sum_with_no_rounding_at_all(cents: list[int]) -> None:
    """Whole-cent inputs must total exactly: a float sum would drift here."""
    values = [Decimal(c).scaleb(-2) for c in cents]
    assert sum_account_total(values, []) == Decimal(sum(cents)).scaleb(-2)


@pytest.mark.parametrize(
    ("positions", "cash", "expected"),
    [
        (["0.004"], ["0.0009"], "0.00"),
        (["0.004"], ["0.001"], "0.01"),  # exactly half a cent rounds up
        (["0.004"], ["0.001", "0.000001"], "0.01"),  # 0.005001 rounds up
        (["0.005"], [], "0.01"),  # half rounds away from zero
        (["-0.005"], [], "-0.01"),
        (["0.1"] * 10, ["0.2"], "1.20"),  # the classic float drift case
        (["999999999999.999999"], ["0.000001"], "1000000000000.00"),
    ],
)
def test_rounding_boundaries(
    positions: list[str], cash: list[str], expected: str
) -> None:
    total = sum_account_total(
        [Decimal(p) for p in positions], [Decimal(c) for c in cash]
    )
    assert format(total, "f") == expected


def test_sum_is_not_rounded_by_the_default_context() -> None:
    """Twenty-eight-plus significant digits must survive until the final rounding.

    Under the default 28-digit context 1e27 + 0.005 collapses to 1e27 (and the
    quantize itself raises); the wide context keeps the half cent and rounds up.
    """
    total = sum_account_total([Decimal("1e27")], [Decimal("0.005")])
    assert format(total, "f") == "1000000000000000000000000000.01"


def test_seeded_random_database_totals_match_the_oracle(
    sqlite_session: Session,
) -> None:
    """End to end through the tables: random positions plus cash, exact cents."""
    rng = random.Random(20260619)  # noqa: S311 - deterministic test data
    expected: dict[str, Decimal] = {}
    for account in (ACCT_INVEST, ACCT_IRA):
        values = [
            Decimal(rng.randint(0, 9 * 10**13)).scaleb(-6)
            for _ in range(rng.randint(1, 25))
        ]
        cash = [Decimal(rng.randint(0, 9 * 10**10)).scaleb(-6)]
        for v in values:
            add_position(sqlite_session, account, v)
        add_cash(sqlite_session, account, cash[0])
        expected[account] = _oracle_cents([*values, *cash])
    sqlite_session.commit()

    result = compute_nightly_totals(sqlite_session, example_registry())
    assert result.inserted == 2
    assert result.rejections == []
    rows = {r.account_key: r.value for r in sqlite_session.query(AccountBalance)}
    assert rows["pp:ibkr:0001"] == expected[ACCT_INVEST]
    assert rows["pp:ibkr:0002"] == expected[ACCT_IRA]


def test_nightly_writes_the_documented_row(sqlite_session: Session) -> None:
    add_position(sqlite_session, ACCT_INVEST, Decimal("1000.10"))
    add_position(sqlite_session, ACCT_INVEST, Decimal("250.25"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("49.65"))
    sqlite_session.commit()
    stamp = datetime(2026, 6, 20, 1, 2, 3, tzinfo=UTC)

    result = compute_nightly_totals(sqlite_session, example_registry(), now=stamp)

    assert (result.report_date, result.inserted, result.updated) == (REPORT_DATE, 1, 0)
    row = sqlite_session.query(AccountBalance).one()
    assert row.value == Decimal("1300.00")
    assert row.source == "ibkr_flex"
    assert row.as_of == REPORT_DATE
    assert row.currency == "USD"
    assert row.category == "Investments"
    assert row.display_name == "Example Brokerage Account"
    assert row.entered_by == ENTERED_BY_NIGHTLY
    assert str(row.entity_id) == "11111111-1111-4111-8111-111111111111"
    assert row.account_key == "pp:ibkr:0001"  # pragma: allowlist secret -- account key


def test_only_the_latest_report_date_is_totalled(sqlite_session: Session) -> None:
    older = date(2026, 6, 18)
    add_position(sqlite_session, ACCT_INVEST, Decimal("1.00"), report_date=older)
    add_cash(sqlite_session, ACCT_INVEST, Decimal("1.00"), report_date=older)
    add_position(sqlite_session, ACCT_INVEST, Decimal("10.00"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("5.00"))
    sqlite_session.commit()
    compute_nightly_totals(sqlite_session, example_registry())
    row = sqlite_session.query(AccountBalance).one()
    assert (row.as_of, row.value) == (REPORT_DATE, Decimal("15.00"))


def test_cash_only_account_is_totalled(sqlite_session: Session) -> None:
    add_position(sqlite_session, ACCT_INVEST, Decimal("1.00"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("1.00"))
    add_cash(sqlite_session, ACCT_IRA, Decimal("7.50"))
    sqlite_session.commit()
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert result.inserted == 2
    ira = sqlite_session.query(AccountBalance).filter_by(account_key="pp:ibkr:0002")
    assert ira.one().value == Decimal("7.50")


def test_rerun_updates_in_place(sqlite_session: Session) -> None:
    add_position(sqlite_session, ACCT_INVEST, Decimal("10.00"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("5.00"))
    sqlite_session.commit()
    registry = example_registry()
    compute_nightly_totals(sqlite_session, registry)
    again = compute_nightly_totals(sqlite_session, registry)
    assert (again.inserted, again.updated) == (0, 1)
    assert sqlite_session.query(AccountBalance).count() == 1


def test_no_positions_means_no_report_date(sqlite_session: Session) -> None:
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert result.report_date is None
    assert sqlite_session.query(AccountBalance).count() == 0


def test_non_usd_balance_withholds_the_account_and_logs_clearly(
    sqlite_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    add_position(sqlite_session, ACCT_INVEST, Decimal("10.00"))
    add_position(sqlite_session, ACCT_INVEST, Decimal("777.77"), currency="EUR")
    add_cash(sqlite_session, ACCT_INVEST, Decimal("5.00"))
    add_position(sqlite_session, ACCT_IRA, Decimal("20.00"))
    add_cash(sqlite_session, ACCT_IRA, Decimal("1.00"))
    sqlite_session.commit()
    caplog.set_level(logging.INFO)

    result = compute_nightly_totals(sqlite_session, example_registry())

    assert result.accounts_withheld == 1
    written = [r.account_key for r in sqlite_session.query(AccountBalance)]
    assert written == ["pp:ibkr:0002"]  # the USD-only account still lands
    text = caplog.text
    assert "non_usd_row" in text
    assert "EUR" in text
    assert "pp:ibkr:0001" in text
    assert "not converted" in text


def test_zero_valued_non_usd_row_is_dropped_but_does_not_withhold(
    sqlite_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    add_position(sqlite_session, ACCT_INVEST, Decimal("10.00"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("5.00"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal(0), currency="EUR")
    sqlite_session.commit()
    caplog.set_level(logging.INFO)
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert result.accounts_withheld == 0
    assert result.inserted == 1
    assert "non_usd_row" in caplog.text
    assert sqlite_session.query(AccountBalance).one().value == Decimal("15.00")


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("missing_cash", "no_usd_cash_row"),
        ("null_value", "missing_value"),
        ("unmapped", "unmapped"),
        ("negative", "negative_total"),
    ],
)
def test_rejections_carry_a_reason_and_never_leak_amounts(
    sqlite_session: Session,
    caplog: pytest.LogCaptureFixture,
    setup: str,
    reason: str,
) -> None:
    account = "U9990009" if setup == "unmapped" else ACCT_INVEST
    if setup == "null_value":
        add_position(sqlite_session, account, None)
        add_cash(sqlite_session, account, Decimal("4242.42"))
    elif setup == "negative":
        add_position(sqlite_session, account, Decimal("-9191.91"))
        add_cash(sqlite_session, account, Decimal("1.00"))
    elif setup == "missing_cash":
        add_position(sqlite_session, account, Decimal("4242.42"))
    else:
        add_position(sqlite_session, account, Decimal("4242.42"))
        add_cash(sqlite_session, account, Decimal("1.00"))
    sqlite_session.commit()
    caplog.set_level(logging.INFO)

    result = compute_nightly_totals(sqlite_session, example_registry())

    assert [r.reason for r in result.rejections] == [reason]
    assert sqlite_session.query(AccountBalance).count() == 0
    for secret in ("4242", "9191", "U999000"):
        assert secret not in caplog.text


def test_suffix_collision_is_rejected_not_merged(sqlite_session: Session) -> None:
    add_position(sqlite_session, "U9990001", Decimal("1.00"))
    add_cash(sqlite_session, "U9990001", Decimal("1.00"))
    add_position(sqlite_session, "U8880001", Decimal("2.00"))
    add_cash(sqlite_session, "U8880001", Decimal("2.00"))
    sqlite_session.commit()
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert [r.reason for r in result.rejections] == ["ambiguous_suffix"]
    assert sqlite_session.query(AccountBalance).count() == 0


def test_existing_manual_mark_is_not_overwritten(sqlite_session: Session) -> None:
    from security_master.balances.service import set_manual_balance

    registry = example_registry()
    set_manual_balance(
        sqlite_session,
        registry,
        account_key="pp:ibkr:0001",  # pragma: allowlist secret -- account key
        value=Decimal("1.00"),
        as_of=REPORT_DATE,
        source="manual_mark",
        note=None,
        entered_by="tester",
    )
    add_position(sqlite_session, ACCT_INVEST, Decimal("10.00"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("5.00"))
    sqlite_session.commit()
    result = compute_nightly_totals(sqlite_session, registry)
    assert [r.reason for r in result.rejections] == ["existing_other_source"]
    assert sqlite_session.query(AccountBalance).one().value == Decimal("1.00")
