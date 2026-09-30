"""Field rules for ``account_balances`` rows.

Rows are read by other services, so the vocabulary and formats here are a
contract: a ``pp:``-prefixed account key that never carries more than the last
four digits of an account number, one of five categories, a decimal (never
float) value with two places, and a separate currency field.

No message raised from this module contains a balance value or an account
number; callers log these messages verbatim.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, localcontext

CATEGORIES = (
    "Investments",
    "Retirement",
    "Cash",
    "Digital currency",
    "Alternatives",
)

SOURCE_IBKR_FLEX = "ibkr_flex"
SOURCE_MANUAL_MARK = "manual_mark"
FEED_SOURCES = ("simplefin", "plaid")

# MVP is USD only. Rows in any other currency are rejected, never converted.
SUPPORTED_CURRENCY = "USD"

KEY_PREFIX = "pp:"
IBKR_KEY_PREFIX = "pp:ibkr:"

_CENT = Decimal("0.01")
# Numeric(18, 2) holds at most sixteen integer digits.
_MAX_ABS_VALUE = Decimal(10) ** 16

_KEY_RE = re.compile(r"^pp:[a-z0-9][a-z0-9_-]*(:[a-z0-9][a-z0-9_-]*)*$")
# Five digits in a row could be most of an account number; four is the limit.
_LONG_DIGIT_RUN_RE = re.compile(r"\d{5,}")
_SOURCE_RE = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
_MONEY_RE = re.compile(r"^-?\d{1,16}(\.\d{1,2})?$")


class BalanceRuleError(ValueError):
    """A value or key violates the account_balances field rules."""


def validate_account_key(key: str) -> str:
    """Validate a stable ``pp:``-prefixed account key.

    Args:
        key: Candidate account key, e.g. ``"pp:ibkr:0001"``.

    Returns:
        The key, unchanged.

    Raises:
        BalanceRuleError: When the key lacks the prefix, uses characters outside
            lowercase alphanumerics, ``_``, ``-`` and ``:``, or contains a run
            of five or more digits (more than a last-four suffix).
    """
    if not _KEY_RE.fullmatch(key):
        msg = "account key must be 'pp:'-prefixed lowercase segments (a-z, 0-9, _, -)"
        raise BalanceRuleError(msg)
    if _LONG_DIGIT_RUN_RE.search(key):
        msg = "account key must not contain more than four consecutive digits"
        raise BalanceRuleError(msg)
    if len(key) > 100:
        msg = "account key must be at most 100 characters"
        raise BalanceRuleError(msg)
    return key


def validate_category(category: str) -> str:
    """Validate a category against the fixed five-value vocabulary.

    Args:
        category: Candidate category label.

    Returns:
        The category, unchanged.

    Raises:
        BalanceRuleError: When the category is not one of :data:`CATEGORIES`.
    """
    if category not in CATEGORIES:
        msg = f"category must be exactly one of: {', '.join(CATEGORIES)}"
        raise BalanceRuleError(msg)
    return category


def validate_source(source: str) -> str:
    """Validate a source token (``ibkr_flex``, ``manual_mark``, or a feed name).

    Args:
        source: Candidate source label.

    Returns:
        The source, unchanged.

    Raises:
        BalanceRuleError: When the token is not a short lowercase identifier.
    """
    if not _SOURCE_RE.fullmatch(source):
        msg = "source must be a lowercase identifier of at most 30 characters"
        raise BalanceRuleError(msg)
    return source


def ibkr_account_key(account_number: str) -> str:
    """Derive the stable account key for an IBKR account.

    Only the last four characters of the account number are used, so the full
    number never reaches the balances table, logs, or the registry seed.

    Args:
        account_number: The IBKR account id from a Flex export.

    Returns:
        A key of the form ``pp:ibkr:<last four, lowercased>``.

    Raises:
        BalanceRuleError: When the account number is empty or its suffix is not
            alphanumeric.
    """
    suffix = account_number.strip()[-4:].lower()
    if not suffix.isalnum():
        msg = "IBKR account number has no usable alphanumeric suffix"
        raise BalanceRuleError(msg)
    return validate_account_key(f"{IBKR_KEY_PREFIX}{suffix}")


def parse_money(text: str) -> Decimal:
    """Parse operator-entered money text into an exact two-place Decimal.

    Accepts an optional leading ``-`` and at most two decimal places. Rejects
    thousands separators, exponents, ``NaN``, ``Infinity``, and floats-in-text
    such as ``1e3`` so nothing is silently rounded or reinterpreted.

    Args:
        text: The value as typed, e.g. ``"1234.56"``.

    Returns:
        The exact Decimal, quantized to two places.

    Raises:
        BalanceRuleError: When the text is not a plain decimal with at most two
            places within the Numeric(18, 2) range. The text is not echoed.
    """
    cleaned = text.strip()
    if not _MONEY_RE.fullmatch(cleaned):
        msg = "value must be a plain decimal with at most two places, e.g. 1234.56"
        raise BalanceRuleError(msg)
    return check_range(_normalize_zero(Decimal(cleaned).quantize(_CENT)))


def check_range(value: Decimal) -> Decimal:
    """Ensure a two-place value fits the ``Numeric(18, 2)`` column.

    Args:
        value: A finite, already-quantized Decimal.

    Returns:
        The value, unchanged.

    Raises:
        BalanceRuleError: When the magnitude exceeds sixteen integer digits.
    """
    if abs(value) >= _MAX_ABS_VALUE:
        msg = "value exceeds the supported range"
        raise BalanceRuleError(msg)
    return value


def quantize_cents(value: Decimal) -> Decimal:
    """Round a Decimal to two places, half away from zero, in a wide context.

    The default 28-digit context could itself round a large exact sum before
    this single, deliberate rounding to cents; a 60-digit context cannot.

    Args:
        value: A finite Decimal of any scale.

    Returns:
        The value quantized to ``0.01``, with negative zero normalized to zero.
    """
    with localcontext() as ctx:
        ctx.prec = 60
        return _normalize_zero(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def _normalize_zero(value: Decimal) -> Decimal:
    """Return ``0.00`` for a negative zero so it never serializes as ``-0.00``."""
    return abs(value) if value == 0 else value


def format_money(value: Decimal) -> str:
    """Serialize a value as a two-place decimal string, never a float.

    Args:
        value: The balance value.

    Returns:
        A plain decimal string such as ``"1234.56"`` or ``"-5.00"``, with no
        exponent and no thousands separator.
    """
    return format(quantize_cents(value), "f")
