"""Parser for IBKR Flex <OpenPosition> position snapshots.

<OpenPosition> appears only in a positions Flex query (e.g. IRA_Positions.xml),
never in the trade or activity files. Each element is a point-in-time holding as
of reportDate. Parsing is a pure function (no I/O); persistence is idempotent on
the natural (accountId, reportDate, conid) snapshot key via IBKRPositionsImportService.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET  # nosec B405  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
    from datetime import date
    from decimal import Decimal

    from sqlalchemy.orm import Session
else:
    import defusedxml.ElementTree as ET  # noqa: N817  # safe parser at runtime

from security_master.extractor._flex_common import (
    dash_to_none,
    none_if_empty,
    parse_decimal,
    parse_flex_date,
)
from security_master.storage.position_models import InteractiveBrokersOpenPosition

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


def _require(value: str | None, field: str, record: str = "OpenPosition") -> str:
    """Return a required attribute or raise with a precise message.

    Args:
        value: Raw attribute value.
        field: Attribute name, for the error message.
        record: Record type name, for the error message.

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


def _require_decimal(
    value: str | None, field: str, record: str = "OpenPosition"
) -> Decimal:
    """Return a required decimal attribute or raise with a precise message.

    Args:
        value: Raw numeric attribute value.
        field: Attribute name, for the error message.
        record: Record type name, for the error message.

    Returns:
        The parsed Decimal.

    Raises:
        ValueError: When the attribute is empty or absent.
    """
    parsed = parse_decimal(value)
    if parsed is None:
        msg = f"IBKR {record} is missing required numeric attribute {field!r}"
        raise ValueError(msg)
    return parsed


def _require_date(value: str | None, field: str, record: str = "OpenPosition") -> date:
    """Return a required parsed date or raise with a precise message.

    Args:
        value: Raw date attribute value.
        field: Attribute name, for the error message.
        record: Record type name, for the error message.

    Returns:
        The parsed date.

    Raises:
        ValueError: When the date is empty, absent, or unparseable.
    """
    parsed = parse_flex_date(value)
    if parsed is None:
        msg = f"IBKR {record} is missing required date attribute {field!r}"
        raise ValueError(msg)
    return parsed


