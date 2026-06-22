"""Parsers for IBKR Flex non-trade records: cash, corporate actions, transfers.

Each parser is a pure function mapping one XML element's attributes to a frozen
dataclass shaped to the persistence columns. Faithful ingest: values are
normalized (empty/``--`` to None, dates/decimals typed) but not interpreted
(no split math, no cash-type normalization; those are Layer-2 concerns).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from security_master.extractor._flex_common import (
    dash_to_none,
    none_if_empty,
    parse_decimal,
    parse_flex_date,
)

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET  # nosec B405
    from datetime import date

_NAME_MAX_LEN = 255


@dataclass(frozen=True)
class ParsedCashTransaction:
    """One IBKR Flex CashTransaction mapped to persistence columns."""

    transaction_date: date
    settlement_date: date | None
    transaction_id: str
    action_id: str | None
    transaction_type: str
    dividend_type: str | None
    ex_date: date | None
    security_name: str
    symbol: str | None
    isin: str | None
    cusip: str | None
    figi: str | None
    conid: str | None
    amount: Decimal
    currency: str
    account_number: str | None
    asset_class: str | None
    sec_type: str | None


@dataclass(frozen=True)
class ParsedCorporateAction:
    """One IBKR Flex CorporateAction mapped to persistence columns."""

    transaction_date: date
    transaction_id: str
    action_id: str | None
    transaction_type: str
    action_description: str
    security_name: str
    symbol: str | None
    isin: str | None
    cusip: str | None
    figi: str | None
    conid: str | None
    quantity: Decimal | None
    amount: Decimal
    proceeds: Decimal | None
    realized_pnl: Decimal | None
    currency: str
    account_number: str | None
    asset_class: str | None
    sec_type: str | None


@dataclass(frozen=True)
class ParsedTransfer:
    """One IBKR Flex Transfer mapped to persistence columns."""

    transaction_date: date
    settlement_date: date | None
    transaction_id: str
    transaction_type: str
    direction: str | None
    security_name: str
    symbol: str | None
    isin: str | None
    quantity: Decimal | None
    amount: Decimal
    currency: str
    account_number: str | None
    asset_class: str | None


def _require(value: str | None, field: str, record: str) -> str:
    """Return a required attribute or raise with a precise message.

    Args:
        value: Raw attribute value.
        field: Attribute name (for the error message).
        record: Record type name (for the error message).

    Returns:
        The non-empty attribute value.

    Raises:
        ValueError: When the attribute is empty or absent.
    """
    cleaned = none_if_empty(value)
    if cleaned is None:
        msg = f"IBKR {record} is missing required attribute {field!r}"
        raise ValueError(msg)
    return cleaned


def _require_date(value: str | None, field: str, record: str) -> date:
    """Return a required parsed date or raise with a precise message.

    Args:
        value: Raw date attribute value.
        field: Attribute name (for the error message).
        record: Record type name (for the error message).

    Returns:
        The parsed date.

    Raises:
        ValueError: When the date is empty or absent.
    """
    parsed = parse_flex_date(value)
    if parsed is None:
        msg = f"IBKR {record} is missing required date attribute {field!r}"
        raise ValueError(msg)
    return parsed


def cash_from_element(elem: ET.Element) -> ParsedCashTransaction:
    """Map a ``<CashTransaction>`` element to a ParsedCashTransaction."""
    a = elem.attrib
    settle = parse_flex_date(a.get("settleDate"))
    report = parse_flex_date(a.get("reportDate"))
    txn_date = settle or report
    if txn_date is None:
        msg = "IBKR CashTransaction is missing settleDate and reportDate"
        raise ValueError(msg)
    return ParsedCashTransaction(
        transaction_date=txn_date,
        settlement_date=settle,
        transaction_id=_require(
            a.get("transactionID"), "transactionID", "CashTransaction"
        ),
        action_id=none_if_empty(a.get("actionID")),
        transaction_type=_require(a.get("type"), "type", "CashTransaction"),
        dividend_type=none_if_empty(a.get("dividendType")),
        ex_date=parse_flex_date(a.get("exDate")),
        security_name=(a.get("description") or a.get("type") or "")[:_NAME_MAX_LEN],
        symbol=dash_to_none(a.get("symbol")),
        isin=dash_to_none(a.get("isin")),
        cusip=dash_to_none(a.get("cusip")),
        figi=none_if_empty(a.get("figi")),
        conid=none_if_empty(a.get("conid")),
        amount=parse_decimal(a.get("amount")) or Decimal(0),
        currency=none_if_empty(a.get("currency")) or "USD",
        account_number=none_if_empty(a.get("accountId")),
        asset_class=none_if_empty(a.get("assetCategory")),
        sec_type=none_if_empty(a.get("subCategory")),
    )


def corp_action_from_element(elem: ET.Element) -> ParsedCorporateAction:
    """Map a ``<CorporateAction>`` element to a ParsedCorporateAction."""
    a = elem.attrib
    description = a.get("actionDescription") or a.get("description") or ""
    # transaction_date is reportDate (the settled effective date). The element
    # also carries a dateTime="MM/DD/YYYY;HHMMSS" attribute; it is intentionally
    # NOT ingested, reportDate is the chosen natural date for Layer 1.
    # #EDGE (financial / data integrity): amount maps to the inherited
    # Numeric(15, 2) column, so a sub-cent corporate-action value (e.g.
    # -122532.667322) rounds to cents (-122532.67). proceeds and realized_pnl
    # use Numeric(18, 6) and preserve raw precision: the lossless economics live
    # there, amount is the PP-compatible cents view.
    # #VERIFY: if exact corporate-action cash effects are needed downstream, read
    # proceeds/realized_pnl, not amount, or widen amount and add a migration.
    return ParsedCorporateAction(
        transaction_date=_require_date(
            a.get("reportDate"), "reportDate", "CorporateAction"
        ),
        transaction_id=_require(
            a.get("transactionID"), "transactionID", "CorporateAction"
        ),
        action_id=none_if_empty(a.get("actionID")),
        transaction_type=_require(a.get("type"), "type", "CorporateAction"),
        action_description=description,
        security_name=(a.get("description") or "")[:_NAME_MAX_LEN],
        symbol=dash_to_none(a.get("symbol")),
        isin=dash_to_none(a.get("isin")),
        cusip=dash_to_none(a.get("cusip")),
        figi=none_if_empty(a.get("figi")),
        conid=none_if_empty(a.get("conid")),
        quantity=parse_decimal(a.get("quantity")),
        amount=parse_decimal(a.get("amount")) or Decimal(0),
        proceeds=parse_decimal(a.get("proceeds")),
        realized_pnl=parse_decimal(a.get("fifoPnlRealized")),
        currency=none_if_empty(a.get("currency")) or "USD",
        account_number=none_if_empty(a.get("accountId")),
        asset_class=none_if_empty(a.get("assetCategory")),
        sec_type=none_if_empty(a.get("subCategory")),
    )


def transfer_from_element(elem: ET.Element) -> ParsedTransfer:
    """Map a ``<Transfer>`` element to a ParsedTransfer."""
    a = elem.attrib
    settle = parse_flex_date(a.get("settleDate"))
    txn_date = parse_flex_date(a.get("date")) or settle
    if txn_date is None:
        msg = "IBKR Transfer is missing date and settleDate"
        raise ValueError(msg)
    txn_type = _require(a.get("type"), "type", "Transfer")
    name = dash_to_none(a.get("description")) or txn_type
    return ParsedTransfer(
        transaction_date=txn_date,
        settlement_date=settle,
        transaction_id=_require(a.get("transactionID"), "transactionID", "Transfer"),
        transaction_type=txn_type,
        direction=none_if_empty(a.get("direction")),
        security_name=name[:_NAME_MAX_LEN],
        symbol=dash_to_none(a.get("symbol")),
        isin=dash_to_none(a.get("isin")),
        quantity=parse_decimal(a.get("quantity")),
        amount=parse_decimal(a.get("cashTransfer")) or Decimal(0),
        currency=none_if_empty(a.get("currency")) or "USD",
        account_number=none_if_empty(a.get("accountId")),
        asset_class=none_if_empty(a.get("assetCategory")),
    )
