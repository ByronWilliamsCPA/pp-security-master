"""Shared, dependency-free parse helpers for IBKR Flex record extractors.

These were originally private to ``ibkr_flex``; they are factored out so the
trade parser, the non-trade record parsers, and the persistence service can
share one tolerant date/decimal/string normalization layer.

The module itself is package-internal (underscore prefix), so the helpers
within are deliberately public: callers inside ``security_master.extractor``
import them by name without going through ``ibkr_flex``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

# IBKR Flex date formats vary by query configuration and field. tradeDate and
# settleDate use MM/DD/YYYY; dateTime fields append ";HHMMSS"; an ISO-configured
# query emits YYYYMMDD. The time suffix is split off before format matching.
_DATE_FORMATS = ("%m/%d/%Y", "%Y%m%d", "%Y-%m-%d")


def none_if_empty(value: str | None) -> str | None:
    """Return None for empty or whitespace-only strings, else the value.

    Args:
        value: Raw attribute value, or None when the attribute is absent.

    Returns:
        None when the value is None, empty, or only whitespace; otherwise the
        original string unchanged.
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


# Backward-compatible alias used by ibkr_flex and its existing tests.
_none_if_empty = none_if_empty


def dash_to_none(value: str | None) -> str | None:
    """Normalize the IBKR ``--`` sentinel (and empty) to None.

    Transfer records use ``--`` for absent symbol/isin/description on cash
    transfers; treat it as a null rather than a literal value.

    Args:
        value: Raw attribute value, or None when the attribute is absent.

    Returns:
        None when the value is None, empty, whitespace, or the ``--``
        sentinel; otherwise the original string unchanged.
    """
    cleaned = none_if_empty(value)
    if cleaned is None or cleaned == "--":
        return None
    return cleaned


# Backward-compatible alias.
_dash_to_none = dash_to_none


def parse_decimal(value: str | None) -> Decimal | None:
    """Parse a numeric string into a Decimal, or None when empty.

    Args:
        value: Numeric string read from the XML, or an empty/None value.

    Returns:
        A :class:`decimal.Decimal`, or None when the input is empty or absent.

    Raises:
        ValueError: When a non-empty value is not a valid decimal. The raw
            value is included so the offending attribute is identifiable;
            ``decimal.InvalidOperation`` is re-raised as ``ValueError`` so
            callers that already guard the empty/format paths with ``ValueError``
            also catch malformed numbers instead of seeing an opaque abort.
    """
    cleaned = none_if_empty(value)
    if cleaned is None:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        msg = f"Unparseable IBKR Flex decimal value: {value!r}"
        raise ValueError(msg) from exc


# Backward-compatible alias.
_parse_decimal = parse_decimal


def parse_flex_date(value: str | None) -> date | None:
    """Parse an IBKR Flex date in any supported format, or None when empty.

    Handles ``MM/DD/YYYY``, the same with a ``;HHMMSS`` time suffix, and ISO
    ``YYYYMMDD`` / ``YYYY-MM-DD``.

    Args:
        value: Date string in a supported IBKR Flex format, or an
            empty/None value.

    Returns:
        A :class:`datetime.date`, or None when the input is empty or absent.

    Raises:
        ValueError: When a non-empty value matches no known format.
    """
    cleaned = none_if_empty(value)
    if cleaned is None:
        return None
    datepart = cleaned.split(";", 1)[0].strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(datepart, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    # Reaching here means no format matched OR a matched format held an invalid
    # calendar value (e.g. 02/31/2024), both surface as strptime ValueErrors.
    msg = f"Unrecognized or invalid IBKR Flex date: {value!r}"
    raise ValueError(msg)
