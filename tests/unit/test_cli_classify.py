"""Unit tests for the ``classify`` CLI sub-group (Tier-4 manual assignment).

The ``classify`` commands open their own engine and call ``engine.dispose()`` in
a ``finally`` block. An in-memory SQLite database is destroyed when its engine is
disposed, so these tests point the CLI at a file-based SQLite database under
``tmp_path``: ``close()``/``dispose()`` then leave the file intact and post-invoke
assertions can reopen it. ``create_db_engine`` is monkeypatched to build a fresh
engine on that same file each call; ``get_session_factory`` is the real one.

The conftest module-level ``@compiles`` shim renders Postgres ``UUID`` columns as
``CHAR(32)`` on SQLite, so the full schema (including ``pp_*`` tables) creates
cleanly here without a live PostgreSQL server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine

from security_master import cli
from security_master.storage.models import Base, SecurityMaster

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine

pytestmark = [pytest.mark.unit, pytest.mark.classifier]

_TEST_ISIN = "US0378331005"


def _seed_engine(
    tmp_path: Path,
    *,
    isin: str | None = _TEST_ISIN,
    symbol: str = "AAPL",
) -> tuple[Engine, str]:
    """Create a file-based SQLite database with one unclassified security.

    Args:
        tmp_path: Pytest temporary directory for the database file.
        isin: ISIN to assign to the seeded security; ``None`` for a symbol-only
            row (used by the crypto-seed path, which matches on symbol).
        symbol: Symbol to assign to the seeded security.

    Returns:
        A tuple of (engine, sqlite-url) for the seeded database.
    """
    # Register the pp_* / transaction tables on Base.metadata before create_all,
    # mirroring the conftest sqlite_session fixture.
    from security_master.storage import (  # noqa: F401
        entity,
        pp_models,
        transaction_models,
    )

    url = f"sqlite:///{tmp_path / 'd3.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=engine)()
    session.add(SecurityMaster(name="Seed Security", isin=isin, symbol=symbol))
    session.commit()
    session.close()
    return engine, url


def _reopen(url: str, *, symbol: str | None = None) -> SecurityMaster:
    """Reopen the database and return the single seeded security.

    Args:
        url: SQLite URL of the file-based test database.
        symbol: When given, match on symbol instead of the default ISIN; needed
            for the crypto-seed row, which is seeded without an ISIN.

    Returns:
        The persisted SecurityMaster row.
    """
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(url)
    session = sessionmaker(bind=engine)()
    try:
        query = session.query(SecurityMaster)
        if symbol is not None:
            return query.filter_by(symbol=symbol).one()
        return query.filter_by(isin=_TEST_ISIN).one()
    finally:
        session.close()
        engine.dispose()


def test_classify_gics_sector_assigns_and_locks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid GICS-L1 sector is written and the row is locked."""
    _, url = _seed_engine(tmp_path)
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: create_engine(url))

    result = CliRunner().invoke(
        cli.app,
        [
            "classify",
            "gics-sector",
            "Information Technology",
            "--isin",
            _TEST_ISIN,
            "--classified-by",
            "byron",
        ],
    )

    assert result.exit_code == 0, result.output
    sec = _reopen(url)
    assert sec.industries_gics_sectors_level1 == "Information Technology"
    assert sec.classification_locked is True


def test_classify_rejects_both_selectors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Supplying both --isin and --id fails loudly instead of silently using ISIN."""
    _, url = _seed_engine(tmp_path)
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: create_engine(url))

    result = CliRunner().invoke(
        cli.app,
        [
            "classify",
            "gics-sector",
            "Information Technology",
            "--isin",
            _TEST_ISIN,
            "--id",
            "1",
            "--classified-by",
            "byron",
        ],
    )

    assert result.exit_code != 0
    assert "exactly one of --isin or --id" in result.output
    sec = _reopen(url)
    assert sec.classification_locked is False


def test_classify_sleeve_rejects_unknown_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown BRX-Plus key is rejected before any write, like the GICS path."""
    _, url = _seed_engine(tmp_path)
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: create_engine(url))

    result = CliRunner().invoke(
        cli.app,
        [
            "classify",
            "sleeve",
            "AC.NOT.A.REAL.KEY",
            "--isin",
            _TEST_ISIN,
            "--classified-by",
            "byron",
        ],
    )

    assert result.exit_code != 0
    sec = _reopen(url)
    assert sec.brx_plus is None
    assert sec.classification_locked is False


