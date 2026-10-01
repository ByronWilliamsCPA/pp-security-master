"""SQLAlchemy ORM model for the ``account_balances`` ledger.

One row per account per as-of date. Rows are written by the nightly IBKR totals
job (source ``ibkr_flex``) and by the manual-mark CLI (source ``manual_mark``),
and are read by downstream consumers, so the column contract (account key
prefix, category vocabulary, decimal value with two places, separate currency)
is enforced here and in the migration, not only in application code.

Entity identity is deliberately a bare UUID with no foreign key: the entity
master lives outside this database, and the account registry seed maps each
account key to that UUID. This table never becomes a second entity master.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base

# Kept in sync with security_master.balances.rules.CATEGORIES; the CHECK
# constraint below repeats the literal list so the DDL is self-describing.
# #VERIFY: test_balance_models pins the two lists together.
_CATEGORY_CHECK = (
    "category IN ('Investments', 'Retirement', 'Cash', "
    "'Digital currency', 'Alternatives')"
)


class AccountBalance(Base):
    """One balance mark for one account on one as-of date."""

    __tablename__ = "account_balances"
    __table_args__ = (
        UniqueConstraint("account_key", "as_of", name="uq_account_balances_key_as_of"),
        CheckConstraint(
            "substr(account_key, 1, 3) = 'pp:'",
            name="ck_account_balances_key_prefix",
        ),
        CheckConstraint(_CATEGORY_CHECK, name="ck_account_balances_category"),
        CheckConstraint("length(currency) = 3", name="ck_account_balances_currency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Stable, unique, "pp:"-prefixed key. Never a full account number.
    account_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # #CRITICAL (data integrity): entity_id is required and never null; a
    # balance with no owning entity cannot be attributed downstream.
    # #VERIFY: test_entity_id_is_required in tests/unit/test_balance_models.py.
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)

    # Market value in ``currency``. Negative only for overdrafts. Numeric, never
    # float, at every layer; serialized as a two-place decimal string.
    value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    entered_by: Mapped[str] = mapped_column(String(100), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        """Return a debug representation that omits the balance value.

        Returns:
            String naming the account key, as-of date, and source only.
        """
        return (
            f"<AccountBalance(account_key='{self.account_key}', "
            f"as_of={self.as_of}, source='{self.source}')>"
        )
