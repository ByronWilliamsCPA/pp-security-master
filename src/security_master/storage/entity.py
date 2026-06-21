"""SQLAlchemy ORM models for the Entity Registry: clients and their legal entities.

The Entity Registry is the WHO axis of the IBOR/ABOR navigation model (ADR-016):
the canonical join between this IBOR, the Xero ABOR (one organisation per legal
entity), and xero-crypto (one client). Entity identity lives here and never in
the asset taxonomy, preserving the axis separation that `TAXONOMY_GUIDE.md`
requires.
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base

# entity_type -> default IRS tax form. Constrained to the five forms the
# Byron Williams CPA master chart of accounts reports against (1040/1065/1120/
# 990/1041); see ADR-016 and the COA "Types" sheet.
ENTITY_TYPE_TAX_FORMS: dict[str, str] = {
    "individual": "1040",
    "sole_proprietor": "1040",
    "partnership": "1065",
    "llc": "1065",
    "s_corp": "1120",
    "c_corp": "1120",
    "nonprofit": "990",
    "trust": "1041",
    "estate": "1041",
}


def default_tax_form_for(entity_type: str) -> str | None:
    """Return the default IRS tax form for an entity type.

    Args:
        entity_type: A legal-entity type key (case-insensitive), e.g. ``"llc"``.

    Returns:
        The matching tax-form string (e.g. ``"1065"``), or ``None`` if the
        entity type is not recognised.
    """
    return ENTITY_TYPE_TAX_FORMS.get(entity_type.strip().lower())


class Client(Base):
    """A CPA client: the top-level tenant that owns one or more legal entities."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    tax_jurisdiction: Mapped[str | None] = mapped_column(String(50))
    accounting_method: Mapped[str | None] = mapped_column(String(20))
    # True when the client holds only direct investments (no fund look-through).
    direct_investments_only: Mapped[bool] = mapped_column(Boolean, default=False)

    # Cross-system identity (ADR-016 identifier contract): xero-crypto Client.id.
    xero_crypto_client_id: Mapped[str | None] = mapped_column(
        String(36),
        unique=True,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(
            tzinfo=None
        ),  # nosemgrep: python.lang.maintainability.return.return-not-in-function -- FP: semgrep misreads SQLAlchemy column default lambdas
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(
            tzinfo=None
        ),  # nosemgrep: python.lang.maintainability.return.return-not-in-function -- FP: semgrep misreads SQLAlchemy column default lambdas
        onupdate=lambda: datetime.now(UTC).replace(
            tzinfo=None
        ),  # nosemgrep: python.lang.maintainability.return.return-not-in-function -- FP: semgrep misreads SQLAlchemy column default lambdas
    )

    legal_entities: Mapped[list["LegalEntity"]] = relationship(
        "LegalEntity",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Return a debug-friendly representation of this Client.

        Returns:
            String in the form <Client(id=..., name=..., status=...)>.
        """
        return f"<Client(id={self.id}, name='{self.name}', status='{self.status}')>"


class LegalEntity(Base):
    """A legal entity under a client; maps one-to-one to a Xero organisation."""

    __tablename__ = "legal_entities"
    __table_args__ = (
        UniqueConstraint("client_id", "name", name="uq_legal_entity_client_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # e.g. individual, llc, s_corp, c_corp, partnership, trust, nonprofit.
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # IRS form this entity reports on; defaults via default_tax_form_for().
    tax_form: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Cross-system identity (ADR-016 identifier contract).
    xero_organisation_id: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )
    # PP file/portfolio that holds this entity's positions.
    pp_portfolio_ref: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(
            tzinfo=None
        ),  # nosemgrep: python.lang.maintainability.return.return-not-in-function -- FP: semgrep misreads SQLAlchemy column default lambdas
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(
            tzinfo=None
        ),  # nosemgrep: python.lang.maintainability.return.return-not-in-function -- FP: semgrep misreads SQLAlchemy column default lambdas
        onupdate=lambda: datetime.now(UTC).replace(
            tzinfo=None
        ),  # nosemgrep: python.lang.maintainability.return.return-not-in-function -- FP: semgrep misreads SQLAlchemy column default lambdas
    )

    client: Mapped["Client"] = relationship("Client", back_populates="legal_entities")

    def __repr__(self) -> str:
        """Return a debug-friendly representation of this LegalEntity.

        Returns:
            String in the form <LegalEntity(id=..., name=..., type=..., form=...)>.
        """
        return (
            f"<LegalEntity(id={self.id}, name='{self.name}', "
            f"type='{self.entity_type}', form='{self.tax_form}')>"
        )