def test_classify_gics_sector_rejects_unknown_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown sector is rejected before any write."""
    _, url = _seed_engine(tmp_path)
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: create_engine(url))

    result = CliRunner().invoke(
        cli.app,
        [
            "classify",
            "gics-sector",
            "Widgets",
            "--isin",
            _TEST_ISIN,
            "--classified-by",
            "byron",
        ],
    )

    assert result.exit_code != 0
    assert "unknown GICS-L1 sector" in result.output
    sec = _reopen(url)
    assert sec.industries_gics_sectors_level1 is None
    assert sec.classification_locked is False


def test_classify_locked_row_requires_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A locked row is refused without --force and overridden with it."""
    _, url = _seed_engine(tmp_path)
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: create_engine(url))
    runner = CliRunner()

    first = runner.invoke(
        cli.app,
        [
            "classify",
            "gics-sector",
            "Energy",
            "--isin",
            _TEST_ISIN,
            "--classified-by",
            "byron",
        ],
    )
    assert first.exit_code == 0, first.output
    assert _reopen(url).industries_gics_sectors_level1 == "Energy"

    blocked = runner.invoke(
        cli.app,
        [
            "classify",
            "gics-sector",
            "Financials",
            "--isin",
            _TEST_ISIN,
            "--classified-by",
            "byron",
        ],
    )
    assert blocked.exit_code != 0
    assert "locked" in blocked.output
    assert _reopen(url).industries_gics_sectors_level1 == "Energy"

    forced = runner.invoke(
        cli.app,
        [
            "classify",
            "gics-sector",
            "Financials",
            "--isin",
            _TEST_ISIN,
            "--classified-by",
            "byron",
            "--force",
        ],
    )
    assert forced.exit_code == 0, forced.output
    assert _reopen(url).industries_gics_sectors_level1 == "Financials"


def test_classify_sleeve_assigns_brx_plus_levels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A BRX-Plus leaf key writes both level columns and the full key."""
    _, url = _seed_engine(tmp_path)
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: create_engine(url))

    result = CliRunner().invoke(
        cli.app,
        [
            "classify",
            "sleeve",
            "AC.ALTS.CRYPTO.ETH",
            "--isin",
            _TEST_ISIN,
            "--classified-by",
            "byron",
        ],
    )

    assert result.exit_code == 0, result.output
    sec = _reopen(url)
    assert sec.brx_plus == "AC.ALTS.CRYPTO.ETH"
    assert sec.brx_plus_level1 == "Alternatives"
    assert sec.brx_plus_level2 == "Crypto (ETH)"


def test_classify_cash_assigns_cash_sleeve_and_locks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cash subcommand writes the cash level1 sleeve and locks the row."""
    _, url = _seed_engine(tmp_path)
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: create_engine(url))

    result = CliRunner().invoke(
        cli.app,
        ["classify", "cash", "--isin", _TEST_ISIN, "--classified-by", "byron"],
    )

    assert result.exit_code == 0, result.output
    sec = _reopen(url)
    assert sec.brx_plus_level1 == "Cash & Cash Equivalents"
    assert sec.classification_locked is True


def test_classify_crypto_seed_bulk_applies_to_matched_symbols(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """crypto-seed assigns the committed sleeve to a symbol-matched row.

    Exercises the distinct crypto-seed session path (its own engine, commit, and
    dispose) end to end via the CLI, not just the underlying apply_crypto_seed.
    """
    _, url = _seed_engine(tmp_path, isin=None, symbol="BTC")
    monkeypatch.setattr(cli, "create_db_engine", lambda *_a, **_k: create_engine(url))

    result = CliRunner().invoke(
        cli.app,
        ["classify", "crypto-seed", "--classified-by", "byron"],
    )

    assert result.exit_code == 0, result.output
    assert "Applied crypto seed to 1 securities." in result.output
    sec = _reopen(url, symbol="BTC")
    assert sec.brx_plus == "AC.ALTS.CRYPTO.BTC"
    assert sec.classification_locked is True
