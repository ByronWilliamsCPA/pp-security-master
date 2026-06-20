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

Scope (walking skeleton, 2026-06-19): client configuration, securities with
full price history, accounts, portfolios, and bookmarks. The transaction graph
(``account-transaction`` / ``portfolio-transaction`` with ``crossEntry``
linkage and positional ``security[N]`` references) is intentionally NOT imported
yet. See ``docs/project/ROADMAP_2026-06-19.md`` Phase C for the follow-up.
"""

from __future__ import annotations

import uuid as uuid_module
from dataclasses import dataclass, field
from datetime import date
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
    PPBookmark,
    PPClientConfig,
    PPPortfolio,
    PPSecurityPrice,
)

_DEFAULT_FEED = "PP"


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


@dataclass
class ParsedAccount:
    """A top-level deposit account."""

    uuid: str
    name: str
    currency_code: str = "USD"
    is_retired: bool = False


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


def parse_client(xml_content: str) -> ParsedClient:
    """Parse a PP ``client.xml`` string into a :class:`ParsedClient`.

    Pure function: no database access and no side effects. Only the supported
    subset is parsed (config, securities, accounts, portfolios, bookmarks);
    transactions and watchlists are ignored.

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
        ParsedAccount(
            uuid=_text(a, "uuid") or "",
            name=_text(a, "name") or "",
            currency_code=_text(a, "currencyCode") or "USD",
            is_retired=_parse_bool(_text(a, "isRetired")),
        )
        for a in root.findall("accounts/account")
        if _text(a, "uuid")
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
        summary.securities, summary.prices = self._persist_securities(client)
        account_uuid_to_id = self._persist_accounts(client)
        summary.accounts = len(account_uuid_to_id)
        summary.portfolios = self._persist_portfolios(client, account_uuid_to_id)
        summary.bookmarks = self._persist_bookmarks(client)

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

    def _persist_securities(self, client: ParsedClient) -> tuple[int, int]:
        """Persist securities and their prices. Returns (securities, prices).

        Prices are only inserted for newly created securities. When a security
        already exists (matched by ISIN), its price history is assumed already
        imported, which keeps re-imports idempotent against the
        (security_id, price_date) unique constraint.
        """
        security_count = 0
        price_count = 0
        for parsed in client.securities:
            security, created = self._get_or_create_security(parsed)
            self.session.flush()  # assign security.id for the price FK
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
        return security_count, price_count

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
