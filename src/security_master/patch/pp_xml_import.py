"""Portfolio Performance XML import service.

Parses a Portfolio Performance ``client.xml`` backup into the database. This is
the inverse of :mod:`security_master.patch.pp_xml_export`: it reads the same
simplified PP schema that the exporter writes (and that the curated
``sample_data`` fixtures use) and persists it via SQLAlchemy.

The module is split into two layers so the parsing logic is testable without a
database:

* :func:`parse_client` is pure: XML string in, :class:`ParsedClient` dataclasses
  out. No database, no side effects.
* :class:`PPXMLImportService` maps a :class:`ParsedClient` onto ORM rows and
  persists them through a session.

Scope (2026-06-20): client configuration, securities with full price history,
accounts, portfolios, bookmarks, and the by-value account-transactions with
their fee/tax units (positional ``security[N]`` references resolved).

PP serializes transactions with XStream object-identity references: a
transaction is defined once by value, and every later appearance is an empty
``reference="..."`` pointer. This importer keeps the by-value account
transactions and skips the reference pointers. Importing the full transaction
graph (portfolio transactions, which live inside account ``crossEntry`` blocks,
and the cross-entry linkage between the two) requires resolving those XStream
references and is the next increment. Only ``cross_entry_type`` is recorded for
now. See ``docs/project/ROADMAP_2026-06-19.md`` Phase C and ADR-014.
"""

from __future__ import annotations

import uuid as uuid_module
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # stdlib has complete type stubs; defusedxml re-exports the same API.
    import xml.etree.ElementTree as ET  # nosec B405

    from sqlalchemy.orm import Session
else:
    import defusedxml.ElementTree as ET  # noqa: N817  # safe parser at runtime

from security_master.storage.models import SecurityMaster
from security_master.storage.pp_models import (
    PPAccount,
    PPAccountTransaction,
    PPBookmark,
    PPClientConfig,
    PPPortfolio,
    PPSecurityPrice,
    PPTransactionUnit,
)

_DEFAULT_FEED = "PP"
# PP serializes monetary amounts as integer cents and share counts scaled by
# 1e8. These invert the exporter's ``int(value * scale)`` conversions.
_PP_AMOUNT_SCALE = Decimal(100)
_PP_SHARES_SCALE = Decimal(10**8)


@dataclass(frozen=True)
class ParsedPrice:
    """A single historical price point for a security."""

    price_date: date
    value: int  # raw PP integer (price * 1e8), stored verbatim


@dataclass
class ParsedSecurity:
    """A security definition with its price history, parsed from XML."""

    name: str
    currency: str = "USD"
    note: str | None = None
    isin: str | None = None
    symbol: str | None = None
    wkn: str | None = None
    feed: str = _DEFAULT_FEED
    prices: list[ParsedPrice] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedUnit:
    """A fee or tax unit attached to a transaction."""

    unit_type: str
    amount: Decimal
    currency: str


@dataclass
class ParsedTransaction:
    """An account-level transaction parsed from XML.

    ``security_position`` is the 1-based index from a positional security
    reference (``securities/security[N]``); it is resolved to a security id
    during persistence. ``None`` when the transaction has no security.
    """

    uuid: str
    transaction_date: date
    amount: Decimal
    shares: Decimal
    transaction_type: str
    currency_code: str = "USD"
    security_position: int | None = None
    cross_entry_type: str | None = None
    units: list[ParsedUnit] = field(default_factory=list)


@dataclass
class ParsedAccount:
    """A top-level deposit account with its transactions."""

    uuid: str
    name: str
    currency_code: str = "USD"
    is_retired: bool = False
    transactions: list[ParsedTransaction] = field(default_factory=list)


@dataclass
class ParsedPortfolio:
    """A top-level securities portfolio."""

    uuid: str
    name: str
    is_retired: bool = False
    reference_account_uuid: str | None = None


@dataclass
class ParsedBookmark:
    """A dashboard bookmark entry."""

    label: str
    pattern: str
    sort_order: int


