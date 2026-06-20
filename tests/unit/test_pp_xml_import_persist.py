"""Unit tests for the persistence layer of ``pp_xml_import``.

The pure parser is covered by ``test_pp_xml_import_parse.py``. These tests drive
:class:`PPXMLImportService` against an in-memory SQLite database (via the
conftest UUID shim) using a small hand-built document that exercises the create,
idempotent-reuse, reference-resolution, and unresolved-reference branches, plus
the parser's None-returning edge cases.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from security_master.patch.pp_xml_import import (
    PPXMLImportService,
    _parse_account_transaction,
    _parse_portfolio,
    _parse_security_position,
    _parse_unit,
    parse_client,
)
from security_master.storage.models import SecurityMaster
from security_master.storage.pp_models import (
    PPAccount,
    PPAccountTransaction,
    PPBookmark,
    PPPortfolio,
    PPSecurityPrice,
    PPTransactionUnit,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

import defusedxml.ElementTree as ET  # noqa: N817  (safe parser, matches module)

pytestmark = [
    pytest.mark.patch,
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]

# A compact backup exercising: an ISIN security with prices, an ISIN-less
# security, an account with a resolvable security reference plus a unit and a
# cross-entry, a second transaction with an out-of-range security position, a
# portfolio with a reference account, and a bookmark.
_DOC = """<?xml version="1.0" encoding="UTF-8"?>
<client>
  <version>69</version>
  <baseCurrency>USD</baseCurrency>
  <securities>
    <security>
      <name>APPLE INC</name>
      <currencyCode>USD</currencyCode>
      <isin>US0378331005</isin>
      <tickerSymbol>AAPL</tickerSymbol>
      <wkn>865985</wkn>
      <feed>PP</feed>
      <prices>
        <price t="2024-01-02" v="2624000000"/>
        <price t="2024-01-03" v="2630000000"/>
      </prices>
    </security>
    <security>
      <name>NO ISIN CORP</name>
      <currencyCode>USD</currencyCode>
    </security>
  </securities>
  <accounts>
    <account>
      <uuid>00000000-0000-0000-0000-000000000001</uuid>
      <name>IRA</name>
      <currencyCode>USD</currencyCode>
      <isRetired>false</isRetired>
      <transactions>
        <account-transaction>
          <uuid>10000000-0000-0000-0000-000000000001</uuid>
          <date>2024-01-03T00:00</date>
          <currencyCode>USD</currencyCode>
          <amount>94850</amount>
          <shares>0</shares>
          <type>BUY</type>
          <security reference="../../../../../securities/security[1]"/>
          <crossEntry class="buysell"/>
          <units>
            <unit type="FEE">
              <amount currency="USD" amount="100"/>
            </unit>
          </units>
        </account-transaction>
        <account-transaction>
          <uuid>10000000-0000-0000-0000-000000000002</uuid>
          <date>2024-01-04T00:00</date>
          <currencyCode>USD</currencyCode>
          <amount>5000</amount>
          <type>DEPOSIT</type>
          <security reference="../../../../../securities/security[99]"/>
        </account-transaction>
        <account-transaction reference="../foo"/>
      </transactions>
    </account>
  </accounts>
  <portfolios>
    <portfolio>
      <uuid>20000000-0000-0000-0000-000000000001</uuid>
      <name>IRA</name>
      <isRetired>false</isRetired>
      <referenceAccount>
        <uuid>00000000-0000-0000-0000-000000000001</uuid>
      </referenceAccount>
    </portfolio>
  </portfolios>
  <settings>
    <bookmarks>
      <bookmark>
        <label>All securities</label>
        <pattern>*</pattern>
      </bookmark>
    </bookmarks>
  </settings>
</client>
"""


def test_import_from_string_persists_entities(sqlite_session: Session) -> None:
    """A full import persists every supported entity and reports the counts."""
    summary = PPXMLImportService(sqlite_session).import_from_string(_DOC)
    sqlite_session.commit()

    assert summary.config_version == 69
    assert summary.securities == 2
    assert summary.prices == 2
    assert summary.accounts == 1
    assert summary.portfolios == 1
    assert summary.bookmarks == 1
    assert summary.account_transactions == 2  # the reference pointer is skipped
    assert summary.transaction_units == 1

    assert sqlite_session.query(SecurityMaster).count() == 2
    assert sqlite_session.query(PPSecurityPrice).count() == 2
    assert sqlite_session.query(PPAccount).count() == 1
    assert sqlite_session.query(PPPortfolio).count() == 1
    assert sqlite_session.query(PPBookmark).count() == 1
    assert sqlite_session.query(PPAccountTransaction).count() == 2
    assert sqlite_session.query(PPTransactionUnit).count() == 1


def test_security_reference_resolution(sqlite_session: Session) -> None:
    """A resolvable security[N] reference links the transaction to that security."""
    PPXMLImportService(sqlite_session).import_from_string(_DOC)
    sqlite_session.commit()

    apple = sqlite_session.query(SecurityMaster).filter_by(isin="US0378331005").one()
    linked = (
        sqlite_session.query(PPAccountTransaction)
        .filter_by(transaction_type="BUY")
        .one()
    )
    assert linked.security_id == apple.id


def test_unresolved_security_position_warns_and_nulls_link(
    sqlite_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An out-of-range security position logs a warning and leaves the link null."""
    with caplog.at_level(logging.WARNING):
        PPXMLImportService(sqlite_session).import_from_string(_DOC)
    sqlite_session.commit()

    assert "unresolved security" in caplog.text
    deposit = (
        sqlite_session.query(PPAccountTransaction)
        .filter_by(transaction_type="DEPOSIT")
        .one()
    )
    assert deposit.security_id is None


