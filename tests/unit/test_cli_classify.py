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


def _seed_engine(tmp_path: Path) -> tuple[Engine, str]:
    """Create a file-based SQLite database with one unclassified security.

    Args:
        tmp_path: Pytest temporary directory for the database file.

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
    session.add(SecurityMaster(name="Apple Inc.", isin=_TEST_ISIN, symbol="AAPL"))
    session.commit()
    session.close()
    return engine, url


def _reopen(url: str) -> SecurityMaster:
    """Reopen the database and return the single seeded security.

    Args:
        url: SQLite URL of the file-based test database.

    Returns:
        The persisted SecurityMaster row.
    """
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(url)
    session = sessionmaker(bind=engine)()
    try:
        return session.query(SecurityMaster).filter_by(isin=_TEST_ISIN).one()
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
