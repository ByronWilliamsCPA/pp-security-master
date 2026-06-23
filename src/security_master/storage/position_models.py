"""SQLAlchemy ORM models for broker position snapshots (point-in-time holdings).

Mirrors the per-provider pattern of ``transaction_models``: an abstract base holds
columns common to every broker's position snapshot; one concrete table per provider
adds provider-specific fields. SP2 implements the IBKR table; future Wells Fargo and
crypto snapshot tables are siblings.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class PositionSnapshotBase(Base):
    """Base class for all broker position-snapshot tables."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)

    # Snapshot scope: a holding is identified by account + as-of date.
    account_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Security identification (provider-agnostic subset).
    security_name: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(20), index=True)
    isin: Mapped[str | None] = mapped_column(String(12), index=True)
    cusip: Mapped[str | None] = mapped_column(String(9))

    # Reported quantity and value.
    position: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    position_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Import metadata.
    import_batch_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_file: Mapped[str | None] = mapped_column(String(255))

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


class InteractiveBrokersOpenPosition(PositionSnapshotBase):
    """Interactive Brokers Flex Query <OpenPosition> snapshot rows.

    Idempotency key is the natural point-in-time tuple
    ``(account_number, report_date, conid)``: a snapshot row carries no
    transactionID, so re-importing the same positions file is a no-op.
    """

    __tablename__ = "ibkr_open_positions"
    __table_args__ = (
        UniqueConstraint(
            "account_number",
            "report_date",
            "conid",
            name="uq_ibkr_open_positions_acct_date_conid",
        ),
    )

    conid: Mapped[str | None] = mapped_column(String(20), index=True)
    figi: Mapped[str | None] = mapped_column(String(12), index=True)
    mark_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cost_basis_money: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cost_basis_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    asset_class: Mapped[str | None] = mapped_column(String(20))
    sub_category: Mapped[str | None] = mapped_column(String(20))
    side: Mapped[str | None] = mapped_column(String(8))  # Long / Short

    def __repr__(self) -> str:
        return (
            f"<InteractiveBrokersOpenPosition(id={self.id}, account={self.account_number}, "
            f"report_date={self.report_date}, conid='{self.conid}', "
            f"position={self.position})>"
        )