@dataclass
class ParsedClient:
    """The full parsed contents of a PP ``client.xml`` (supported subset)."""

    version: int
    base_currency: str
    securities: list[ParsedSecurity] = field(default_factory=list)
    accounts: list[ParsedAccount] = field(default_factory=list)
    portfolios: list[ParsedPortfolio] = field(default_factory=list)
    bookmarks: list[ParsedBookmark] = field(default_factory=list)

    @property
    def price_count(self) -> int:
        """Total number of price points across all securities."""
        return sum(len(s.prices) for s in self.securities)


@dataclass
class ImportSummary:
    """Counts of rows created by an import run."""

    config_version: int
    securities: int = 0
    prices: int = 0
    accounts: int = 0
    portfolios: int = 0
    bookmarks: int = 0
    account_transactions: int = 0
    transaction_units: int = 0


def _parse_bool(text: str | None) -> bool:
    """Parse a PP boolean element ("true"/"false") into a Python bool."""
    return (text or "").strip().lower() == "true"


def _text(elem: ET.Element, tag: str) -> str | None:
    """Return the stripped text of a child element, or None if absent/empty."""
    child = elem.find(tag)
    if child is None or child.text is None:
        return None
    stripped = child.text.strip()
    return stripped or None


def _parse_security(elem: ET.Element) -> ParsedSecurity:
    """Parse a single ``<security>`` element into a ParsedSecurity."""
    prices: list[ParsedPrice] = []
    prices_elem = elem.find("prices")
    if prices_elem is not None:
        for price_elem in prices_elem.findall("price"):
            t = price_elem.get("t")
            v = price_elem.get("v")
            if t is None or v is None:
                continue
            prices.append(ParsedPrice(price_date=date.fromisoformat(t), value=int(v)))

    return ParsedSecurity(
        name=_text(elem, "name") or "",
        currency=_text(elem, "currencyCode") or "USD",
        note=_text(elem, "note"),
        isin=_text(elem, "isin"),
        symbol=_text(elem, "tickerSymbol"),
        wkn=_text(elem, "wkn"),
        feed=_text(elem, "feed") or _DEFAULT_FEED,
        prices=prices,
    )


def _parse_portfolio(elem: ET.Element) -> ParsedPortfolio:
    """Parse a single top-level ``<portfolio>`` element."""
    ref_account_uuid: str | None = None
    ref_account = elem.find("referenceAccount")
    if ref_account is not None:
        ref_account_uuid = _text(ref_account, "uuid")

    return ParsedPortfolio(
        uuid=_text(elem, "uuid") or "",
        name=_text(elem, "name") or "",
        is_retired=_parse_bool(_text(elem, "isRetired")),
        reference_account_uuid=ref_account_uuid,
    )


def _parse_security_position(elem: ET.Element) -> int | None:
    """Extract the 1-based index from a positional ``<security reference=...>``.

    PP references a security as ``.../securities/security[N]``. Returns N, or
    None when the transaction has no security reference.
    """
    security_elem = elem.find("security")
    if security_elem is None:
        return None
    reference = security_elem.get("reference")
    if reference is None or "[" not in reference:
        return None
    index_text = reference.rsplit("[", 1)[-1].rstrip("]")
    return int(index_text) if index_text.isdigit() else None


def _parse_unit(elem: ET.Element) -> ParsedUnit | None:
    """Parse a single ``<unit>`` (fee/tax) element, or None when malformed."""
    amount_elem = elem.find("amount")
    if amount_elem is None:
        return None
    raw_amount = amount_elem.get("amount")
    if raw_amount is None:
        return None
    return ParsedUnit(
        unit_type=elem.get("type") or "",
        amount=Decimal(raw_amount) / _PP_AMOUNT_SCALE,
        currency=amount_elem.get("currency") or "USD",
    )


