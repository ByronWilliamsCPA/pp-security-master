"""Tests for the nightly IBKR totals: exact-to-the-cent sums and rejections."""

from __future__ import annotations

import logging
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from security_master.balances.ibkr_totals import (
    ENTERED_BY_NIGHTLY,
    RUN_KEY,
    UNDERIVABLE_KEY,
    RejectReason,
    TotalsResult,
    _AccountData,
    _Row,
    _usd_values,
    compute_nightly_totals,
    sum_account_total,
)
from security_master.balances.registry import parse_registry
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
_NO_ROWS = RejectReason.NO_ROWS_ON_REPORT_DATE

# A registry with an IBKR Cash account, to exercise the overdraft rule.
_CASH_IBKR_SEED = """
accounts:
  - account_key: "pp:ibkr:0003"  # pragma: allowlist secret -- account key
    entity_id: "11111111-1111-4111-8111-111111111111"
    display_name: "Example Cash Sweep"
    category: "Cash"
"""


def _reasons(result: TotalsResult, key: str) -> list[RejectReason]:
    """Return the reason codes recorded for one account key, in order."""
    return [r.reason for r in result.rejections if r.account_key == key]


def _oracle_cents(values: list[Decimal]) -> Decimal:
    """Independent reference: integer micro-units, one half-up rounding to cents.

    Shares no summation or rounding code with the implementation: each value
    is shifted to an exact integer number of millionths (``scaleb`` only moves
    the exponent), and the sum and the rounding are plain integer arithmetic.
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
    """End to end through the tables: random positions plus cash, exact cents.

    SQLite stores ``Numeric`` as a float (hence the filtered SAWarning), so the
    values are bounded to at most fourteen significant digits, which a double
    round-trips exactly. Exactness beyond that is proven on the pure function
    above; this test proves the query, grouping, and write path.
    """
    rng = random.Random(20260619)
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
    first_stamp = datetime(2026, 6, 20, 1, 0, tzinfo=UTC)
    compute_nightly_totals(sqlite_session, registry, now=first_stamp)
    assert sqlite_session.query(AccountBalance).one().value == Decimal("15.00")

    # A late position for the same date changes the total; the rerun must
    # rewrite the existing row, not just count it.
    add_position(sqlite_session, ACCT_INVEST, Decimal("2.50"))
    sqlite_session.commit()
    second_stamp = datetime(2026, 6, 20, 2, 0, tzinfo=UTC)
    again = compute_nightly_totals(sqlite_session, registry, now=second_stamp)

    assert (again.inserted, again.updated) == (0, 1)
    row = sqlite_session.query(AccountBalance).one()
    assert row.value == Decimal("17.50")
    assert row.entered_at.replace(tzinfo=UTC) == second_stamp


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
    add_cash(sqlite_session, ACCT_IRA, Decimal("1.00"))
    sqlite_session.commit()
    caplog.set_level(logging.INFO)
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert result.accounts_withheld == 0
    assert result.inserted == 2
    assert "non_usd_row" in caplog.text
    invest = sqlite_session.query(AccountBalance).filter_by(account_key="pp:ibkr:0001")
    assert invest.one().value == Decimal("15.00")


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

    key = "pp:ibkr:0009" if setup == "unmapped" else "pp:ibkr:0001"
    assert _reasons(result, key) == [reason]
    assert all(r.reason == _NO_ROWS for r in result.rejections if r.account_key != key)
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
    assert _reasons(result, "pp:ibkr:0001") == ["ambiguous_suffix"]
    assert sqlite_session.query(AccountBalance).count() == 0


def test_suffix_collision_on_another_date_is_rejected(
    sqlite_session: Session,
) -> None:
    """A different account with the same last four on any date is ambiguous."""
    older = REPORT_DATE - timedelta(days=30)
    add_position(sqlite_session, "U8880001", Decimal("2.00"), report_date=older)
    add_cash(sqlite_session, "U8880001", Decimal("2.00"), report_date=older)
    add_position(sqlite_session, ACCT_INVEST, Decimal("1.00"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("1.00"))
    sqlite_session.commit()
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert _reasons(result, "pp:ibkr:0001") == ["ambiguous_suffix"]
    assert sqlite_session.query(AccountBalance).count() == 0


def test_registered_account_with_no_rows_is_withheld(
    sqlite_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """A registered IBKR account missing from the export must not pass silently."""
    add_position(sqlite_session, ACCT_INVEST, Decimal("10.00"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("5.00"))
    sqlite_session.commit()
    caplog.set_level(logging.INFO)

    result = compute_nightly_totals(sqlite_session, example_registry())

    assert result.inserted == 1
    assert _reasons(result, "pp:ibkr:0002") == ["no_rows_on_report_date"]
    assert result.accounts_withheld == 1
    assert "pp:ibkr:0002" in caplog.text
    # Non-IBKR registry accounts (manual marks) are not expected in the export.
    assert _reasons(result, "pp:bank:0003") == []


def test_cash_dated_a_day_later_is_not_joined(sqlite_session: Session) -> None:
    """Cash for another day is never summed with these positions."""
    next_day = REPORT_DATE + timedelta(days=1)
    for account in (ACCT_INVEST, ACCT_IRA):
        add_position(sqlite_session, account, Decimal("10.00"))
        add_cash(sqlite_session, account, Decimal("5.00"), report_date=next_day)
    sqlite_session.commit()

    result = compute_nightly_totals(sqlite_session, example_registry())

    assert result.report_date == REPORT_DATE
    assert _reasons(result, RUN_KEY) == ["cash_date_ahead"]
    assert _reasons(result, "pp:ibkr:0001") == ["no_usd_cash_row"]
    assert _reasons(result, "pp:ibkr:0002") == ["no_usd_cash_row"]
    assert result.accounts_withheld == 3
    assert sqlite_session.query(AccountBalance).count() == 0


def test_newer_cash_with_complete_older_date_still_exits_nonzero(
    sqlite_session: Session,
) -> None:
    """Re-totalling the older day is fine, but the lag must not exit 0."""
    for account in (ACCT_INVEST, ACCT_IRA):
        add_position(sqlite_session, account, Decimal("10.00"))
        add_cash(sqlite_session, account, Decimal("5.00"))
        add_cash(
            sqlite_session,
            account,
            Decimal("6.00"),
            report_date=REPORT_DATE + timedelta(days=1),
        )
    sqlite_session.commit()
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert result.inserted == 2
    assert [r.reason for r in result.rejections] == ["cash_date_ahead"]
    assert result.accounts_withheld == 1


def test_cash_dated_before_positions_withholds(sqlite_session: Session) -> None:
    for account in (ACCT_INVEST, ACCT_IRA):
        add_position(sqlite_session, account, Decimal("10.00"))
        add_cash(
            sqlite_session,
            account,
            Decimal("5.00"),
            report_date=REPORT_DATE - timedelta(days=1),
        )
    sqlite_session.commit()
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert {r.reason for r in result.rejections} == {"no_usd_cash_row"}
    assert sqlite_session.query(AccountBalance).count() == 0


def test_out_of_range_total_is_withheld(
    sqlite_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    # 2e16 is exact in a double, so it survives SQLite's float storage.
    add_position(sqlite_session, ACCT_INVEST, Decimal("2e16"))
    add_cash(sqlite_session, ACCT_INVEST, Decimal("1.00"))
    sqlite_session.commit()
    caplog.set_level(logging.INFO)
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert _reasons(result, "pp:ibkr:0001") == ["out_of_range"]
    assert sqlite_session.query(AccountBalance).count() == 0
    assert "20000000000000000" not in caplog.text


def test_negative_total_is_allowed_for_a_cash_account(sqlite_session: Session) -> None:
    registry = parse_registry(_CASH_IBKR_SEED)
    add_position(sqlite_session, "U9990003", Decimal("1.00"))
    add_cash(sqlite_session, "U9990003", Decimal("-26.25"))
    sqlite_session.commit()
    result = compute_nightly_totals(sqlite_session, registry)
    assert result.rejections == []
    assert sqlite_session.query(AccountBalance).one().value == Decimal("-25.25")


def test_bad_account_number_is_rejected_without_echoing_it(
    sqlite_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    add_position(sqlite_session, "U77-", Decimal("1.00"))
    add_cash(sqlite_session, "U77-", Decimal("1.00"))
    sqlite_session.commit()
    caplog.set_level(logging.INFO)
    result = compute_nightly_totals(sqlite_session, example_registry())
    assert _reasons(result, UNDERIVABLE_KEY) == ["bad_account_number"] * 2
    assert "U77-" not in caplog.text
    # Two un-keyable rows are one problem, plus the two missing accounts.
    assert result.accounts_withheld == 3


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_value_is_rejected_as_invalid(bad: str) -> None:
    """SQLite cannot store NaN, so the row filter is exercised directly."""
    result = TotalsResult(report_date=REPORT_DATE)
    data = _AccountData(
        account_numbers={ACCT_INVEST},
        positions=[_Row("USD", Decimal(bad))],
        cash=[_Row("USD", Decimal("1.00"))],
    )
    assert _usd_values("pp:ibkr:0001", data, result) is None
    assert [r.reason for r in result.rejections] == ["invalid_value"]


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
    assert _reasons(result, "pp:ibkr:0001") == ["existing_other_source"]
    assert sqlite_session.query(AccountBalance).one().value == Decimal("1.00")
