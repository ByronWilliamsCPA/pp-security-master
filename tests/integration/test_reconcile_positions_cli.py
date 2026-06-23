"""End-to-end CLI test: import trades, then reconcile a positions snapshot."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from security_master.cli import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.extractor]

_TRADES = """<?xml version="1.0"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
  <Trades>
    <Trade tradeDate="01/02/2023" buySell="BUY" proceeds="-41560.00" currency="USD"
        description="DBJA FUND" symbol="DBJA" isin="US000000DBJA" tradeID="DBJA1"
        quantity="4156" tradePrice="10" accountId="U1"/>
    <Trade tradeDate="01/03/2023" buySell="BUY" proceeds="-23540.69" currency="USD"
        description="BMBCX FUND" symbol="BMBCX" isin="US000000BMBC" tradeID="BMBC1"
        quantity="2354.069" tradePrice="10" accountId="U1"/>
  </Trades>
  <CorporateActions>
    <CorporateAction reportDate="20240110" transactionID="DBJACA1" type="TC"
        description="DBJA MERGER" actionDescription="DBJA MERGED FOR CASH"
        symbol="DBJA" isin="US000000DBJA" quantity="-4156" amount="0"
        currency="USD" accountId="U1"/>
  </CorporateActions>
</FlexStatement></FlexStatements></FlexQueryResponse>
"""

_POSITIONS = """<?xml version="1.0"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
  <OpenPositions>
    <OpenPosition accountId="U1" conid="111" symbol="BMBCX" isin="US000000BMBC"
        description="BMBCX FUND" position="2520.119" currency="USD"
        side="Long" reportDate="20260619"/>
  </OpenPositions>
</FlexStatement></FlexStatements></FlexQueryResponse>
"""


def test_reconcile_positions_reports_dbja_matched_and_bmbcx_drift(
    tmp_path: Path,
) -> None:
    db = tmp_path / "sp2.db"
    url = f"sqlite:///{db}"
    trades = tmp_path / "trades.xml"
    trades.write_text(_TRADES, encoding="utf-8")
    positions = tmp_path / "positions.xml"
    positions.write_text(_POSITIONS, encoding="utf-8")

    runner = CliRunner()
    seed = runner.invoke(
        app, ["import-broker", str(trades), "--database-url", url, "--create-schema"]
    )
    assert seed.exit_code == 0, seed.output

    result = runner.invoke(
        app, ["reconcile-positions", str(positions), "--database-url", url]
    )
    assert result.exit_code == 0, result.output

    lines = result.output.splitlines()
    dbja_line = next(line for line in lines if "US000000DBJA" in line)
    assert "MATCHED" in dbja_line
    bmbc_line = next(line for line in lines if "US000000BMBC" in line)
    assert "DRIFT" in bmbc_line


def test_reconcile_positions_still_reports_on_reimport(tmp_path: Path) -> None:
    """A second reconcile of an already-imported snapshot still prints the report.

    Scopes are derived from the file's content, not the (idempotency-emptied)
    import batch, so the diagnostic is not silent on re-run.
    """
    db = tmp_path / "sp2.db"
    url = f"sqlite:///{db}"
    trades = tmp_path / "trades.xml"
    trades.write_text(_TRADES, encoding="utf-8")
    positions = tmp_path / "positions.xml"
    positions.write_text(_POSITIONS, encoding="utf-8")

    runner = CliRunner()
    seed = runner.invoke(
        app, ["import-broker", str(trades), "--database-url", url, "--create-schema"]
    )
    assert seed.exit_code == 0, seed.output

    first = runner.invoke(
        app, ["reconcile-positions", str(positions), "--database-url", url]
    )
    assert first.exit_code == 0, first.output

    second = runner.invoke(
        app, ["reconcile-positions", str(positions), "--database-url", url]
    )
    assert second.exit_code == 0, second.output
    assert "skipped 1 existing" in second.output
    lines = second.output.splitlines()
    bmbc_line = next(line for line in lines if "US000000BMBC" in line)
    assert "DRIFT" in bmbc_line
