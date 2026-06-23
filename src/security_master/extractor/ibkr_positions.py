"""Parser for IBKR Flex <OpenPosition> position snapshots.

<OpenPosition> appears only in a positions Flex query (e.g. IRA_Positions.xml),
never in the trade or activity files. Each element is a point-in-time holding as
of reportDate. Parsing is a pure function (no I/O); persistence is idempotent on
the natural (accountId, reportDate, conid) snapshot key and will be added in a
later task.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET  # nosec B405  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
    from datetime import date
    from decimal import Decimal
else:
    import defusedxml.ElementTree as ET  # noqa: N817  # safe parser at runtime

from security_master.extractor._flex_common import (
    dash_to_none,
    none_if_empty,
    parse_decimal,
    parse_flex_date,
)

_NAME_MAX_LEN = 255


@dataclass(frozen=True)
class ParsedOpenPosition:
    """One IBKR Flex OpenPosition mapped to the snapshot persistence columns."""

    account_number: str
    report_date: date
    conid: str
    symbol: str | None
    isin: str | None
    cusip: str | None
    figi: str | None
    security_name: str
    position: Decimal
    position_value: Decimal | None
    mark_price: Decimal | None
    cost_basis_money: Decimal | None
    cost_basis_price: Decimal | None
    currency: str
    asset_class: str | None
    sub_category: str | None
    side: str | None


def _require(value: str | None, field: str) -> str:
    """Return a required attribute or raise with a precise message.

    Args:
        value: Raw attribute value.
        field: Attribute name, for the error message.

    Returns:
        The non-empty attribute value.

    Raises:
        ValueError: When the attribute is empty or absent.
    """
    cleaned = none_if_empty(value)
    if cleaned is None:
        msg = f"IBKR OpenPosition is missing required attribute {field!r}"
        raise ValueError(msg)
    return cleaned


def _require_decimal(value: str | None, field: str) -> Decimal:
    """Return a required decimal attribute or raise with a precise message.

    Args:
        value: Raw numeric attribute value.
        field: Attribute name, for the error message.

    Returns:
        The parsed Decimal.

    Raises:
        ValueError: When the attribute is empty or absent.
    """
    parsed = parse_decimal(value)
    if parsed is None:
        msg = f"IBKR OpenPosition is missing required numeric attribute {field!r}"
        raise ValueError(msg)
    return parsed


def open_position_from_element(elem: ET.Element) -> ParsedOpenPosition:
    """Map one ``<OpenPosition>`` element to a ParsedOpenPosition.

    Args:
        elem: An XML ``<OpenPosition>`` element from a positions Flex query.

    Returns:
        A :class:`ParsedOpenPosition` with nullable attributes normalized and
        date/decimal fields typed.

    Raises:
        ValueError: When a required attribute (accountId, reportDate, conid,
            position, currency) is absent.
    """
    a = elem.attrib
    report_date = parse_flex_date(a.get("reportDate"))
    if report_date is None:
        msg = "IBKR OpenPosition is missing required attribute 'reportDate'"
        raise ValueError(msg)
    return ParsedOpenPosition(
        account_number=_require(a.get("accountId"), "accountId"),
        report_date=report_date,
        conid=_require(a.get("conid"), "conid"),
        symbol=dash_to_none(a.get("symbol")),
        isin=dash_to_none(a.get("isin")),
        cusip=dash_to_none(a.get("cusip")),
        figi=none_if_empty(a.get("figi")),
        security_name=(a.get("description") or "")[:_NAME_MAX_LEN],
        position=_require_decimal(a.get("position"), "position"),
        position_value=parse_decimal(a.get("positionValue")),
        mark_price=parse_decimal(a.get("markPrice")),
        cost_basis_money=parse_decimal(a.get("costBasisMoney")),
        cost_basis_price=parse_decimal(a.get("costBasisPrice")),
        currency=_require(a.get("currency"), "currency"),
        asset_class=none_if_empty(a.get("assetCategory")),
        sub_category=none_if_empty(a.get("subCategory")),
        side=none_if_empty(a.get("side")),
    )


def parse_ibkr_open_positions(xml_content: str) -> list[ParsedOpenPosition]:
    """Parse every ``<OpenPosition>`` in an IBKR positions Flex document.

    Pure function: no database or network access. Every ``<OpenPosition>``
    descendant is mapped in document order.

    Args:
        xml_content: The full IBKR positions Flex Query XML document as a string.

    Returns:
        List of :class:`ParsedOpenPosition`, one per element, in document order.
    """
    root = ET.fromstring(xml_content)
    return [open_position_from_element(e) for e in root.findall(".//OpenPosition")]