def _parse_account_transaction(elem: ET.Element) -> ParsedTransaction | None:
    """Parse a single ``<account-transaction>`` element.

    Returns None for XStream reference pointers (``<account-transaction
    reference="..."/>``, which carry no content) and for any element missing the
    required uuid/date/amount.
    """
    if elem.get("reference") is not None:
        return None

    uuid_text = _text(elem, "uuid")
    date_text = _text(elem, "date")
    amount_text = _text(elem, "amount")
    if uuid_text is None or date_text is None or amount_text is None:
        return None

    cross_entry = elem.find("crossEntry")
    units = [
        unit
        for unit_elem in elem.findall("units/unit")
        if (unit := _parse_unit(unit_elem)) is not None
    ]
    shares_text = _text(elem, "shares") or "0"
    return ParsedTransaction(
        uuid=uuid_text,
        # PP serializes the date as ``YYYY-MM-DDT00:00``; keep the date part.
        transaction_date=date.fromisoformat(date_text.split("T", 1)[0]),
        amount=Decimal(amount_text) / _PP_AMOUNT_SCALE,
        shares=Decimal(shares_text) / _PP_SHARES_SCALE,
        transaction_type=_text(elem, "type") or "",
        currency_code=_text(elem, "currencyCode") or "USD",
        security_position=_parse_security_position(elem),
        cross_entry_type=cross_entry.get("class") if cross_entry is not None else None,
        units=units,
    )


def _parse_account(elem: ET.Element) -> ParsedAccount:
    """Parse a top-level ``<account>`` including its account-transactions."""
    transactions = [
        txn
        for txn_elem in elem.findall("transactions/account-transaction")
        if (txn := _parse_account_transaction(txn_elem)) is not None
    ]
    return ParsedAccount(
        uuid=_text(elem, "uuid") or "",
        name=_text(elem, "name") or "",
        currency_code=_text(elem, "currencyCode") or "USD",
        is_retired=_parse_bool(_text(elem, "isRetired")),
        transactions=transactions,
    )


def parse_client(xml_content: str) -> ParsedClient:
    """Parse a PP ``client.xml`` string into a :class:`ParsedClient`.

    Pure function: no database access and no side effects. Parses config,
    securities with prices, accounts with their account-transactions and units,
    portfolios, and bookmarks. Portfolio-transactions (nested in account
    cross-entries via XStream references) and watchlists are not parsed.

    Args:
        xml_content: The full XML document as a string.

    Returns:
        A :class:`ParsedClient` describing the supported entities.

    Raises:
        ValueError: When the document is missing the ``<version>`` element.
    """
    root = ET.fromstring(xml_content)  # defusedxml at runtime

    version_text = root.findtext("version")
    if version_text is None:
        msg = "PP client XML is missing the required <version> element"
        raise ValueError(msg)

    client = ParsedClient(
        version=int(version_text),
        base_currency=root.findtext("baseCurrency") or "USD",
    )

    client.securities = [
        _parse_security(s) for s in root.findall("securities/security")
    ]
    # Skip degenerate placeholder entries that carry no uuid (the PP export can
    # contain an empty <account/> / <portfolio/> with no identity or name).
    client.accounts = [
        _parse_account(a) for a in root.findall("accounts/account") if _text(a, "uuid")
    ]
    client.portfolios = [
        _parse_portfolio(p)
        for p in root.findall("portfolios/portfolio")
        if _text(p, "uuid")
    ]
    client.bookmarks = [
        ParsedBookmark(
            label=_text(b, "label") or "",
            pattern=_text(b, "pattern") or "",
            sort_order=index,
        )
        for index, b in enumerate(root.findall("settings/bookmarks/bookmark"))
    ]

    return client


