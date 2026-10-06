"""Unit tests for the account_balances field rules."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from security_master.balances.rules import (
    CASH_CATEGORY,
    CATEGORIES,
    BalanceRuleError,
    check_plain_text,
    check_range,
    check_sign,
    format_money,
    ibkr_account_key,
    parse_money,
    quantize_cents,
    require_cents,
    validate_account_key,
    validate_category,
    validate_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.storage]


@pytest.mark.parametrize("key", ["pp:ibkr:0001", "pp:bank:abcd", "pp:simplefin:x-1_2"])
def test_valid_keys_pass(key: str) -> None:
    assert validate_account_key(key) == key


@pytest.mark.parametrize(
    "key",
    [
        "ibkr:0001",  # missing prefix
        "PP:ibkr:0001",  # uppercase
        "pp:",  # empty segment
        "pp:ibkr:",  # trailing empty segment
        "pp:ibkr:12345",  # five digits: more than a last-four suffix
        "pp:ibkr:U9990001",  # full account number
        "pp:ibkr: 0001",  # whitespace
    ],
)
def test_invalid_keys_are_rejected(key: str) -> None:
    with pytest.raises(BalanceRuleError):
        validate_account_key(key)


def test_ibkr_key_uses_last_four_only() -> None:
    key = ibkr_account_key("U9990001")
    assert key == "pp:ibkr:0001"
    assert "9990" not in key


def test_ibkr_key_rejects_unusable_suffix() -> None:
    with pytest.raises(BalanceRuleError):
        ibkr_account_key("  ")


def test_categories_are_exactly_the_five() -> None:
    assert CATEGORIES == (
        "Investments",
        "Retirement",
        "Cash",
        "Digital currency",
        "Alternatives",
    )
    for category in CATEGORIES:
        assert validate_category(category) == category
    with pytest.raises(BalanceRuleError):
        validate_category("investments")  # case matters


def test_source_tokens() -> None:
    for ok in ("ibkr_flex", "manual_mark", "simplefin", "plaid"):
        assert validate_source(ok) == ok
    for bad in ("", "Manual", "a b", "1abc", "x" * 31):
        with pytest.raises(BalanceRuleError):
            validate_source(bad)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1234.56", "1234.56"),
        ("1234", "1234.00"),
        ("0.5", "0.50"),
        ("-25.10", "-25.10"),
        ("-0", "0.00"),
        ("  7.00 ", "7.00"),
    ],
)
def test_parse_money_accepts_plain_decimals(text: str, expected: str) -> None:
    assert format_money(parse_money(text)) == expected


@pytest.mark.parametrize(
    "text",
    ["1,234.56", "1e3", "NaN", "Infinity", "12.345", "", "abc", "+5", "1" * 17],
)
def test_parse_money_rejects_and_never_echoes(text: str) -> None:
    with pytest.raises(BalanceRuleError) as info:
        parse_money(text)
    if text.strip():
        assert text not in str(info.value)


def test_quantize_rounds_half_away_from_zero_and_avoids_negative_zero() -> None:
    assert quantize_cents(Decimal("0.005")) == Decimal("0.01")
    assert quantize_cents(Decimal("-0.005")) == Decimal("-0.01")
    assert quantize_cents(Decimal("0.004")) == Decimal("0.00")
    assert str(quantize_cents(Decimal("-0.004"))) == "0.00"


@given(
    st.decimals(
        min_value=Decimal("-1e15"),
        max_value=Decimal("1e15"),
        places=6,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_format_money_is_always_a_two_place_plain_decimal_string(
    value: Decimal,
) -> None:
    text = format_money(value)
    whole, _, frac = text.partition(".")
    assert len(frac) == 2
    assert "e" not in text.lower()
    assert whole.lstrip("-").isdigit()
    assert Decimal(text) == quantize_cents(value)


# Built from code points so the source stays ASCII: fullwidth "12.34",
# Arabic-Indic "12", and a superscript two.
_NON_ASCII_DIGITS = [
    "".join(map(chr, (0xFF11, 0xFF12))) + "." + "".join(map(chr, (0xFF13, 0xFF14))),
    "".join(map(chr, (0x0661, 0x0662))),
    "1" + chr(0x00B2),
]


@pytest.mark.parametrize("text", _NON_ASCII_DIGITS)
def test_parse_money_rejects_non_ascii_digits(text: str) -> None:
    with pytest.raises(BalanceRuleError):
        parse_money(text)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_quantize_and_range_reject_non_finite_values(bad: str) -> None:
    with pytest.raises(BalanceRuleError, match="finite"):
        quantize_cents(Decimal(bad))
    with pytest.raises(BalanceRuleError, match="finite"):
        check_range(Decimal(bad))


def test_require_cents_never_rounds() -> None:
    assert str(require_cents(Decimal("1.5"))) == "1.50"
    with pytest.raises(BalanceRuleError, match="two decimal places"):
        require_cents(Decimal("1.005"))


def test_check_sign_allows_negative_only_for_cash() -> None:
    assert check_sign(Decimal("-1.00"), CASH_CATEGORY) == Decimal("-1.00")
    assert check_sign(Decimal(0), "Investments") == Decimal(0)
    with pytest.raises(BalanceRuleError, match="Cash"):
        check_sign(Decimal("-0.01"), "Investments")


def test_check_plain_text_rejects_controls_but_allows_note_newlines() -> None:
    assert check_plain_text("line one\nline two\t!", "note", multiline=True)
    for text in ("a\x1b[31mb", "a\x00b", "a\x7fb"):
        with pytest.raises(BalanceRuleError, match="control characters"):
            check_plain_text(text, "note", multiline=True)
    with pytest.raises(BalanceRuleError, match="entered-by"):
        check_plain_text("a\nb", "entered-by")
