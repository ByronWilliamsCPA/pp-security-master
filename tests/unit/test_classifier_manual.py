"""Tier-4 manual classification: lock honored, provenance written."""

import pytest
from sqlalchemy.orm import Session

from security_master.classifier.manual import apply_manual_classification
from security_master.classifier.types import (
    AssignmentKind,
    ClassificationLockedError,
    ClassificationTier,
    ManualAssignment,
)
from security_master.storage.models import SecurityMaster

pytestmark = [pytest.mark.unit, pytest.mark.classifier]


def _new_security(session: Session) -> SecurityMaster:
    sec = SecurityMaster(name="Apple Inc.", isin="US0378331005")
    session.add(sec)
    session.commit()
    session.refresh(sec)
    return sec


def test_assign_gics_sector_writes_provenance_and_locks(
    sqlite_session: Session,
) -> None:
    sec = _new_security(sqlite_session)
    result = apply_manual_classification(
        sqlite_session,
        sec,
        ManualAssignment(AssignmentKind.GICS_SECTOR, "Information Technology"),
        classified_by="byron",
    )
    assert sec.industries_gics_sectors_level1 == "Information Technology"
    assert sec.classification_tier == ClassificationTier.MANUAL
    assert sec.classification_source == "manual"
    assert sec.classification_confidence == pytest.approx(1.0)
    assert sec.classification_locked is True
    assert sec.classified_by == "byron"
    assert sec.classified_at is not None
    assert result.locked is True


def test_assign_sleeve_writes_brx_plus_columns(sqlite_session: Session) -> None:
    sec = _new_security(sqlite_session)
    apply_manual_classification(
        sqlite_session,
        sec,
        ManualAssignment(AssignmentKind.SLEEVE, "AC.ALTS.CRYPTO.BTC"),
        classified_by="byron",
    )
    assert sec.brx_plus_level1 == "Alternatives"
    assert sec.brx_plus_level2 == "Crypto (BTC)"
    assert sec.brx_plus == "AC.ALTS.CRYPTO.BTC"


def test_assign_cash_sets_cash_level1(sqlite_session: Session) -> None:
    sec = _new_security(sqlite_session)
    apply_manual_classification(
        sqlite_session,
        sec,
        ManualAssignment(AssignmentKind.CASH, "Cash & Cash Equivalents"),
        classified_by="byron",
    )
    assert sec.brx_plus_level1 == "Cash & Cash Equivalents"


def test_locked_row_refuses_without_force(sqlite_session: Session) -> None:
    sec = _new_security(sqlite_session)
    apply_manual_classification(
        sqlite_session,
        sec,
        ManualAssignment(AssignmentKind.GICS_SECTOR, "Energy"),
        classified_by="byron",
    )
    with pytest.raises(ClassificationLockedError):
        apply_manual_classification(
            sqlite_session,
            sec,
            ManualAssignment(AssignmentKind.GICS_SECTOR, "Financials"),
            classified_by="someone-else",
        )
    assert sec.industries_gics_sectors_level1 == "Energy"  # unchanged


def test_force_overrides_locked_row_and_restamps(sqlite_session: Session) -> None:
    sec = _new_security(sqlite_session)
    apply_manual_classification(
        sqlite_session,
        sec,
        ManualAssignment(AssignmentKind.GICS_SECTOR, "Energy"),
        classified_by="byron",
    )
    apply_manual_classification(
        sqlite_session,
        sec,
        ManualAssignment(AssignmentKind.GICS_SECTOR, "Financials"),
        classified_by="byron2",
        force=True,
    )
    assert sec.industries_gics_sectors_level1 == "Financials"
    assert sec.classification_locked is True
    assert sec.classified_by == "byron2"
