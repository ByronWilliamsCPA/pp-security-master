"""Unit tests for the Entity Registry models (ADR-016, Phase E1)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from security_master.storage.entity import (
    Client,
    LegalEntity,
    default_tax_form_for,
)


@pytest.mark.parametrize(
    ("entity_type", "expected"),
    [
        ("individual", "1040"),
        ("sole_proprietor", "1040"),
        ("partnership", "1065"),
        ("llc", "1065"),
        ("s_corp", "1120"),
        ("c_corp", "1120"),
        ("nonprofit", "990"),
        ("trust", "1041"),
        ("estate", "1041"),
        ("LLC", "1065"),
        ("  Trust  ", "1041"),
    ],
)
def test_default_tax_form_for_known_types(entity_type: str, expected: str) -> None:
    """Known entity types resolve to the expected IRS form, case/space-insensitive."""
    assert default_tax_form_for(entity_type) == expected


def test_default_tax_form_for_unknown_type_returns_none() -> None:
    """An unrecognised entity type yields None rather than raising."""
    assert default_tax_form_for("cooperative") is None


def test_client_with_multiple_legal_entities_persists(
    sqlite_session: Session,
) -> None:
    """A client persists with its legal entities and the relationship round-trips."""
    client = Client(
        name="Williams Family",
        xero_crypto_client_id="11111111-1111-1111-1111-111111111111",
        legal_entities=[
            LegalEntity(
                name="Williams Holdings LLC",
                entity_type="llc",
                tax_form=default_tax_form_for("llc"),
                xero_organisation_id="xero-org-llc-1",
                pp_portfolio_ref="Williams.xml/Holdings",
            ),
            LegalEntity(
                name="Williams IRA",
                entity_type="individual",
                tax_form=default_tax_form_for("individual"),
                xero_organisation_id="xero-org-ira-1",
            ),
        ],
    )
    sqlite_session.add(client)
    sqlite_session.commit()

    stored = sqlite_session.query(Client).filter_by(name="Williams Family").one()
    assert stored.id is not None
    assert stored.status == "active"
    assert stored.direct_investments_only is False
    assert len(stored.legal_entities) == 2
    assert {e.tax_form for e in stored.legal_entities} == {"1065", "1040"}
    # Back-reference resolves to the owning client.
    assert stored.legal_entities[0].client is stored
    # Audit timestamps are populated by the column defaults.
    assert stored.created_at is not None
    assert stored.legal_entities[0].created_at is not None


def test_direct_investments_only_client(sqlite_session: Session) -> None:
    """A direct-investments-only client persists the flag and needs no entities."""
    client = Client(name="Solo Direct Investor", direct_investments_only=True)
    sqlite_session.add(client)
    sqlite_session.commit()

    stored = sqlite_session.query(Client).filter_by(name="Solo Direct Investor").one()
    assert stored.direct_investments_only is True
    assert stored.legal_entities == []


def test_legal_entity_name_unique_within_client(sqlite_session: Session) -> None:
    """Two legal entities with the same name under one client violate the constraint."""
    client = Client(name="Dup Co")
    client.legal_entities.append(LegalEntity(name="Main", entity_type="llc"))
    client.legal_entities.append(LegalEntity(name="Main", entity_type="s_corp"))
    sqlite_session.add(client)
    with pytest.raises(IntegrityError):
        sqlite_session.commit()


def test_cascade_delete_removes_legal_entities(sqlite_session: Session) -> None:
    """Deleting a client cascades to its legal entities."""
    client = Client(name="Temp Client")
    client.legal_entities.append(LegalEntity(name="E1", entity_type="llc"))
    sqlite_session.add(client)
    sqlite_session.commit()
    assert sqlite_session.query(LegalEntity).count() == 1

    sqlite_session.delete(client)
    sqlite_session.commit()
    assert sqlite_session.query(LegalEntity).count() == 0


def test_repr_includes_key_fields(sqlite_session: Session) -> None:
    """The model reprs surface the identifying fields for debugging."""
    client = Client(name="Repr Co")
    entity = LegalEntity(name="Repr LLC", entity_type="llc", tax_form="1065")
    client.legal_entities.append(entity)
    sqlite_session.add(client)
    sqlite_session.commit()

    assert "Repr Co" in repr(client)
    assert "Repr LLC" in repr(entity)
    assert "1065" in repr(entity)
