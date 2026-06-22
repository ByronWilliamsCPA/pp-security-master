"""Provenance + override-lock columns on SecurityMaster (Phase D3)."""

import pytest
from sqlalchemy import text as sa_text
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


def test_existing_row_backfills_locked_false(sqlite_session: Session) -> None:
    """Server-side default backfills classification_locked on a raw insert.

    The ORM default=False supplies the value on ORM inserts, so it masks the
    DDL server_default. This raw insert omits the column to exercise the
    server_default directly: the backfill-safety mechanism that is the
    integration contract for pre-existing rows (ADR-003 4.3 / ADR-015).
    """
    assert SecurityMaster.__table__.c.classification_locked.server_default is not None
    # The other NOT NULL columns use Python-side defaults (no DDL DEFAULT), so a
    # raw insert must supply them; classification_locked is deliberately omitted
    # so the DDL server_default is the only thing that can fill it.
    sqlite_session.execute(
        sa_text(
            "INSERT INTO securities_master "
            "(name, currency, created_at, updated_at, data_source) "
            "VALUES ('Legacy Co', 'USD', '2026-06-21 00:00:00', "
            "'2026-06-21 00:00:00', 'legacy_backfill')"
        )
    )
    sqlite_session.commit()
    locked = sqlite_session.execute(
        sa_text(
            "SELECT classification_locked FROM securities_master WHERE name='Legacy Co'"
        )
    ).scalar_one()
    assert bool(locked) is False