def open_position_from_element(elem: ET.Element) -> ParsedOpenPosition:
    """Map one ``<OpenPosition>`` element to a ParsedOpenPosition.

    Args:
        elem: An XML ``<OpenPosition>`` element from a positions Flex query.

    Returns:
        A :class:`ParsedOpenPosition` with nullable attributes normalized and
        date/decimal fields typed.
    """
    a = elem.attrib
    return ParsedOpenPosition(
        account_number=_require(a.get("accountId"), "accountId"),
        report_date=_require_date(a.get("reportDate"), "reportDate"),
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


@dataclass
class PositionImportSummary:
    """Result of a snapshot import run.

    Attributes:
        import_batch_id: Batch identifier stamped onto every row this run.
        positions: Number of snapshot rows newly inserted this run.
        skipped: Number of rows skipped because their (account, report_date,
            conid) key already existed (idempotency).
        source_file: Path string recorded as the source, or None.
    """

    import_batch_id: str
    positions: int = 0
    skipped: int = 0
    source_file: str | None = None


class IBKRPositionsImportService:
    """Parse IBKR positions Flex XML and persist snapshot rows idempotently.

    Each import generates one ``import_batch_id``. A row whose
    ``(account_number, report_date, conid)`` key already exists is skipped, so
    re-importing the same positions file neither duplicates rows nor raises a
    unique-constraint error.
    """

    def __init__(self, session: Session) -> None:
        """Store the SQLAlchemy session used for persistence.

        Args:
            session: An active SQLAlchemy session bound to the target engine.
        """
        self.session = session

    @staticmethod
    def _new_batch_id() -> str:
        """Return a unique snapshot import batch id of the form ``ibkr-pos-<hex>``."""
        return f"ibkr-pos-{uuid4().hex[:12]}"

    def _existing_keys(
        self, keys: list[tuple[str, date, str]]
    ) -> set[tuple[str, date, str]]:
        """Return the subset of snapshot keys already present in the table.

        Args:
            keys: Candidate ``(account_number, report_date, conid)`` tuples.

        Returns:
            The subset already present in ``ibkr_open_positions``.
        """
        if not keys:
            return set()
        accounts = {k[0] for k in keys}
        dates = {k[1] for k in keys}
        conids = {k[2] for k in keys}
        rows = (
            self.session.query(
                InteractiveBrokersOpenPosition.account_number,
                InteractiveBrokersOpenPosition.report_date,
                InteractiveBrokersOpenPosition.conid,
            )
            .filter(
                InteractiveBrokersOpenPosition.account_number.in_(accounts),
                InteractiveBrokersOpenPosition.report_date.in_(dates),
                InteractiveBrokersOpenPosition.conid.in_(conids),
            )
            .all()
        )
        present = {(r[0], r[1], r[2]) for r in rows}
        return {k for k in keys if k in present}

    @staticmethod
    def _orm(
        rec: ParsedOpenPosition,
        batch_id: str,
        source_file: str | None,
    ) -> InteractiveBrokersOpenPosition:
        """Build an ORM row from a parsed open position.

        Args:
            rec: Parsed open-position record.
            batch_id: Import batch identifier for this run.
            source_file: Source file path to stamp on the row, or None.

        Returns:
            An unsaved :class:`InteractiveBrokersOpenPosition` row.
        """
        return InteractiveBrokersOpenPosition(
            account_number=rec.account_number,
            report_date=rec.report_date,
            conid=rec.conid,
            symbol=rec.symbol,
            isin=rec.isin,
            cusip=rec.cusip,
            figi=rec.figi,
            security_name=rec.security_name,
            position=rec.position,
            position_value=rec.position_value,
            mark_price=rec.mark_price,
            cost_basis_money=rec.cost_basis_money,
            cost_basis_price=rec.cost_basis_price,
            currency=rec.currency,
            asset_class=rec.asset_class,
            sub_category=rec.sub_category,
            side=rec.side,
            import_batch_id=batch_id,
            source_file=source_file,
        )

    def _persist(
        self,
        records: list[ParsedOpenPosition],
        source_file: str | None,
    ) -> PositionImportSummary:
        """Persist snapshot rows under one batch id, deduped on the snapshot key.

        Args:
            records: Parsed open-position records from one document.
            source_file: Source file path to stamp on inserted rows, or None.

        Returns:
            A :class:`PositionImportSummary` with inserted and skipped counts.
        """
        batch_id = self._new_batch_id()
        summary = PositionImportSummary(
            import_batch_id=batch_id, source_file=source_file
        )
        keys = [(r.account_number, r.report_date, r.conid) for r in records]
        present = self._existing_keys(keys)
        seen: set[tuple[str, date, str]] = set()
        # #CRITICAL (data integrity): (account_number, report_date, conid) is the
        # snapshot idempotency key; re-import must not duplicate rows.
        # #VERIFY: covered by test_persist_is_idempotent_on_account_date_conid.
        for rec in records:
            key = (rec.account_number, rec.report_date, rec.conid)
            if key in present or key in seen:
                summary.skipped += 1
                continue
            seen.add(key)
            self.session.add(self._orm(rec, batch_id, source_file))
            summary.positions += 1
        self.session.commit()
        return summary

    def import_from_string(
        self,
        xml_content: str,
        source_file: str | None = None,
    ) -> PositionImportSummary:
        """Parse XML from a string and persist all snapshot rows.

        Args:
            xml_content: The IBKR positions Flex Query XML document as a string.
            source_file: Optional source path to record on each inserted row.

        Returns:
            A :class:`PositionImportSummary` for the run.
        """
        return self._persist(parse_ibkr_open_positions(xml_content), source_file)

    def import_from_file(self, path: str | Path) -> PositionImportSummary:
        """Read an IBKR positions Flex XML file and persist all snapshot rows.

        Args:
            path: Filesystem path to the IBKR positions Flex Query XML file.

        Returns:
            A :class:`PositionImportSummary`, with source_file set to the input path.
        """
        file_path = Path(path)
        xml_content = file_path.read_text(encoding="utf-8")
        return self._persist(parse_ibkr_open_positions(xml_content), str(file_path))
