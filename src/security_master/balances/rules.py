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
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, localcontext

CATEGORIES = (
    "Investments",
    "Retirement",
    "Cash",
    "Digital currency",
    "Alternatives",
)
# The only category whose balance may be negative (an overdraft).
CASH_CATEGORY = "Cash"

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
# [0-9], not \d: \d also matches non-ASCII digits such as fullwidth forms.
_MONEY_RE = re.compile(r"^-?[0-9]{1,16}(\.[0-9]{1,2})?$")
# Characters allowed in free text despite being Unicode controls (category Cc).
_ALLOWED_CONTROLS = frozenset("\n\t")


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
            lowercase alphanumerics, ``_``, ``-`` and ``:``, contains a run of
            five or more digits (more than a last-four suffix), or is longer
            than 100 characters.
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
        BalanceRuleError: When the stripped account number is empty, or its
            last four characters (all of it, if shorter) are not all
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
    """Ensure a value is finite and fits the ``Numeric(18, 2)`` column.

    Args:
        value: The Decimal to check, normally already quantized to cents.

    Returns:
        The value, unchanged.

    Raises:
        BalanceRuleError: When the value is NaN or infinite, or its magnitude
            exceeds sixteen integer digits.
    """
    _require_finite(value)
    if abs(value) >= _MAX_ABS_VALUE:
        msg = "value exceeds the supported range"
        raise BalanceRuleError(msg)
    return value


def quantize_cents(value: Decimal) -> Decimal:
    """Round a Decimal to two places, half away from zero, in a wide context.

    ``quantize`` raises ``InvalidOperation`` when its result needs more digits
    than the context precision, so under the default 28-digit context a value
    with more than 26 integer digits could not be rounded at all. The 60-digit
    context makes the rounding total for any value a sum can produce. A NaN
    or infinite value raises ``BalanceRuleError`` (from the finiteness check).

    Args:
        value: A Decimal of any scale.

    Returns:
        The value quantized to ``0.01``, with negative zero normalized to zero.
    """
    _require_finite(value)
    with localcontext() as ctx:
        ctx.prec = 60
        return _normalize_zero(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def require_cents(value: Decimal) -> Decimal:
    """Ensure a value is finite, in range, and has at most two decimal places.

    Unlike :func:`quantize_cents` this never rounds: a sub-cent input is an
    error, so nothing an API caller passes is silently changed.

    Args:
        value: The candidate balance.

    Returns:
        The value quantized to exactly two places (trailing zeros only).

    Raises:
        BalanceRuleError: When the value is not finite, has more than two
            decimal places, or exceeds the ``Numeric(18, 2)`` range.
    """
    cents = quantize_cents(value)
    if cents != value:
        msg = "value must have at most two decimal places"
        raise BalanceRuleError(msg)
    return check_range(cents)


def check_sign(value: Decimal, category: str) -> Decimal:
    """Allow a negative value only for a Cash account (an overdraft).

    Args:
        value: The balance value.
        category: The account's category.

    Returns:
        The value, unchanged.

    Raises:
        BalanceRuleError: When the value is negative and the category is not
            :data:`CASH_CATEGORY`.
    """
    if value < 0 and category != CASH_CATEGORY:
        msg = "a negative value is only allowed for Cash accounts (overdraft)"
        raise BalanceRuleError(msg)
    return value


def check_plain_text(text: str, field: str, *, multiline: bool = False) -> str:
    """Reject control characters (terminal escapes) in operator-entered text.

    Every Unicode control character, including the escape that starts an ANSI
    sequence, is refused so stored text cannot rewrite a terminal when it is
    listed later. ``multiline`` text may still contain newlines and tabs.

    Args:
        text: The text to check.
        field: Field name for the error message.
        multiline: Allow newlines and tabs (free-text notes).

    Returns:
        The text, unchanged.

    Raises:
        BalanceRuleError: When the text contains a disallowed control character.
    """
    allowed: frozenset[str] = _ALLOWED_CONTROLS if multiline else frozenset()
    if any(unicodedata.category(ch) == "Cc" and ch not in allowed for ch in text):
        msg = f"{field} must not contain control characters"
        raise BalanceRuleError(msg)
    return text


def _require_finite(value: Decimal) -> None:
    """Raise a rule error for NaN or an infinity.

    Args:
        value: The Decimal to check.

    Raises:
        BalanceRuleError: When the value is not finite.
    """
    if not value.is_finite():
        msg = "value must be a finite number"
        raise BalanceRuleError(msg)


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
