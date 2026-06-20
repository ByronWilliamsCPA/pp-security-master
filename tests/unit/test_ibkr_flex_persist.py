"""Unit tests for the persistence layer of ``extractor.ibkr_flex``.

The pure parser is covered by ``test_ibkr_flex_parse.py``; these tests drive
:class:`IBKRFlexImportService` against an in-memory SQLite database (via the
conftest UUID shim) and cover the missing-tradeDate parse guard. A compact
inline document exercises in-run de-duplication, null-trade-id handling, and
cross-run idempotency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from security_master.extractor.ibkr_flex import (
    IBKRFlexImportService,
    parse_ibkr_flex,
)
from security_master.storage.transaction_models import InteractiveBrokersTransaction

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

pytestmark = [
    pytest.mark.extractor,
    pytest.mark.filterwarnings(
        "ignore:Dialect sqlite.+does .not. support Decimal objects natively"
        ":sqlalchemy.exc.SAWarning",
    ),
]

# Three trades: T1, a duplicate of T1 (in-run skip), and a trade with no
# tradeID (never deduped). Numeric attributes exercise the Decimal conversions.
_DOC = """<?xml version="1.0"?>
<FlexQueryResponse>
  <FlexStatements>
    <FlexStatement>
      <Trades>
        <Trade tradeDate="01/02/2024" buySell="BUY" proceeds="-1000.00"
               currency="USD" description="APPLE INC" symbol="AAPL"
               tradeID="T1" quantity="10" tradePrice="100" ibCommission="-1.00"/>
        <Trade tradeDate="01/02/2024" buySell="BUY" proceeds="-1000.00"
               currency="USD" description="APPLE INC" symbol="AAPL"
               tradeID="T1" quantity="10" tradePrice="100"/>
        <Trade tradeDate="01/03/2024" buySell="SELL" proceeds="500.00"
               currency="USD" description="MSFT" symbol="MSFT"/>
      </Trades>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
"""


def test_import_from_string_inserts_and_dedupes_within_run(
    sqlite_session: Session,
) -> None:
    """A first import inserts distinct trades and skips the in-run duplicate."""
    summary = IBKRFlexImportService(sqlite_session).import_from_string(_DOC)

    # T1 inserted once, its duplicate skipped, the null-id trade inserted.
    assert summary.trades == 2
    assert summary.skipped == 1
    assert summary.import_batch_id.startswith("ibkr-")
    assert sqlite_session.query(InteractiveBrokersTransaction).count() == 2


def test_reimport_skips_existing_trade_ids(sqlite_session: Session) -> None:
    """Re-importing skips trades whose trade_id already exists in the database."""
    service = IBKRFlexImportService(sqlite_session)
    service.import_from_string(_DOC)
    second = service.import_from_string(_DOC)

    # T1 (and its dup) are now in the DB and skipped; the null-id trade re-inserts.
    assert second.skipped == 2
    assert second.trades == 1


def test_import_empty_document_inserts_nothing(sqlite_session: Session) -> None:
    """A document with no trades yields an empty summary and no rows."""
    summary = IBKRFlexImportService(sqlite_session).import_from_string(
        "<FlexQueryResponse/>",
    )
    assert summary.trades == 0
    assert summary.skipped == 0
    assert sqlite_session.query(InteractiveBrokersTransaction).count() == 0


def test_import_from_file_records_source(
    sqlite_session: Session,
    tmp_path: Path,
) -> None:
    """import_from_file reads the path and records it as the row source."""
    path = tmp_path / "flex.xml"
    path.write_text(_DOC, encoding="utf-8")
    summary = IBKRFlexImportService(sqlite_session).import_from_file(str(path))

    assert summary.trades == 2
    assert summary.source_file == str(path)
    row = sqlite_session.query(InteractiveBrokersTransaction).first()
    assert row is not None
    assert row.source_file == str(path)


def test_parse_rejects_trade_without_trade_date() -> None:
    """A Trade element missing tradeDate raises a clear ValueError."""
    doc = "<FlexQueryResponse><Trade buySell='BUY' proceeds='1' currency='USD'/></FlexQueryResponse>"
    with pytest.raises(ValueError, match="tradeDate"):
        parse_ibkr_flex(doc)