class PPXMLImportService:
    """Persist a parsed PP client backup into the database.

    Inverse of :class:`security_master.patch.pp_xml_export.PPXMLExportService`
    for the supported entity subset.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def import_from_file(
        self,
        file_path: str,
        config_name: str = "default",
    ) -> ImportSummary:
        """Import a PP backup from a file path.

        Args:
            file_path: Path to the PP ``client.xml`` backup.
            config_name: Name to assign to the created PPClientConfig record.

        Returns:
            An :class:`ImportSummary` with per-entity row counts.
        """
        xml_content = Path(file_path).read_text(encoding="utf-8")
        return self.import_from_string(xml_content, config_name)

    def import_from_string(
        self,
        xml_content: str,
        config_name: str = "default",
    ) -> ImportSummary:
        """Import a PP backup from an XML string.

        Persists the supported entities and flushes the session (the caller is
        responsible for committing). Existing securities are matched by ISIN so
        re-importing does not create duplicates.

        Args:
            xml_content: The full PP ``client.xml`` document as a string.
            config_name: Name to assign to the created PPClientConfig record.

        Returns:
            An :class:`ImportSummary` with per-entity row counts.
        """
        client = parse_client(xml_content)
        summary = ImportSummary(config_version=client.version)

        self._persist_config(client, config_name)
        summary.securities, summary.prices, position_to_id = self._persist_securities(
            client
        )
        account_uuid_to_id = self._persist_accounts(client)
        summary.accounts = len(account_uuid_to_id)
        summary.portfolios = self._persist_portfolios(client, account_uuid_to_id)
        summary.bookmarks = self._persist_bookmarks(client)
        summary.account_transactions, summary.transaction_units = (
            self._persist_account_transactions(
                client,
                account_uuid_to_id,
                position_to_id,
            )
        )

        self.session.flush()
        return summary

    def _persist_config(self, client: ParsedClient, config_name: str) -> None:
        """Create or refresh the active PPClientConfig for this backup."""
        existing = (
            self.session.query(PPClientConfig)
            .filter_by(config_name=config_name)
            .first()
        )
        if existing is not None:
            existing.version = client.version
            existing.base_currency = client.base_currency
            existing.is_active = True
            return
        self.session.add(
            PPClientConfig(
                version=client.version,
                base_currency=client.base_currency,
                config_name=config_name,
                is_active=True,
            ),
        )

    def _persist_securities(
        self,
        client: ParsedClient,
    ) -> tuple[int, int, dict[int, int]]:
        """Persist securities and prices.

        Returns ``(securities, prices, position_to_id)`` where
        ``position_to_id`` maps the 1-based security position to its database id,
        used to resolve transactions' positional security references.

        Prices are only inserted for newly created securities. When a security
        already exists (matched by ISIN), its price history is assumed already
        imported, which keeps re-imports idempotent against the
        (security_id, price_date) unique constraint.
        """
        security_count = 0
        price_count = 0
        position_to_id: dict[int, int] = {}
        for position, parsed in enumerate(client.securities, start=1):
            security, created = self._get_or_create_security(parsed)
            self.session.flush()  # assign security.id for the price FK
            position_to_id[position] = security.id
            security_count += 1
            if not created:
                continue
            for parsed_price in parsed.prices:
                self.session.add(
                    PPSecurityPrice(
                        security_id=security.id,
                        price_date=parsed_price.price_date,
                        price_value=parsed_price.value,
                        price_source=parsed.feed,
                    ),
                )
                price_count += 1
        return security_count, price_count, position_to_id

    def _get_or_create_security(
        self,
        parsed: ParsedSecurity,
    ) -> tuple[SecurityMaster, bool]:
        """Match an existing security by ISIN, else create one.

        Returns the security and a flag that is True when it was newly created.
        """
        if parsed.isin:
            existing = (
                self.session.query(SecurityMaster).filter_by(isin=parsed.isin).first()
            )
            if existing is not None:
                return existing, False

        security = SecurityMaster(
            name=parsed.name,
            isin=parsed.isin,
            symbol=parsed.symbol,
            wkn=parsed.wkn,
            note=parsed.note,
            currency=parsed.currency,
        )
        self.session.add(security)
        return security, True

    def _persist_accounts(self, client: ParsedClient) -> dict[str, int]:
        """Persist accounts (idempotent by uuid). Returns uuid -> account id."""
        uuid_to_id: dict[str, int] = {}
        for parsed in client.accounts:
            if not parsed.uuid:
                continue
            account_uuid = uuid_module.UUID(parsed.uuid)
            existing = (
                self.session.query(PPAccount).filter_by(uuid=account_uuid).first()
            )
            if existing is not None:
                uuid_to_id[parsed.uuid] = existing.id
                continue
            account = PPAccount(
                uuid=account_uuid,
                name=parsed.name,
                currency_code=parsed.currency_code,
                is_retired=parsed.is_retired,
            )
            self.session.add(account)
            self.session.flush()  # assign account.id for the map and portfolio FK
            uuid_to_id[parsed.uuid] = account.id
        return uuid_to_id

    def _persist_portfolios(
        self,
        client: ParsedClient,
        account_uuid_to_id: dict[str, int],
    ) -> int:
        """Persist portfolios (idempotent by uuid), resolving reference accounts."""
        count = 0
        for parsed in client.portfolios:
            if not parsed.uuid:
                continue
            portfolio_uuid = uuid_module.UUID(parsed.uuid)
            existing = (
                self.session.query(PPPortfolio).filter_by(uuid=portfolio_uuid).first()
            )
            if existing is not None:
                continue
            reference_account_id = None
            if parsed.reference_account_uuid:
                reference_account_id = account_uuid_to_id.get(
                    parsed.reference_account_uuid,
                )
            self.session.add(
                PPPortfolio(
                    uuid=portfolio_uuid,
                    name=parsed.name,
                    is_retired=parsed.is_retired,
                    reference_account_id=reference_account_id,
                ),
            )
            count += 1
        return count

    def _persist_bookmarks(self, client: ParsedClient) -> int:
        """Persist dashboard bookmarks (idempotent by label + pattern)."""
        count = 0
        for parsed in client.bookmarks:
            existing = (
                self.session.query(PPBookmark)
                .filter_by(label=parsed.label, pattern=parsed.pattern)
                .first()
            )
            if existing is not None:
                continue
            self.session.add(
                PPBookmark(
                    label=parsed.label,
                    pattern=parsed.pattern,
                    sort_order=parsed.sort_order,
                ),
            )
            count += 1
        return count

    def _persist_account_transactions(
        self,
        client: ParsedClient,
        account_uuid_to_id: dict[str, int],
        position_to_id: dict[int, int],
    ) -> tuple[int, int]:
        """Persist account-transactions and their units (idempotent by uuid).

        Returns ``(transactions, units)``. Cross-entry linkage to portfolio
        transactions is not reconstructed yet; only ``cross_entry_type`` is
        recorded. Returns counts of newly inserted rows.
        """
        transaction_count = 0
        unit_count = 0
        for parsed_account in client.accounts:
            account_id = account_uuid_to_id.get(parsed_account.uuid)
            if account_id is None:
                continue
            for parsed_txn in parsed_account.transactions:
                created, units_added = self._persist_one_account_transaction(
                    parsed_txn,
                    account_id,
                    position_to_id,
                )
                transaction_count += created
                unit_count += units_added
        return transaction_count, unit_count

    def _persist_one_account_transaction(
        self,
        parsed_txn: ParsedTransaction,
        account_id: int,
        position_to_id: dict[int, int],
    ) -> tuple[int, int]:
        """Persist one account-transaction with its units. Returns (txn, units)."""
        txn_uuid = uuid_module.UUID(parsed_txn.uuid)
        existing = (
            self.session.query(PPAccountTransaction).filter_by(uuid=txn_uuid).first()
        )
        if existing is not None:
            return 0, 0

        security_id = None
        if parsed_txn.security_position is not None:
            security_id = position_to_id.get(parsed_txn.security_position)

        transaction = PPAccountTransaction(
            account_id=account_id,
            uuid=txn_uuid,
            transaction_date=parsed_txn.transaction_date,
            currency_code=parsed_txn.currency_code,
            amount=parsed_txn.amount,
            security_id=security_id,
            shares=parsed_txn.shares,
            transaction_type=parsed_txn.transaction_type,
            cross_entry_type=parsed_txn.cross_entry_type,
        )
        self.session.add(transaction)
        self.session.flush()  # assign transaction.id for the unit FK

        for parsed_unit in parsed_txn.units:
            self.session.add(
                PPTransactionUnit(
                    transaction_id=transaction.id,
                    transaction_type="ACCOUNT",
                    unit_type=parsed_unit.unit_type,
                    amount=parsed_unit.amount,
                    currency_code=parsed_unit.currency,
                ),
            )
        return 1, len(parsed_txn.units)
