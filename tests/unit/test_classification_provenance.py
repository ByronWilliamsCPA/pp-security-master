"""Provenance + override-lock columns on SecurityMaster (Phase D3)."""

import pytest
from sqlalchemy.orm import Session

from security_master.storage.models import SecurityMaster

pytestmark = [pytest.mark.unit]


def test_new_security_defaults_unlocked(sqlite_session: Session) -> None:
    sec = SecurityMaster(name="Apple Inc.", isin="US0378331005")
    sqlite_session.add(sec)
    sqlite_session.commit()
    sqlite_session.refresh(sec)
    assert sec.classification_locked is False
    assert sec.classification_tier is None
    assert sec.classification_source is None
    assert sec.classification_confidence is None
    assert sec.classified_by is None
    assert sec.classified_at is None
