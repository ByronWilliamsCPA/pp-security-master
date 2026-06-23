"""Unit tests for Tier-3 classify_equity (provenance, lock, resolver branches)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from security_master.classifier.equity import classify_equity
from security_master.classifier.types import ClassificationTier
from security_master.external.errors import ExternalAPIError
from security_master.external.openfigi import OpenFIGIRecord
from security_master.storage.models import SecurityMaster

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = [pytest.mark.unit, pytest.mark.classifier]


class _FigiStub:
    def __init__(self, record: OpenFIGIRecord | None, *, raises: bool = False) -> None:
        self._record = record
        self._raises = raises

    def map_identifier(
        self, *, isin: str | None = None, symbol: str | None = None
    ) -> OpenFIGIRecord | None:
        if self._raises:
            raise ExternalAPIError(provider="openfigi", message="down")
        return self._record


class _EdgarStub:
    def __init__(self, sic: str | None, *, raises: bool = False) -> None:
        self._sic = sic
        self._raises = raises

    def sic_for_symbol(self, symbol: str) -> str | None:
        if self._raises:
            raise ExternalAPIError(provider="sec_edgar", message="down")
        return self._sic


_EQUITY = OpenFIGIRecord(figi="BBG", name="APPLE INC", market_sector="Equity")


def _add(session: Session, **kwargs) -> SecurityMaster:
    sec = SecurityMaster(name="Apple", **kwargs)
    session.add(sec)
    session.flush()
    return sec


def test_provider_sector_path_writes_provenance(sqlite_session: Session) -> None:
    sec = _add(sqlite_session, isin="US0378331005", symbol="AAPL", sector="Technology")
    result = classify_equity(
        sqlite_session, sec, openfigi=_FigiStub(_EQUITY), edgar=_EdgarStub(None)
    )
    assert result is not None
    assert sec.industries_gics_sectors_level1 == "Information Technology"
    assert sec.classification_tier == ClassificationTier.EXTERNAL_API
    assert sec.classification_source == "provider-sector"
    assert sec.classification_confidence == Decimal("0.80")
    assert sec.classification_locked is False
    assert sec.classified_by == "auto"
    assert sec.classified_at is not None
    assert sec.classified_at.tzinfo is None  # naive UTC per project convention


def test_sic_fallback_path(sqlite_session: Session) -> None:
    sec = _add(sqlite_session, isin="US0378331005", symbol="AAPL")
    result = classify_equity(
        sqlite_session, sec, openfigi=_FigiStub(_EQUITY), edgar=_EdgarStub("3571")
    )
    assert result is not None
    assert sec.industries_gics_sectors_level1 == "Information Technology"
    assert sec.classification_source == "edgar-sic"


def test_locked_row_is_skipped(sqlite_session: Session) -> None:
    sec = _add(sqlite_session, isin="US0378331005", symbol="AAPL", sector="Technology")
    sec.classification_locked = True
    result = classify_equity(
        sqlite_session, sec, openfigi=_FigiStub(_EQUITY), edgar=_EdgarStub(None)
    )
    assert result is None
    assert sec.industries_gics_sectors_level1 is None
    assert sec.classification_tier is None
    assert sec.classification_source is None
    assert sec.classification_confidence is None
    assert sec.classified_by is None
    assert sec.classified_at is None


def test_unresolved_when_no_sector_and_no_sic(sqlite_session: Session) -> None:
    sec = _add(sqlite_session, isin="US0378331005", symbol="AAPL")
    result = classify_equity(
        sqlite_session, sec, openfigi=_FigiStub(_EQUITY), edgar=_EdgarStub(None)
    )
    assert result is None


def test_non_equity_is_unresolved(sqlite_session: Session) -> None:
    sec = _add(sqlite_session, isin="US912828XX00", symbol="UST", sector="Technology")
    bond = OpenFIGIRecord(figi="G", market_sector="Govt")
    result = classify_equity(
        sqlite_session, sec, openfigi=_FigiStub(bond), edgar=_EdgarStub(None)
    )
    assert result is None


def test_api_outage_degrades_to_unresolved(sqlite_session: Session) -> None:
    sec = _add(sqlite_session, isin="US0378331005", symbol="AAPL", sector="Technology")
    result = classify_equity(
        sqlite_session,
        sec,
        openfigi=_FigiStub(None, raises=True),
        edgar=_EdgarStub(None),
    )
    assert result is None


def test_edgar_outage_degrades_to_unresolved(sqlite_session: Session) -> None:
    # No provider sector, so it falls to the EDGAR SIC path, which errors.
    sec = _add(sqlite_session, isin="US0378331005", symbol="AAPL")
    result = classify_equity(
        sqlite_session,
        sec,
        openfigi=_FigiStub(_EQUITY),
        edgar=_EdgarStub(None, raises=True),
    )
    assert result is None  # batch continues; ExternalAPIError did not propagate
    assert sec.industries_gics_sectors_level1 is None


def test_unresolved_when_no_identifier(sqlite_session: Session) -> None:
    sec = _add(sqlite_session, sector="Technology")  # no isin, no symbol
    result = classify_equity(
        sqlite_session, sec, openfigi=_FigiStub(_EQUITY), edgar=_EdgarStub(None)
    )
    assert result is None
    assert sec.industries_gics_sectors_level1 is None
