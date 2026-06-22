"""SQLAlchemy ORM models for the Security Master, Kubera integration, and holdings comparison tables."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base class shared by all ORM-mapped models in this package."""


class SecurityMaster(Base):
    """Row in the securities_master table: a single Portfolio Performance security with full taxonomy."""

    __tablename__ = "securities_master"

    # Primary identification
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(String(12), unique=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(20), index=True)
    wkn: Mapped[str | None] = mapped_column(String(20), index=True)

    # Descriptive fields
    note: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Pricing data
    latest_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    delta_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    delta_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    latest_date: Mapped[date | None] = mapped_column(Date)
    last_historical_date: Mapped[date | None] = mapped_column(Date)
    first_historical_date: Mapped[date | None] = mapped_column(Date)

    # Data feeds
    quote_feed_historic: Mapped[str | None] = mapped_column(String(100))
    quote_feed_latest: Mapped[str | None] = mapped_column(String(100))
    url_historic_quotes: Mapped[str | None] = mapped_column(String(500))
    url_latest_quotes: Mapped[str | None] = mapped_column(String(500))

    # Corporate actions
    next_ex_date: Mapped[date | None] = mapped_column(Date)
    next_payment_date: Mapped[date | None] = mapped_column(Date)
    next_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    # Fund/ETF specific
    logo: Mapped[str | None] = mapped_column(String(500))
    ter: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))  # Total Expense Ratio
    aum: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
    )  # Assets Under Management
    vendor: Mapped[str | None] = mapped_column(String(100))
    acquisition_fee: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    management_fee: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))

    # Asset Classifications - Level 1 (simplified)
    asset_classes_level1: Mapped[str | None] = mapped_column(String(100))
    asset_classes: Mapped[str | None] = mapped_column(String(200))

    # Sector Classifications
    sector: Mapped[str | None] = mapped_column(String(100), index=True)
    industry_group: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))

    # GICS Classifications
    industries_gics_level4: Mapped[str | None] = mapped_column(String(200))
    industries_gics: Mapped[str | None] = mapped_column(String(200))
    industries_gics_sectors_level1: Mapped[str | None] = mapped_column(String(100))
    industries_gics_sectors: Mapped[str | None] = mapped_column(String(200))

    # Asset Allocation
    asset_allocation_level1: Mapped[str | None] = mapped_column(String(100))
    asset_allocation_level2: Mapped[str | None] = mapped_column(String(100))
    asset_allocation: Mapped[str | None] = mapped_column(String(200))

    # Geographic Classifications
    market: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    regions_msci_level3: Mapped[str | None] = mapped_column(String(100))
    regions_msci: Mapped[str | None] = mapped_column(String(200))

    # Security Type Classifications
    type_of_security_level1: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
    )
    type_of_security: Mapped[str | None] = mapped_column(String(200))

    # Custom Classifications (Byron's BRX-Plus taxonomy)
    brx_plus_level1: Mapped[str | None] = mapped_column(String(100))
    brx_plus_level2: Mapped[str | None] = mapped_column(String(100))
    brx_plus: Mapped[str | None] = mapped_column(String(200))

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
    data_source: Mapped[str] = mapped_column(
        String(50),
        default="portfolio_performance",
    )
    data_quality_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
    )  # 0.00-1.00

    # Classification provenance + override lock (Phase D3, ADR-003 4.3 / ADR-015).
    # classification_locked is the integration contract: automated tiers MUST skip
    # locked rows so a later run cannot silently overwrite a human classification.
    classification_tier: Mapped[int | None] = mapped_column()  # 1-4; 4 = manual
    classification_source: Mapped[str | None] = mapped_column(String(50))
    classification_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
    )  # 0.00-1.00
    classification_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    classified_by: Mapped[str | None] = mapped_column(String(100))
    classified_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        """Return a debug-friendly string representation of this SecurityMaster record.

        Returns:
            String in the form <SecurityMaster(id=..., name=..., isin=..., symbol=...)>.
        """
        return f"<SecurityMaster(id={self.id}, name='{self.name}', isin='{self.isin}', symbol='{self.symbol}')>"


class KuberaSheet(Base):
    """Row in the kubera_sheets table: a top-level Kubera account sheet mapped to a Portfolio Performance group."""

    __tablename__ = "kubera_sheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Portfolio Performance mapping
    pp_group_name: Mapped[str | None] = mapped_column(String(100), index=True)

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
    sections: Mapped[list["KuberaSection"]] = relationship(
        "KuberaSection",
        back_populates="sheet",
    )

    def __repr__(self) -> str:
        """Return a debug-friendly string representation of this KuberaSheet record.

        Returns:
            String in the form <KuberaSheet(id=..., name=..., pp_group=...)>.
        """
        return f"<KuberaSheet(id={self.id}, name='{self.sheet_name}', pp_group='{self.pp_group_name}')>"


class KuberaSection(Base):
    """Row in the kubera_sections table: a Kubera account section within a sheet, mapped to a Portfolio Performance account."""

    __tablename__ = "kubera_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    section_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Sheet relationship
    sheet_id: Mapped[int] = mapped_column(
        ForeignKey("kubera_sheets.id"),
        nullable=False,
    )
    sheet: Mapped["KuberaSheet"] = relationship(
        "KuberaSheet",
        back_populates="sections",
    )

    # Portfolio Performance mapping
    pp_account_name: Mapped[str | None] = mapped_column(String(100), index=True)

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
    holdings: Mapped[list["KuberaHolding"]] = relationship(
        "KuberaHolding",
        back_populates="section",
    )

    def __repr__(self) -> str:
        """Return a debug-friendly string representation of this KuberaSection record.

        Returns:
            String in the form <KuberaSection(id=..., name=..., pp_account=...)>.
        """
        return f"<KuberaSection(id={self.id}, name='{self.section_name}', pp_account='{self.pp_account_name}')>"


