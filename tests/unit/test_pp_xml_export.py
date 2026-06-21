"""Unit tests for :mod:`security_master.patch.pp_xml_export`.

Covers the pure PP amount/share conversion helpers and the
:class:`PPXMLExportService`. The service is exercised against an in-memory
SQLite database (via the conftest UUID shim) populated with a rich entity graph
so every serialization branch (securities, prices, accounts, account
transactions with units and cross-entries, portfolios with reference accounts,
portfolio transactions with linked account transactions, properties, and
bookmarks) executes without a live PostgreSQL server.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from security_master.patch.pp_xml_export import (
    PPXMLExportService,
    decimal_to_pp_amount,
    decimal_to_pp_shares,
    pp_amount_to_decimal,
    pp_shares_to_decimal,
)
from security_master.storage.models import SecurityMaster
from security_master.storage.pp_models import (
    PPAccount,
    PPAccountTransaction,
    PPBookmark,
    PPClientConfig,
    PPPortfolio,
    PPPortfolioTransaction,
    PPSecurityPrice,
    PPSetting,
    PPTransactionUnit,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = [
    pytest.mark.patch,
    # SQLite has no native Decimal; SQLAlchemy converts via float and warns.
    # Expected in-process-test fallback, irrelevant to the PostgreSQL path.
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]


# ---------------------------------------------------------------------------
# Pure conversion helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pp_amount", "expected"),
    [(94850, 948.5), (0, 0.0), (-100, -1.0)],
)
def test_pp_amount_to_decimal(pp_amount: int, expected: float) -> None:
    """PP integer cents convert to a float amount."""
    assert pp_amount_to_decimal(pp_amount) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("amount", "expected"), [(948.5, 94850), (0.0, 0), (-1.0, -100)]
)
def test_decimal_to_pp_amount(amount: float, expected: int) -> None:
    """Float amounts convert to PP integer cents."""
    assert decimal_to_pp_amount(amount) == expected


def test_pp_shares_round_trip() -> None:
    """Share conversion round-trips through the PP integer representation."""
    assert pp_shares_to_decimal(1_000_000_000) == pytest.approx(10.0)
    assert decimal_to_pp_shares(10.0) == 1_000_000_000


# ---------------------------------------------------------------------------
# PPXMLExportService backed by in-memory SQLite
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_session(sqlite_session: Session) -> Session:
    """Populate a SQLite session with a complete PP entity graph.

    Builds the full relationship graph the exporter walks: a configured client,
    two securities (one rich, one bare), a price, an active and a retired
    account, an account transaction with a fee unit and a cross-entry, a
    portfolio with a reference account, a portfolio transaction linked back to
    the account transaction with a tax unit, a properties setting, and a
    bookmark.

    Args:
        sqlite_session: The base in-memory session fixture.

    Returns:
        The same session, populated and committed.
    """
    session = sqlite_session
    session.add(
        PPClientConfig(
            version=69,
            base_currency="USD",
            config_name="default",
            is_active=True,
        ),
    )

    rich = SecurityMaster(
        name="APPLE INC",
        currency="USD",
        isin="US0378331005",
        symbol="AAPL",
        wkn="865985",
        note="primary holding",
    )
    bare = SecurityMaster(name="BARE CORP", currency="USD")
    session.add_all([rich, bare])
    session.flush()

    session.add(
        PPSecurityPrice(
            security_id=rich.id,
            price_date=date(2024, 1, 2),
            price_value=2_624_000_000,
        ),
    )

    active = PPAccount(
        uuid=uuid4(),
        name="IRA",
        currency_code="USD",
        is_retired=False,
        attributes='{"note": "x"}',
    )
    # A second active account with no attributes and no transactions exercises
    # the attribute-absent and transaction-absent branches.
    plain = PPAccount(
        uuid=uuid4(),
        name="BROKERAGE",
        currency_code="USD",
        is_retired=False,
    )
    retired = PPAccount(
        uuid=uuid4(),
        name="OLD",
        currency_code="USD",
        is_retired=True,
    )
    session.add_all([active, plain, retired])
    session.flush()

    atxn = PPAccountTransaction(
        uuid=uuid4(),
        account_id=active.id,
        transaction_date=date(2024, 1, 3),
        currency_code="USD",
        amount=Decimal("948.50"),
        security_id=rich.id,
        shares=Decimal(0),
        transaction_type="BUY",
        cross_entry_type="buysell",
    )
    # A cash-only transaction with no security and no cross-entry exercises the
    # security-absent and cross-entry-absent branches.
    cash_txn = PPAccountTransaction(
        uuid=uuid4(),
        account_id=active.id,
        transaction_date=date(2024, 1, 5),
        currency_code="USD",
        amount=Decimal("100.00"),
        shares=Decimal(0),
        transaction_type="DEPOSIT",
    )
    session.add_all([atxn, cash_txn])
    session.flush()
    session.add(
        PPTransactionUnit(
            transaction_id=atxn.id,
            transaction_type="ACCOUNT",
            unit_type="FEE",
            amount=Decimal("1.00"),
            currency_code="USD",
        ),
    )

    portfolio = PPPortfolio(
        uuid=uuid4(),
        name="IRA",
        is_retired=False,
        reference_account_id=active.id,
    )
    # A portfolio with no reference account and an unlinked transaction, plus an
    # empty portfolio, exercise the reference-absent, link-absent, and
    # transaction-absent branches.
    no_ref = PPPortfolio(uuid=uuid4(), name="TAXABLE", is_retired=False)
    empty = PPPortfolio(uuid=uuid4(), name="EMPTY", is_retired=False)
    session.add_all([portfolio, no_ref, empty])
    session.flush()

    ptxn = PPPortfolioTransaction(
        uuid=uuid4(),
        portfolio_id=portfolio.id,
        transaction_date=date(2024, 1, 4),
        currency_code="USD",
        amount=Decimal("948.50"),
        security_id=rich.id,
        shares=Decimal(10),
        transaction_type="BUY",
        linked_account_transaction_id=atxn.id,
    )
    unlinked = PPPortfolioTransaction(
        uuid=uuid4(),
        portfolio_id=no_ref.id,
        transaction_date=date(2024, 1, 6),
        currency_code="USD",
        amount=Decimal("200.00"),
        security_id=rich.id,
        shares=Decimal(2),
        transaction_type="SELL",
    )
    session.add_all([ptxn, unlinked])
    session.flush()
    session.add(
        PPTransactionUnit(
            transaction_id=ptxn.id,
            transaction_type="PORTFOLIO",
            unit_type="TAX",
            amount=Decimal("2.00"),
            currency_code="USD",
        ),
    )

    session.add(
        PPSetting(
            setting_category="properties", setting_key="foo", setting_value="bar"
        ),
    )
    session.add(PPBookmark(label="All securities", pattern="*", sort_order=0))
    session.commit()
    return session


def test_generate_complete_backup_serializes_entity_graph(
    populated_session: Session,
) -> None:
    """The exporter produces a well-formed client document for the full graph."""
    exporter = PPXMLExportService(populated_session)
    xml_content = exporter.generate_complete_backup()

    assert xml_content.lstrip().startswith("<?xml")
    assert "<client>" in xml_content

    stats = exporter.validate_export(xml_content)
    # Two active accounts are exported; the retired one is filtered out.
    assert stats["accounts"] == 2
    assert stats["portfolios"] == 3
    assert stats["account_transactions"] == 2
    assert stats["portfolio_transactions"] == 2
    assert stats["prices"] == 1
    assert stats["bookmarks"] == 1
    assert stats["securities"] >= 2  # two master securities (plus reference nodes)


def test_generate_complete_backup_without_config_raises(
    sqlite_session: Session,
) -> None:
    """Exporting with no active configuration raises a clear ValueError."""
    exporter = PPXMLExportService(sqlite_session)
    with pytest.raises(ValueError, match="No active PP configuration"):
        exporter.generate_complete_backup()


def test_export_to_file_writes_document(
    populated_session: Session,
    tmp_path: object,
) -> None:
    """export_to_file writes the generated backup to disk."""
    from pathlib import Path

    out = Path(str(tmp_path)) / "backup.xml"
    exporter = PPXMLExportService(populated_session)
    exporter.export_to_file(str(out))

    content = out.read_text(encoding="utf-8")
    assert "<client>" in content
    assert "securities" in content


def test_validate_export_rejects_invalid_xml(sqlite_session: Session) -> None:
    """validate_export raises ValueError on malformed XML input."""
    exporter = PPXMLExportService(sqlite_session)
    with pytest.raises(ValueError, match="Invalid XML"):
        exporter.validate_export("<client><unclosed>")


def test_prettify_xml_wraps_defused_errors(
    sqlite_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DefusedXmlException during prettification is re-raised as ValueError."""
    import defusedxml

    from security_master.patch import pp_xml_export

    def _boom(_content: str) -> object:
        msg = "blocked"
        raise defusedxml.DefusedXmlException(msg)

    monkeypatch.setattr(pp_xml_export.defused_minidom, "parseString", _boom)
    exporter = PPXMLExportService(sqlite_session)
    element = pp_xml_export.ET.Element("client")
    with pytest.raises(ValueError, match="prettification failed"):
        exporter._prettify_xml(element)  # noqa: SLF001  (targeted branch coverage)