def test_import_is_idempotent_for_keyed_entities(sqlite_session: Session) -> None:
    """Re-import dedupes ISIN securities, accounts, txns, and bookmarks.

    The ISIN-less security is the documented #EDGE: with no key to match on it
    is re-created on every import, so the SecurityMaster total grows while the
    ISIN-keyed entity stays unique.
    """
    service = PPXMLImportService(sqlite_session)
    service.import_from_string(_DOC)
    sqlite_session.commit()
    second = service.import_from_string(_DOC)
    sqlite_session.commit()

    # Prices/transactions/bookmarks are keyed, so the second pass adds none.
    assert second.prices == 0  # prices only added for newly created securities
    assert second.account_transactions == 0
    assert second.bookmarks == 0

    # The ISIN security is deduped; the ISIN-less one is duplicated (#EDGE).
    assert (
        sqlite_session.query(SecurityMaster).filter_by(isin="US0378331005").count() == 1
    )
    assert sqlite_session.query(SecurityMaster).count() == 3
    assert sqlite_session.query(PPSecurityPrice).count() == 2
    assert sqlite_session.query(PPAccountTransaction).count() == 2
    assert sqlite_session.query(PPBookmark).count() == 1


def test_import_from_file_reads_path(
    sqlite_session: Session,
    tmp_path: Path,
) -> None:
    """import_from_file reads the document from disk and delegates to the parser."""
    path = tmp_path / "client.xml"
    path.write_text(_DOC, encoding="utf-8")
    summary = PPXMLImportService(sqlite_session).import_from_file(str(path))
    sqlite_session.commit()
    assert summary.securities == 2


def test_import_empty_client(
    sqlite_session: Session,
    pp_empty_client_sample_file: Path,
) -> None:
    """The empty sample imports a config with zero of every collection."""
    summary = PPXMLImportService(sqlite_session).import_from_string(
        pp_empty_client_sample_file.read_text(encoding="utf-8"),
    )
    sqlite_session.commit()
    assert summary.securities == 0
    assert summary.accounts == 1  # the empty sample has one account
    assert summary.account_transactions == 0


# ---------------------------------------------------------------------------
# Parser edge cases (None-returning branches)
# ---------------------------------------------------------------------------


def test_parse_security_position_variants() -> None:
    """Position parsing handles missing element, missing/bracketless references."""
    assert _parse_security_position(ET.fromstring("<t/>")) is None
    assert _parse_security_position(ET.fromstring("<t><security/></t>")) is None
    assert (
        _parse_security_position(
            ET.fromstring('<t><security reference="no-brackets"/></t>'),
        )
        is None
    )
    assert (
        _parse_security_position(
            ET.fromstring('<t><security reference="x/security[7]"/></t>'),
        )
        == 7
    )


def test_parse_unit_returns_none_when_malformed() -> None:
    """A unit without an amount element or amount attribute parses to None."""
    assert _parse_unit(ET.fromstring('<unit type="FEE"/>')) is None
    assert _parse_unit(ET.fromstring('<unit type="FEE"><amount/></unit>')) is None
    parsed = _parse_unit(
        ET.fromstring('<unit type="FEE"><amount currency="USD" amount="100"/></unit>'),
    )
    assert parsed is not None
    assert parsed.unit_type == "FEE"


def test_parse_account_transaction_skips_reference_and_incomplete() -> None:
    """Reference pointers and records missing uuid/date/amount parse to None."""
    assert (
        _parse_account_transaction(
            ET.fromstring('<account-transaction reference="x"/>')
        )
        is None
    )
    assert (
        _parse_account_transaction(
            ET.fromstring("<account-transaction><uuid>u</uuid></account-transaction>"),
        )
        is None
    )


def test_parse_portfolio_with_and_without_reference_account() -> None:
    """Portfolio parsing resolves a reference-account uuid when present, else None."""
    with_ref = _parse_portfolio(
        ET.fromstring(
            "<portfolio><uuid>p1</uuid><name>IRA</name><isRetired>false</isRetired>"
            "<referenceAccount><uuid>a1</uuid></referenceAccount></portfolio>",
        ),
    )
    assert with_ref.reference_account_uuid == "a1"

    without_ref = _parse_portfolio(
        ET.fromstring("<portfolio><uuid>p2</uuid><name>Taxable</name></portfolio>"),
    )
    assert without_ref.reference_account_uuid is None


def test_parse_client_requires_version() -> None:
    """A document without <version> is rejected with a clear error."""
    with pytest.raises(ValueError, match="version"):
        parse_client("<client><baseCurrency>USD</baseCurrency></client>")
