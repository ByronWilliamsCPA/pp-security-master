"""Broker-account to Portfolio-Performance account mapping.

Maps a broker ``account_number`` to a Portfolio Performance ``pp_group`` and
``pp_account``. This is the broker-account-to-PP bridge the L1->L2 normalizer
reads. Seedable and auditable as data rather than code.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class AccountMapping(Base):
    """One broker account mapped to a Portfolio Performance group + account."""

    __tablename__ = "account_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    pp_group: Mapped[str] = mapped_column(String(100), nullable=False)
    pp_account: Mapped[str] = mapped_column(String(100), nullable=False)
    # Optional future linkage to the entity registry; unused by SP3 logic.
    legal_entity_id: Mapped[int | None] = mapped_column(ForeignKey("legal_entities.id"))

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

    def __repr__(self) -> str:
        return (
            f"<AccountMapping(account_number='{self.account_number}', "
            f"pp_group='{self.pp_group}', pp_account='{self.pp_account}')>"
        )