class KuberaHolding(Base):
    """Row in the kubera_holdings table: a single security position imported from a Kubera snapshot."""

    __tablename__ = "kubera_holdings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Kubera identifiers
    kubera_asset_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Section relationship
    section_id: Mapped[int] = mapped_column(
        ForeignKey("kubera_sections.id"),
        nullable=False,
    )
    section: Mapped["KuberaSection"] = relationship(
        "KuberaSection",
        back_populates="holdings",
    )

    # Security identifiers
    ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    ticker_id: Mapped[int | None] = mapped_column()
    isin: Mapped[str | None] = mapped_column(String(12), index=True)

    # Classification
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # asset, liability
    sub_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # stock, mutual fund, etf, cash, etc.
    ticker_sub_type: Mapped[str | None] = mapped_column(
        String(20),
    )  # cs, etf, oef, scr
    asset_class: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # stock, fund, cash, crypto
    security_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # investment, other

    # Market data
    exchange: Mapped[str | None] = mapped_column(String(50))
    sector: Mapped[str | None] = mapped_column(String(100), index=True)
    ticker_sector: Mapped[str | None] = mapped_column(String(100))

    # Position data
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    current_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Cost basis
    cost_per_share: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    cost_basis_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    cost_basis_for_tax: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    # Performance metrics
    irr: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
    )  # Internal Rate of Return
    unrealized_gain_loss: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    tax_on_unrealized_gain: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    # Dates
    purchase_date: Mapped[date | None] = mapped_column(Date)
    holding_period_days: Mapped[int | None] = mapped_column()

    # Tax information
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # percentage
    tax_status: Mapped[str | None] = mapped_column(
        String(20),
    )  # taxable, tax-deferred, etc.

    # Geographic and liquidity
    geography_country: Mapped[str | None] = mapped_column(String(50))
    geography_region: Mapped[str | None] = mapped_column(String(50))
    liquidity: Mapped[str | None] = mapped_column(String(20))  # high, medium, low
    investable: Mapped[str | None] = mapped_column(
        String(50),
    )  # investable_easy_convert, investable_cash
    ownership: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        default=1.0,
    )  # ownership percentage

    # Data connection info
    aggregator: Mapped[str | None] = mapped_column(
        String(50),
    )  # finicity, yodlee, manual
    provider_name: Mapped[str | None] = mapped_column(String(100))
    provider_account_id: Mapped[str | None] = mapped_column(String(50))
    provider_connection_id: Mapped[str | None] = mapped_column(String(50))
    last_updated: Mapped[datetime | None] = mapped_column(DateTime)

    # Manual data flag
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)

    # Holdings count (for parent accounts)
    holdings_count: Mapped[int] = mapped_column(default=0)

    # Parent relationship (for account summaries)
    parent_id: Mapped[str | None] = mapped_column(String(100))
    parent_name: Mapped[str | None] = mapped_column(String(255))

    # Snapshot metadata
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_source: Mapped[str] = mapped_column(String(50), default="kubera")

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
        """Return a debug-friendly string representation of this KuberaHolding record.

        Returns:
            String in the form <KuberaHolding(id=..., name=..., ticker=..., quantity=..., value=...)>.
        """
        return f"<KuberaHolding(id={self.id}, name='{self.name}', ticker='{self.ticker}', quantity={self.quantity}, value={self.current_value})>"


class HoldingComparison(Base):
    """Row in the holding_comparisons table: variance analysis record comparing a Portfolio Performance holding against its Kubera counterpart."""

    __tablename__ = "holding_comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Comparison metadata
    comparison_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pp_group: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pp_account: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Security identification
    security_name: Mapped[str] = mapped_column(String(255), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12), index=True)
    ticker: Mapped[str | None] = mapped_column(String(20), index=True)

    # Portfolio Performance data
    pp_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    pp_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    pp_currency: Mapped[str | None] = mapped_column(String(3))

    # Kubera data
    kubera_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    kubera_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    kubera_currency: Mapped[str | None] = mapped_column(String(3))

    # Variance analysis
    quantity_variance: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    quantity_variance_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    value_variance: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    value_variance_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Status flags
    is_matched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_pp_only: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_kubera_only: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    variance_threshold_exceeded: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
    )

    # Tolerance settings used
    quantity_tolerance_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=0.01,
    )  # 0.01%
    value_tolerance_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=0.50,
    )  # 0.50%

    # Notes and investigation
    notes: Mapped[str | None] = mapped_column(Text)
    investigation_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )  # pending, investigating, resolved

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
        """Return a debug-friendly string representation of this HoldingComparison record.

        Returns:
            String in the form <HoldingComparison(id=..., security=..., pp_value=..., kubera_value=..., matched=...)>.
        """
        return f"<HoldingComparison(id={self.id}, security='{self.security_name}', pp_value={self.pp_value}, kubera_value={self.kubera_value}, matched={self.is_matched})>"
