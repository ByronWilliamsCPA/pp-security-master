"""
Portfolio Performance specific database models for complete backup restoration capability.
These models capture the exact structure needed to generate PP XML backup files.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base


class PPClientConfig(Base):
    """Portfolio Performance client configuration."""

    __tablename__ = "pp_client_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(nullable=False)  # PP version (e.g., 66)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Configuration metadata
    config_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="default",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Audit fields
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
        return f"<PPClientConfig(version={self.version}, currency='{self.base_currency}', config='{self.config_name}')>"


class PPAccount(Base):
    """Portfolio Performance accounts (deposit/cash accounts)."""

    __tablename__ = "pp_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False)

    # Account attributes (PP XML properties)
    attributes: Mapped[str | None] = mapped_column(
        Text,
    )  # JSON storage for PP attributes

    # Audit fields
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

    # Relationships
    transactions: Mapped[list["PPAccountTransaction"]] = relationship(
        "PPAccountTransaction",
        back_populates="account",
    )
    portfolios: Mapped[list["PPPortfolio"]] = relationship(
        "PPPortfolio",
        back_populates="reference_account",
    )

    def __repr__(self) -> str:
        return f"<PPAccount(uuid='{self.uuid}', name='{self.name}', currency='{self.currency_code}', retired={self.is_retired})>"


class PPPortfolio(Base):
    """Portfolio Performance portfolios (security holding accounts)."""

    __tablename__ = "pp_portfolios"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False)

    # Reference account relationship
    reference_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("pp_accounts.id"),
    )
    reference_account: Mapped[Optional["PPAccount"]] = relationship(
        "PPAccount",
        back_populates="portfolios",
    )

    # Audit fields
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

    # Relationships
    transactions: Mapped[list["PPPortfolioTransaction"]] = relationship(
        "PPPortfolioTransaction",
        back_populates="portfolio",
    )

    def __repr__(self) -> str:
        return f"<PPPortfolio(uuid='{self.uuid}', name='{self.name}', retired={self.is_retired})>"


class PPAccountTransaction(Base):
    """Portfolio Performance account transactions (cash movements)."""

    __tablename__ = "pp_account_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4,
    )

    # Account relationship
    account_id: Mapped[int] = mapped_column(
        ForeignKey("pp_accounts.id"),
        nullable=False,
    )
    account: Mapped["PPAccount"] = relationship(
        "PPAccount",
        back_populates="transactions",
    )

    # Transaction core data
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Security reference (optional for cash-only transactions)
    security_id: Mapped[int | None] = mapped_column(
        ForeignKey("securities_master.id"),
    )

    # Share quantity (usually 0 for account transactions)
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=0)

    # Transaction type (BUY, SELL, DEPOSIT, WITHDRAWAL, etc.)
    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Cross-entry information for linked portfolio transactions
    cross_entry_type: Mapped[str | None] = mapped_column(
        String(50),
    )  # "buysell", "dividend", etc.

    # Audit fields
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

    # Relationships
    portfolio_transactions: Mapped[list["PPPortfolioTransaction"]] = relationship(
        "PPPortfolioTransaction",
        back_populates="linked_account_transaction",
    )
    units: Mapped[list["PPTransactionUnit"]] = relationship(
        "PPTransactionUnit",
        foreign_keys="[PPTransactionUnit.transaction_id]",
        primaryjoin="and_(PPAccountTransaction.id == PPTransactionUnit.transaction_id, PPTransactionUnit.transaction_type == 'ACCOUNT')",
    )

    def __repr__(self) -> str:
        return f"<PPAccountTransaction(uuid='{self.uuid}', date={self.transaction_date}, type='{self.transaction_type}', amount={self.amount})>"


class PPPortfolioTransaction(Base):
    """Portfolio Performance portfolio transactions (security movements)."""

    __tablename__ = "pp_portfolio_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4,
    )

    # Portfolio relationship
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("pp_portfolios.id"),
        nullable=False,
    )
    portfolio: Mapped["PPPortfolio"] = relationship(
        "PPPortfolio",
        back_populates="transactions",
    )

    # Transaction core data
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Security reference (required for portfolio transactions)
    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities_master.id"),
        nullable=False,
    )

    # Share quantity (required for portfolio transactions)
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    # Transaction type (BUY, SELL, DIVIDEND, etc.)
    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Cross-reference to linked account transaction
    linked_account_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("pp_account_transactions.id"),
    )
    linked_account_transaction: Mapped[Optional["PPAccountTransaction"]] = relationship(
        "PPAccountTransaction",
        back_populates="portfolio_transactions",
    )

    # Audit fields
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

    # Relationships
    units: Mapped[list["PPTransactionUnit"]] = relationship(
        "PPTransactionUnit",
        foreign_keys="[PPTransactionUnit.transaction_id]",
        primaryjoin="and_(PPPortfolioTransaction.id == PPTransactionUnit.transaction_id, PPTransactionUnit.transaction_type == 'PORTFOLIO')",
    )

    def __repr__(self) -> str:
        return f"<PPPortfolioTransaction(uuid='{self.uuid}', date={self.transaction_date}, type='{self.transaction_type}', shares={self.shares}, amount={self.amount})>"


class PPTransactionUnit(Base):
    """Portfolio Performance transaction units (fees, taxes, etc.)."""

    __tablename__ = "pp_transaction_units"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Reference to either account or portfolio transaction
    transaction_id: Mapped[int] = mapped_column(nullable=False)
    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # 'ACCOUNT' or 'PORTFOLIO'

    # Unit details
    unit_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'FEE', 'TAX'
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(
            tzinfo=None
        ),  # nosemgrep: python.lang.maintainability.return.return-not-in-function -- FP: semgrep misreads SQLAlchemy column default lambdas
    )

    def __repr__(self) -> str:
        return f"<PPTransactionUnit(transaction_id={self.transaction_id}, type='{self.unit_type}', amount={self.amount})>"


class PPSecurityPrice(Base):
    """Portfolio Performance daily security prices."""

    __tablename__ = "pp_security_prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Security reference
    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities_master.id"),
        nullable=False,
    )

    # Price data
    price_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    price_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # PP stores as integer (multiply by 100000000)

    # Data source tracking
    price_source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
    )  # manual, yahoo, pp, etc.

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(
            tzinfo=None
        ),  # nosemgrep: python.lang.maintainability.return.return-not-in-function -- FP: semgrep misreads SQLAlchemy column default lambdas
    )

    # Unique constraint on security + date
    __table_args__ = (
        UniqueConstraint("security_id", "price_date", name="uq_security_price_date"),
    )

    @property
    def price_decimal(self) -> Decimal:
        """Convert PP integer price to decimal.

        Returns:
            Decimal: Price as a Decimal value (PP integer divided by 100,000,000).
        """
        return Decimal(self.price_value) / Decimal(100000000)

    @price_decimal.setter
    def price_decimal(self, value: Decimal) -> None:
        """Set price from decimal value.

        Args:
            value (Decimal): Decimal price to store as a PP integer (multiplied by 100,000,000).
        """
        self.price_value = int(value * Decimal(100000000))

    def __repr__(self) -> str:
        return f"<PPSecurityPrice(security_id={self.security_id}, date={self.price_date}, price={self.price_decimal})>"


class PPSetting(Base):
    """Portfolio Performance user settings and configuration."""

    __tablename__ = "pp_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Setting identification
    setting_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'properties', 'bookmarks', etc.
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False)
    setting_value: Mapped[str | None] = mapped_column(Text)

    # Audit fields
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

    # Unique constraint on category + key
    __table_args__ = (
        UniqueConstraint(
            "setting_category",
            "setting_key",
            name="uq_setting_category_key",
        ),
    )

    def __repr__(self) -> str:
        return f"<PPSetting(category='{self.setting_category}', key='{self.setting_key}', value='{self.setting_value}')>"


class PPBookmark(Base):
    """Portfolio Performance user bookmarks."""

    __tablename__ = "pp_bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Bookmark data
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern: Mapped[str] = mapped_column(String(500), nullable=False)

    # Display order
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Audit fields
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
        return f"<PPBookmark(label='{self.label}', pattern='{self.pattern}')>"


# Portfolio Performance Import/Export Tracking
class PPImportBatch(Base):
    """Track Portfolio Performance XML import batches."""

    __tablename__ = "pp_import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Import metadata
    source_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    pp_version: Mapped[int] = mapped_column(nullable=False)

    # Import statistics
    securities_imported: Mapped[int] = mapped_column(default=0)
    accounts_imported: Mapped[int] = mapped_column(default=0)
    portfolios_imported: Mapped[int] = mapped_column(default=0)
    transactions_imported: Mapped[int] = mapped_column(default=0)
    prices_imported: Mapped[int] = mapped_column(default=0)

    # Processing status
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Audit fields
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
        return f"<PPImportBatch(batch_id='{self.batch_id}', status='{self.status}', securities={self.securities_imported}, transactions={self.transactions_imported})>"
