"""Interactive Brokers Flex Query trade extractor and persistence service.

Parses IBKR Flex Query XML (FlexQueryResponse > FlexStatements >
FlexStatement > Trades > Trade) into mapped :class:`ParsedTrade` records and
persists them to the ``transactions_interactive_brokers`` table.

The parse stage is a pure function (no database, no network) so it can be
unit-tested against a fixture without infrastructure. The persistence stage
is idempotent: ``trade_id`` is unique, and trades whose ``trade_id`` already
exists in the database are skipped rather than re-inserted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # stdlib has complete type stubs; defusedxml.ElementTree re-exports the
    # same API at runtime via the safe parser imported in the else branch.
    import xml.etree.ElementTree as ET  # nosec B405  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
    from datetime import date

    from sqlalchemy.orm import Session
else:
    import defusedxml.ElementTree as ET  # noqa: N817  # safe parser at runtime

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from security_master.extractor._flex_common import (
    none_if_empty,
    parse_decimal,
    parse_flex_date,
)
from security_master.extractor.ibkr_flex_records import (
    ParsedCashTransaction,
    ParsedCorporateAction,
    ParsedTransfer,
    cash_from_element,
    corp_action_from_element,
    transfer_from_element,
)
from security_master.storage.transaction_models import InteractiveBrokersTransaction

# Account name is a constant: the Flex Trade record has no attribute that
# names the institution, so every IBKR row is stamped with this label.
IBKR_ACCOUNT_NAME = "Interactive Brokers"

# security_name maps to the SQLAlchemy String(255) description column.
_SECURITY_NAME_MAX_LEN = 255

# Back-compat aliases: existing call sites and tests used these underscore
# names; keep them to avoid churn across the codebase.
_none_if_empty = none_if_empty
_parse_decimal = parse_decimal
_parse_date = parse_flex_date


@dataclass(frozen=True)
class ParsedTrade:
    """One IBKR Flex Trade mapped to the persistence column shape.

    Fields mirror the columns on :class:`InteractiveBrokersTransaction`. All
    nullable source attributes are normalized so that absent values are None
    rather than empty strings.
    """

    transaction_date: date
    settlement_date: date | None
    transaction_id: str | None
    security_name: str
    symbol: str | None
    isin: str | None
    cusip: str | None
    transaction_type: str
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal
    currency: str
    commission: Decimal | None
    ib_commission: Decimal | None
    account_name: str
    account_number: str | None
    trade_id: str | None
    order_id: str | None
    execution_id: str | None
    exchange: str | None
    multiplier: Decimal | None
    asset_class: str | None
    sec_type: str | None
    strike: Decimal | None
    expiry: date | None
    put_call: str | None
    underlying_symbol: str | None


@dataclass
class ImportSummary:
    """Result of an import run.

    Attributes:
        import_batch_id: Batch identifier stamped onto every row this run.
        trades: Number of trades newly inserted this run (skips excluded).
        skipped: Number of trades skipped because their trade_id already
            existed in the database (idempotency).
        source_file: Path string recorded as the source for inserted rows,
            or None for string-based imports.
    """

    import_batch_id: str
    trades: int = 0
    skipped: int = 0
    source_file: str | None = None


def _trade_from_element(elem: ET.Element) -> ParsedTrade:
    """Map a single ``<Trade>`` element's attributes to a ParsedTrade.

    Args:
        elem: An XML ``<Trade>`` element from the Flex Query response.

    Returns:
        A :class:`ParsedTrade` with every nullable attribute normalized and
        date/decimal fields converted to their typed values.

    Raises:
        ValueError: When the Trade element is missing the required tradeDate
            attribute.
    """
    attr = elem.attrib

    # security_name is NOT NULL; truncate to the column width. Default to an
    # empty-then-truncated value defensively, though description is always
    # present in well-formed Flex output.
    description = (attr.get("description") or "")[:_SECURITY_NAME_MAX_LEN]

    # transaction_date is NOT NULL in the model; tradeDate is always present
    # on a Flex Trade record, so _parse_date will not return None here.
    transaction_date = _parse_date(attr.get("tradeDate"))
    if transaction_date is None:
        msg = "Trade element is missing required tradeDate attribute"
        raise ValueError(msg)

    # #EDGE: several numeric columns round sub-cent precision on persist. price
    # is Numeric(12, 4): a FUND tradePrice with 8 decimals (e.g. 9.70000033)
    # rounds to 9.7000. amount (proceeds) is Numeric(15, 2) and the commissions
    # are Numeric(10, 2): Flex emits sub-cent values for these (the sample has
    # proceeds="-1059.306" and ibCommission="-0.625"), which round to whole
    # cents on persist (-> -1059.31, -0.63). The rounding is bounded to sub-cent,
    # but it is NOT lossless: amount and commission are affected, not only the
    # per-share price readout.
    # #VERIFY: if exact execution prices or proceeds are ever needed downstream,
    # widen the affected column scales (e.g. price Numeric(18, 8), amount
    # Numeric(18, 4)) and add a migration.
    price = _parse_decimal(attr.get("tradePrice"))

    # #ASSUME: well-formed Flex Trade records always carry buySell, proceeds, and
    # currency, so the lenient fallbacks below (transaction_type -> "", amount ->
    # Decimal(0), currency -> "USD") are never exercised in practice. A malformed
    # record missing these would persist invalid economics into NOT NULL columns
    # rather than failing loudly.
    # #VERIFY: if broker exports are ever found to omit these attributes, replace
    # the fallbacks with an explicit raise so bad economics cannot reach the DB.
    return ParsedTrade(
        transaction_date=transaction_date,
        settlement_date=_parse_date(attr.get("settleDateTarget")),
        transaction_id=_none_if_empty(attr.get("transactionID")),
        security_name=description,
        symbol=_none_if_empty(attr.get("symbol")),
        isin=_none_if_empty(attr.get("isin")),
        cusip=_none_if_empty(attr.get("cusip")),
        transaction_type=attr.get("buySell") or "",
        quantity=_parse_decimal(attr.get("quantity")),
        price=price,
        amount=_parse_decimal(attr.get("proceeds")) or Decimal(0),
        currency=_none_if_empty(attr.get("currency")) or "USD",
        commission=_parse_decimal(attr.get("ibCommission")),
        ib_commission=_parse_decimal(attr.get("ibCommission")),
        account_name=IBKR_ACCOUNT_NAME,
        account_number=_none_if_empty(attr.get("accountId")),
        trade_id=_none_if_empty(attr.get("tradeID")),
        order_id=_none_if_empty(attr.get("ibOrderID")),
        execution_id=_none_if_empty(attr.get("ibExecID")),
        exchange=_none_if_empty(attr.get("exchange")),
        multiplier=_parse_decimal(attr.get("multiplier")),
        asset_class=_none_if_empty(attr.get("assetCategory")),
        sec_type=_none_if_empty(attr.get("subCategory")),
        strike=_parse_decimal(attr.get("strike")),
        expiry=_parse_date(attr.get("expiry")),
        put_call=_none_if_empty(attr.get("putCall")),
        underlying_symbol=_none_if_empty(attr.get("underlyingSymbol")),
    )


def parse_ibkr_flex(xml_content: str) -> list[ParsedTrade]:
    """Parse IBKR Flex Query XML into a list of ParsedTrade records.

    Pure function: performs no database or network access. Every ``<Trade>``
    descendant anywhere in the document is mapped, preserving document order.

    Args:
        xml_content: The full IBKR Flex Query XML document as a string.

    Returns:
        List of :class:`ParsedTrade`, one per ``<Trade>`` element, in
        document order.
    """
    root = ET.fromstring(xml_content)
    return [_trade_from_element(trade) for trade in root.findall(".//Trade")]


@dataclass(frozen=True)
class IBKRFlexRecords:
    """All record types parsed from one IBKR Flex document, in document order."""

    trades: list[ParsedTrade]
    cash_transactions: list[ParsedCashTransaction]
    corporate_actions: list[ParsedCorporateAction]
    transfers: list[ParsedTransfer]


def parse_ibkr_flex_records(xml_content: str) -> IBKRFlexRecords:
    """Parse every supported IBKR Flex record type in a single pass.

    Args:
        xml_content: The full IBKR Flex Query XML document as a string.

    Returns:
        An :class:`IBKRFlexRecords` with trades, cash transactions, corporate
        actions, and transfers, each in document order.
    """
    root = ET.fromstring(xml_content)
    return IBKRFlexRecords(
        trades=[_trade_from_element(e) for e in root.findall(".//Trade")],
        cash_transactions=[
            cash_from_element(e) for e in root.findall(".//CashTransaction")
        ],
        corporate_actions=[
            corp_action_from_element(e) for e in root.findall(".//CorporateAction")
        ],
        transfers=[transfer_from_element(e) for e in root.findall(".//Transfer")],
    )


class IBKRFlexImportService:
    """Parse IBKR Flex XML and persist trades idempotently.

    Each call to an import method generates one ``import_batch_id`` and stamps
    it onto every row inserted during that run. Trades whose ``trade_id``
    already exists in the database are skipped, so re-importing the same file
    neither duplicates rows nor raises a unique-constraint error.
    """

    def __init__(self, session: Session) -> None:
        """Store the SQLAlchemy session used for persistence.

        Args:
            session: An active SQLAlchemy session bound to the target engine.
        """
        self.session = session

    @staticmethod
    def _new_batch_id() -> str:
        """Generate a unique import batch identifier.

        Returns:
            A short, collision-resistant batch id of the form ``ibkr-<hex>``.
        """
        return f"ibkr-{uuid4().hex[:12]}"

    def _existing_trade_ids(self, trade_ids: list[str]) -> set[str]:
        """Return the subset of trade_ids already present in the database.

        Args:
            trade_ids: Candidate trade ids to check for prior existence.

        Returns:
            Set of trade ids that already have a row in
            ``transactions_interactive_brokers``.
        """
        if not trade_ids:
            return set()
        rows = (
            self.session.query(InteractiveBrokersTransaction.trade_id)
            .filter(InteractiveBrokersTransaction.trade_id.in_(trade_ids))
            .all()
        )
        return {row[0] for row in rows if row[0] is not None}

    def _persist(
        self,
        trades: list[ParsedTrade],
        source_file: str | None,
    ) -> ImportSummary:
        """Persist parsed trades, skipping any whose trade_id already exists.

        Args:
            trades: Parsed trades to insert.
            source_file: Source file path to record on each row, or None.

        Returns:
            An :class:`ImportSummary` describing inserts and skips for the run.
        """
        batch_id = self._new_batch_id()
        summary = ImportSummary(import_batch_id=batch_id, source_file=source_file)

        # De-duplicate before the existence query: a Flex file can repeat a
        # trade_id (handled below via seen_in_run), and a deduplicated list keeps
        # the IN (...) parameter count proportional to distinct ids, not rows.
        candidate_ids = list({t.trade_id for t in trades if t.trade_id is not None})
        already_present = self._existing_trade_ids(candidate_ids)

        # #CRITICAL: trade_id is the idempotency key (UNIQUE column). Skipping
        # within a single run as well as against the DB prevents a duplicate
        # trade_id inside one file from tripping the unique constraint on flush.
        # #VERIFY: re-importing the same Flex file must leave the row count
        # unchanged (covered by tests/integration/test_ibkr_flex_import.py).
        seen_in_run: set[str] = set()

        for trade in trades:
            tid = trade.trade_id
            if tid is not None and (tid in already_present or tid in seen_in_run):
                summary.skipped += 1
                continue
            if tid is not None:
                seen_in_run.add(tid)

            self.session.add(
                InteractiveBrokersTransaction(
                    transaction_date=trade.transaction_date,
                    settlement_date=trade.settlement_date,
                    transaction_id=trade.transaction_id,
                    security_name=trade.security_name,
                    symbol=trade.symbol,
                    isin=trade.isin,
                    cusip=trade.cusip,
                    transaction_type=trade.transaction_type,
                    quantity=trade.quantity,
                    price=trade.price,
                    amount=trade.amount,
                    currency=trade.currency,
                    commission=trade.commission,
                    account_name=trade.account_name,
                    account_number=trade.account_number,
                    import_batch_id=batch_id,
                    source_file=source_file,
                    trade_id=trade.trade_id,
                    order_id=trade.order_id,
                    execution_id=trade.execution_id,
                    exchange=trade.exchange,
                    multiplier=trade.multiplier,
                    asset_class=trade.asset_class,
                    sec_type=trade.sec_type,
                    strike=trade.strike,
                    expiry=trade.expiry,
                    put_call=trade.put_call,
                    underlying_symbol=trade.underlying_symbol,
                    ib_commission=trade.ib_commission,
                )
            )
            summary.trades += 1

        self.session.commit()
        return summary

    def import_from_string(
        self,
        xml_content: str,
        source_file: str | None = None,
    ) -> ImportSummary:
        """Parse XML from a string and persist the resulting trades.

        Args:
            xml_content: The IBKR Flex Query XML document as a string.
            source_file: Optional source path to record on each inserted row.

        Returns:
            An :class:`ImportSummary` for the run.
        """
        trades = parse_ibkr_flex(xml_content)
        return self._persist(trades, source_file)

    def import_from_file(self, path: str | Path) -> ImportSummary:
        """Read an IBKR Flex XML file from disk and persist its trades.

        Args:
            path: Filesystem path to the IBKR Flex Query XML file.

        Returns:
            An :class:`ImportSummary` for the run, with source_file set to the
            resolved input path.
        """
        file_path = Path(path)
        xml_content = file_path.read_text(encoding="utf-8")
        return self._persist(parse_ibkr_flex(xml_content), str(file_path))
