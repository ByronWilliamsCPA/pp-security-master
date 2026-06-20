"""Integration test: PP XML import -> database -> export round-trip.

Imports the committed sample PP backup into a real PostgreSQL database, asserts
the persisted entity counts, then exports via :class:`PPXMLExportService` and
asserts the exported document round-trips the supported entities (securities,
prices, accounts, portfolios).

Requires a PostgreSQL database via the ``DATABASE_URL`` environment variable;
the test skips when it is not set. Runs in CI's integration-tests job (which
provisions a postgres:17 service) and against any local ephemeral Postgres.

Scope note: the importer does not yet load the transaction graph, so this test
asserts round-trip fidelity only for the supported entity subset.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET  # noqa: N817
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from security_master.patch.pp_xml_export import PPXMLExportService
from security_master.patch.pp_xml_import import PPXMLImportService
from security_master.storage.models import Base, SecurityMaster
from security_master.storage.pp_models import (
    PPAccount,
    PPBookmark,
    PPPortfolio,
    PPSecurityPrice,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

pytestmark = [pytest.mark.integration, pytest.mark.database]

_SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "../sample_data"
    / ("BruceandSueWilliams_sample.xml")
)
# One <account> and one <portfolio> in the sample are uuid-less placeholders
# that the importer skips, so the persisted counts are 3 and 2.
_EXPECTED_SECURITIES = 18
_EXPECTED_PRICES = 53207
_EXPECTED_ACCOUNTS = 3
_EXPECTED_PORTFOLIOS = 2
_EXPECTED_BOOKMARKS = 18


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Yield a session bound to DATABASE_URL; rolls back after the test.

    The schema is created idempotently. The test runs entirely inside one
    uncommitted transaction so the exporter sees the imported rows while the
    database is left clean on teardown.
    """
    # PPSM_TEST_DATABASE_URL takes precedence and is never clobbered by the
    # autouse setup_test_environment fixture, so a local ephemeral Postgres can
    # be targeted without editing conftest. CI relies on DATABASE_URL.
    database_url = os.getenv("PPSM_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("no test database URL set; integration test requires PostgreSQL")

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()
        engine.dispose()


def test_import_then_export_roundtrip(session: Session) -> None:
    """Import the sample backup, then export and confirm entity round-trip."""
    importer = PPXMLImportService(session)
    summary = importer.import_from_string(_SAMPLE.read_text(encoding="utf-8"))

    # Imported summary matches the known sample.
    assert summary.config_version == 66
    assert summary.securities == _EXPECTED_SECURITIES
    assert summary.prices == _EXPECTED_PRICES
    assert summary.accounts == _EXPECTED_ACCOUNTS
    assert summary.portfolios == _EXPECTED_PORTFOLIOS
    assert summary.bookmarks == _EXPECTED_BOOKMARKS

    # Database reflects the import.
    assert session.query(SecurityMaster).count() == _EXPECTED_SECURITIES
    assert session.query(PPSecurityPrice).count() == _EXPECTED_PRICES
    assert session.query(PPAccount).count() == _EXPECTED_ACCOUNTS
    assert session.query(PPPortfolio).count() == _EXPECTED_PORTFOLIOS
    assert session.query(PPBookmark).count() == _EXPECTED_BOOKMARKS

    # Export from the same session and assert the supported entities round-trip:
    # the exported document must reproduce exactly what the import persisted.
    exporter = PPXMLExportService(session)
    xml_content = exporter.generate_complete_backup()
    root = ET.fromstring(xml_content)

    assert len(root.findall("securities/security")) == summary.securities
    assert len(root.findall("accounts/account")) == summary.accounts
    assert len(root.findall("portfolios/portfolio")) == summary.portfolios
    assert len(root.findall(".//price")) == summary.prices


def test_import_is_idempotent_for_securities(session: Session) -> None:
    """Re-importing matches securities by ISIN instead of duplicating them."""
    importer = PPXMLImportService(session)
    importer.import_from_string(_SAMPLE.read_text(encoding="utf-8"))
    importer.import_from_string(_SAMPLE.read_text(encoding="utf-8"))

    # Securities are de-duplicated by ISIN across the two imports.
    assert session.query(SecurityMaster).count() == _EXPECTED_SECURITIES
