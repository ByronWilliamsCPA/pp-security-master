"""
Benchmark Security Generator for Portfolio Performance Integration
Generates synthetic single securities that replicate multi-asset portfolio performance
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
from pydantic import BaseModel, Field

from ..analytics.models.portfolio_models import PortfolioPosition, PortfolioSnapshot
from ..database.engine import DatabaseEngine


@dataclass
class BenchmarkComposition:
    """Composition of a benchmark portfolio at a point in time."""

    date: date
    positions: list[PortfolioPosition]
    total_value: Decimal
    weights: dict[str, Decimal]  # security_id -> weight

    @classmethod
    def from_portfolio_snapshot(
        cls,
        snapshot: PortfolioSnapshot,
    ) -> "BenchmarkComposition":
        """Create benchmark composition from portfolio snapshot.

        Args:
            snapshot (PortfolioSnapshot): Portfolio snapshot to derive weights from.

        Returns:
            BenchmarkComposition: New composition with weights calculated from snapshot market values.
        """
        weights = {}
        total_mv = snapshot.total_market_value

        for position in snapshot.positions:
            if total_mv > 0:
                weights[position.security_id] = position.market_value / total_mv
            else:
                weights[position.security_id] = Decimal("0")

        return cls(
            date=snapshot.date,
            positions=snapshot.positions.copy(),
            total_value=total_mv,
            weights=weights,
        )


@dataclass
class BenchmarkReturn:
    """Daily return calculation for benchmark."""

    date: date
    portfolio_return: Decimal
    individual_returns: dict[str, Decimal]  # security_id -> return
    weights: dict[str, Decimal]  # security_id -> weight
    total_return: Decimal

    def get_attribution_breakdown(self) -> dict[str, Decimal]:
        """Get return attribution by security.

        Returns:
            dict[str, Decimal]: Dict mapping security_id to its weighted return contribution.
        """
        attribution = {}
        for security_id in self.weights:
            weight = self.weights.get(security_id, Decimal("0"))
            security_return = self.individual_returns.get(security_id, Decimal("0"))
            attribution[security_id] = weight * security_return
        return attribution


class SyntheticBenchmarkSecurity(BaseModel):
    """Synthetic security that replicates portfolio performance."""

    # Security identification
    uuid: UUID = Field(default_factory=uuid4)
    symbol: str
    name: str
    isin: str | None = None
    currency: str = "USD"

    # Benchmark metadata
    benchmark_type: str = Field(
        ...,
        description="'reference_portfolio', 'custom_index', 'blended'",
    )
    base_date: date = Field(..., description="Inception date for price calculation")
    base_price: Decimal = Field(
        default=Decimal("100.00"),
        description="Starting price (usually 100)",
    )

    # Composition tracking
    underlying_portfolio_id: str | None = None
    underlying_securities: list[str] = Field(default_factory=list)
    rebalance_frequency: str = Field(
        default="monthly",
        description="'daily', 'monthly', 'quarterly'",
    )

    # Performance tracking
    price_history: list[dict[str, Any]] = Field(default_factory=list)
    return_history: list[dict[str, Any]] = Field(default_factory=list)
    composition_history: list[dict[str, Any]] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class BenchmarkSecurityGenerator:
    """Generates synthetic benchmark securities for Portfolio Performance."""

    def __init__(self, db_engine: DatabaseEngine = None):
        self.db_engine = db_engine or DatabaseEngine()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def create_portfolio_benchmark(
        self,
        portfolio_id: str,
        benchmark_name: str,
        start_date: date,
        end_date: date | None = None,
        base_price: Decimal = Decimal("100.00"),
        rebalance_frequency: str = "monthly",
    ) -> SyntheticBenchmarkSecurity:
        """
        Create a synthetic benchmark security that replicates a portfolio's performance.

        Args:
            portfolio_id (str): Portfolio to replicate.
            benchmark_name (str): Name for the synthetic security.
            start_date (date): Start date for performance calculation.
            end_date (date | None): End date (defaults to today).
            base_price (Decimal): Starting price for synthetic security.
            rebalance_frequency (str): How often to rebalance weights.

        Returns:
            SyntheticBenchmarkSecurity: Synthetic benchmark security with complete price history.
        """
        if end_date is None:
            end_date = date.today()

        self.logger.info(
            f"Creating portfolio benchmark for {portfolio_id} from {start_date} to {end_date}",
        )

        # Generate synthetic symbol
        portfolio_symbol = portfolio_id.replace("-", "").upper()[:6]
        synthetic_symbol = f"PBEN_{portfolio_symbol}"

        # Create benchmark security
        benchmark = SyntheticBenchmarkSecurity(
            symbol=synthetic_symbol,
            name=f"{benchmark_name} Benchmark",
            isin=f"SYNTH{synthetic_symbol}",
            benchmark_type="reference_portfolio",
            base_date=start_date,
            base_price=base_price,
            underlying_portfolio_id=portfolio_id,
            rebalance_frequency=rebalance_frequency,
        )

        # Calculate performance history
        self._calculate_benchmark_performance(benchmark, start_date, end_date)

        # Store in database
        self._store_benchmark_security(benchmark)

        self.logger.info(
            f"Created benchmark {synthetic_symbol} with {len(benchmark.price_history)} price points",
        )

        return benchmark

    def create_custom_index_benchmark(
        self,
        securities: list[str],
        weights: list[Decimal],
        benchmark_name: str,
        start_date: date,
        end_date: date | None = None,
        base_price: Decimal = Decimal("100.00"),
        rebalance_frequency: str = "quarterly",
    ) -> SyntheticBenchmarkSecurity:
        """
        Create a custom weighted index benchmark.

        Args:
            securities (list[str]): List of security IDs to include.
            weights (list[Decimal]): Corresponding weights (must sum to 1.0).
            benchmark_name (str): Name for the synthetic security.
            start_date (date): Start date for performance calculation.
            end_date (date | None): End date (defaults to today).
            base_price (Decimal): Starting price.
            rebalance_frequency (str): Rebalancing frequency.

        Returns:
            SyntheticBenchmarkSecurity: Synthetic benchmark security representing the custom index.

        Raises:
            ValueError: If an error occurs.
        """
        if len(securities) != len(weights):
            raise ValueError("Securities and weights lists must have same length")

        if abs(sum(weights) - Decimal("1.0")) > Decimal("0.001"):
            raise ValueError("Weights must sum to 1.0")

        if end_date is None:
            end_date = date.today()

        # Generate synthetic symbol
        symbol_hash = str(hash(tuple(securities)))[-6:]
        synthetic_symbol = f"CIDX_{symbol_hash}"

        benchmark = SyntheticBenchmarkSecurity(
            symbol=synthetic_symbol,
            name=f"{benchmark_name} Custom Index",
            isin=f"SYNTH{synthetic_symbol}",
            benchmark_type="custom_index",
            base_date=start_date,
            base_price=base_price,
            underlying_securities=securities,
            rebalance_frequency=rebalance_frequency,
        )

        # Calculate custom index performance
        self._calculate_custom_index_performance(
            benchmark,
            securities,
            weights,
            start_date,
            end_date,
        )

        # Store in database
        self._store_benchmark_security(benchmark)

        return benchmark

    def _calculate_benchmark_performance(
        self,
        benchmark: SyntheticBenchmarkSecurity,
        start_date: date,
        end_date: date,
    ):
        """Calculate performance history for portfolio benchmark.

        Args:
            benchmark (SyntheticBenchmarkSecurity): Benchmark to populate with price history.
            start_date (date): Start date for price history generation.
            end_date (date): End date for price history generation.
        """

        # Get portfolio snapshots for the period
        snapshots = self._get_portfolio_snapshots(
            benchmark.underlying_portfolio_id,
            start_date,
            end_date,
        )

        if not snapshots:
            self.logger.warning(
                f"No portfolio data found for {benchmark.underlying_portfolio_id}",
            )
            return

        # Convert to daily compositions with rebalancing
        daily_compositions = self._generate_daily_compositions(
            snapshots,
            benchmark.rebalance_frequency,
            start_date,
            end_date,
        )

        # Calculate daily returns and prices
        current_price = benchmark.base_price
        previous_value = None

        for composition in daily_compositions:
            if previous_value is not None:
                # Calculate portfolio return for the day
                portfolio_return = self._calculate_daily_portfolio_return(
                    composition,
                    previous_value,
                )

                # Update synthetic security price
                current_price = current_price * (Decimal("1") + portfolio_return)
                current_price = current_price.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )

                # Store return data
                benchmark.return_history.append(
                    {
                        "date": composition.date.isoformat(),
                        "portfolio_return": float(portfolio_return),
                        "cumulative_price": float(current_price),
                        "total_portfolio_value": float(composition.total_value),
                    },
                )

            # Store price data (PP format: integer * 100000000)
            pp_price_value = int(current_price * 100000000)
            benchmark.price_history.append(
                {
                    "date": composition.date.isoformat(),
                    "value": pp_price_value,
                    "price_decimal": float(current_price),
                },
            )

            # Store composition data
            benchmark.composition_history.append(
                {
                    "date": composition.date.isoformat(),
                    "total_value": float(composition.total_value),
                    "weights": {k: float(v) for k, v in composition.weights.items()},
                    "position_count": len(composition.positions),
                },
            )

            previous_value = composition.total_value

    def _calculate_custom_index_performance(
        self,
        benchmark: SyntheticBenchmarkSecurity,
        securities: list[str],
        weights: list[Decimal],
        start_date: date,
        end_date: date,
    ):
        """Calculate performance for custom weighted index.

        Args:
            benchmark (SyntheticBenchmarkSecurity): Benchmark to populate with price history.
            securities (list[str]): List of security IDs in the index.
            weights (list[Decimal]): Corresponding weights for each security.
            start_date (date): Start date for price history generation.
            end_date (date): End date for price history generation.
        """

        # Get price history for all securities
        price_data = self._get_securities_price_history(
            securities,
            start_date,
            end_date,
        )

        # Calculate daily index returns
        current_price = benchmark.base_price
        date_range = pd.date_range(start_date, end_date, freq="D")

        for current_date in date_range:
            if current_date.date() == start_date:
                # Store initial price
                pp_price_value = int(current_price * 100000000)
                benchmark.price_history.append(
                    {
                        "date": current_date.date().isoformat(),
                        "value": pp_price_value,
                        "price_decimal": float(current_price),
                    },
                )
                continue

            # Calculate weighted return for the day
            daily_return = Decimal("0")
            valid_data_count = 0

            for i, security_id in enumerate(securities):
                security_return = self._get_security_daily_return(
                    price_data.get(security_id, {}),
                    current_date.date(),
                )

                if security_return is not None:
                    daily_return += weights[i] * security_return
                    valid_data_count += 1

            # Only update price if we have data for majority of securities
            if valid_data_count >= len(securities) * 0.7:  # 70% threshold
                current_price = current_price * (Decimal("1") + daily_return)
                current_price = current_price.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )

                # Store return data
                benchmark.return_history.append(
                    {
                        "date": current_date.date().isoformat(),
                        "index_return": float(daily_return),
                        "cumulative_price": float(current_price),
                        "valid_securities": valid_data_count,
                    },
                )

            # Store price data
            pp_price_value = int(current_price * 100000000)
            benchmark.price_history.append(
                {
                    "date": current_date.date().isoformat(),
                    "value": pp_price_value,
                    "price_decimal": float(current_price),
                },
            )

    def _get_portfolio_snapshots(
        self,
        portfolio_id: str,
        start_date: date,
        end_date: date,
    ) -> list[PortfolioSnapshot]:
        """Get portfolio snapshots for the specified period.

        Args:
            portfolio_id (str): ID of the portfolio to query.
            start_date (date): Start of the date range.
            end_date (date): End of the date range.

        Returns:
            list[PortfolioSnapshot]: Portfolio snapshots ordered by date.
        """
        with self.db_engine.get_session() as session:
            # Implementation would query portfolio positions over time
            # This is a simplified placeholder
            snapshots = []

            # Query portfolio transactions and build snapshots
            # This would involve complex position calculation over time

            return snapshots

    def _generate_daily_compositions(
        self,
        snapshots: list[PortfolioSnapshot],
        rebalance_frequency: str,
        start_date: date,
        end_date: date,
    ) -> list[BenchmarkComposition]:
        """Generate daily portfolio compositions with periodic rebalancing.

        Args:
            snapshots (list[PortfolioSnapshot]): Historical portfolio snapshots for weight derivation.
            rebalance_frequency (str): Rebalancing frequency (daily, monthly, quarterly).
            start_date (date): Start of the date range.
            end_date (date): End of the date range.

        Returns:
            list[BenchmarkComposition]: Daily compositions for each date in the range.
        """

        compositions = []

        # Determine rebalance dates
        rebalance_dates = self._get_rebalance_dates(
            start_date,
            end_date,
            rebalance_frequency,
        )

        # Generate daily compositions
        current_date = start_date
        current_composition = None

        while current_date <= end_date:
            # Check if we need to rebalance
            if current_date in rebalance_dates or current_composition is None:
                # Find nearest snapshot for rebalancing
                nearest_snapshot = self._find_nearest_snapshot(snapshots, current_date)
                if nearest_snapshot:
                    current_composition = BenchmarkComposition.from_portfolio_snapshot(
                        nearest_snapshot,
                    )
                    current_composition.date = current_date

            if current_composition:
                # Create composition for current date
                daily_composition = BenchmarkComposition(
                    date=current_date,
                    positions=current_composition.positions.copy(),
                    total_value=current_composition.total_value,
                    weights=current_composition.weights.copy(),
                )
                compositions.append(daily_composition)

            current_date += timedelta(days=1)

        return compositions

    def _get_rebalance_dates(
        self,
        start_date: date,
        end_date: date,
        frequency: str,
    ) -> list[date]:
        """Get rebalance dates based on frequency.

        Args:
            start_date (date): Start of the date range.
            end_date (date): End of the date range.
            frequency (str): Rebalancing frequency (daily, monthly, quarterly).

        Returns:
            list[date]: Sorted list of rebalance dates within the range.
        """
        dates = []
        current_date = start_date

        if frequency == "daily":
            # Daily rebalancing - every day is a rebalance date
            while current_date <= end_date:
                dates.append(current_date)
                current_date += timedelta(days=1)

        elif frequency == "monthly":
            # Monthly rebalancing - first business day of each month
            while current_date <= end_date:
                # Add first day of month (simplified)
                if current_date.day == 1 or current_date == start_date:
                    dates.append(current_date)
                current_date += timedelta(days=1)

        elif frequency == "quarterly":
            # Quarterly rebalancing
            quarters = [(1, 1), (4, 1), (7, 1), (10, 1)]  # Jan, Apr, Jul, Oct
            year = start_date.year
            while year <= end_date.year:
                for month, day in quarters:
                    rebal_date = date(year, month, day)
                    if start_date <= rebal_date <= end_date:
                        dates.append(rebal_date)
                year += 1

        return sorted(dates)

    def _find_nearest_snapshot(
        self,
        snapshots: list[PortfolioSnapshot],
        target_date: date,
    ) -> PortfolioSnapshot | None:
        """Find portfolio snapshot nearest to target date.

        Args:
            snapshots (list[PortfolioSnapshot]): Available portfolio snapshots to search.
            target_date (date): Date to find the nearest snapshot for.

        Returns:
            PortfolioSnapshot | None: Nearest snapshot or None if the list is empty.
        """
        if not snapshots:
            return None

        # Find snapshot with minimum date difference
        min_diff = float("inf")
        nearest_snapshot = None

        for snapshot in snapshots:
            diff = abs((snapshot.date - target_date).days)
            if diff < min_diff:
                min_diff = diff
                nearest_snapshot = snapshot

        return nearest_snapshot

    def _calculate_daily_portfolio_return(
        self,
        composition: BenchmarkComposition,
        previous_value: Decimal,
    ) -> Decimal:
        """Calculate daily portfolio return based on composition.

        Args:
            composition (BenchmarkComposition): Current day's portfolio composition.
            previous_value (Decimal): Portfolio total value from the prior day.

        Returns:
            Decimal: Daily return as a decimal fraction (e.g., 0.01 for 1%).
        """
        if previous_value <= 0:
            return Decimal("0")

        # Simplified calculation - would need actual price changes
        # This is a placeholder that would calculate weighted returns
        return (composition.total_value - previous_value) / previous_value

    def _get_securities_price_history(
        self,
        securities: list[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, dict[date, Decimal]]:
        """Get price history for multiple securities.

        Args:
            securities (list[str]): List of security IDs to retrieve prices for.
            start_date (date): Start of the date range.
            end_date (date): End of the date range.

        Returns:
            dict[str, dict[date, Decimal]]: Nested dict mapping security_id to date-to-price mapping.
        """
        price_data = {}

        with self.db_engine.get_session() as session:
            # Query price history for all securities
            # Implementation would retrieve from pp_price_history table
            # Return format: {security_id: {date: price}}
            pass

        return price_data

    def _get_security_daily_return(
        self,
        price_history: dict[date, Decimal],
        target_date: date,
    ) -> Decimal | None:
        """Calculate daily return for a security.

        Args:
            price_history (dict[date, Decimal]): Mapping of date to closing price.
            target_date (date): Date to calculate the return for.

        Returns:
            Decimal | None: Daily return as a fraction, or None if insufficient price data.
        """
        if target_date not in price_history:
            return None

        previous_date = target_date - timedelta(days=1)
        if previous_date not in price_history:
            return None

        current_price = price_history[target_date]
        previous_price = price_history[previous_date]

        if previous_price <= 0:
            return None

        return (current_price - previous_price) / previous_price

    def _store_benchmark_security(self, benchmark: SyntheticBenchmarkSecurity):
        """Store benchmark security in database.

        Args:
            benchmark (SyntheticBenchmarkSecurity): Benchmark security to persist.

        Raises:
            Exception: If an error occurs.
        """
        with self.db_engine.get_session() as session:
            try:
                # Store in securities_master table
                session.execute(
                    """
                    INSERT INTO securities_master (
                        uuid, symbol, name, isin, currency, 
                        asset_class, security_type, is_synthetic_benchmark
                    ) VALUES (
                        %s, %s, %s, %s, %s, 'Benchmark', 'Synthetic', true
                    ) ON CONFLICT (uuid) DO NOTHING
                """,
                    (
                        str(benchmark.uuid),
                        benchmark.symbol,
                        benchmark.name,
                        benchmark.isin,
                        benchmark.currency,
                    ),
                )

                # Store price history
                for price_point in benchmark.price_history:
                    session.execute(
                        """
                        INSERT INTO pp_price_history (
                            security_master_id, date, close_price, currency, source
                        ) SELECT id, %s, %s, %s, 'synthetic_benchmark'
                        FROM securities_master WHERE uuid = %s
                        ON CONFLICT (security_master_id, date) DO UPDATE 
                        SET close_price = EXCLUDED.close_price
                    """,
                        (
                            price_point["date"],
                            Decimal(str(price_point["price_decimal"])),
                            benchmark.currency,
                            str(benchmark.uuid),
                        ),
                    )

                # Store benchmark metadata
                session.execute(
                    """
                    INSERT INTO benchmark_securities (
                        security_uuid, benchmark_type, base_date, base_price,
                        underlying_portfolio_id, rebalance_frequency, composition_data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (security_uuid) DO UPDATE SET
                        composition_data = EXCLUDED.composition_data,
                        updated_at = NOW()
                """,
                    (
                        str(benchmark.uuid),
                        benchmark.benchmark_type,
                        benchmark.base_date,
                        benchmark.base_price,
                        benchmark.underlying_portfolio_id,
                        benchmark.rebalance_frequency,
                        str(benchmark.composition_history),  # JSON string
                    ),
                )

                session.commit()
                self.logger.info(
                    f"Stored benchmark security {benchmark.symbol} with {len(benchmark.price_history)} price points",
                )

            except Exception as e:
                session.rollback()
                self.logger.error(f"Failed to store benchmark security: {e}")
                raise

    def update_benchmark_security(
        self,
        benchmark_uuid: UUID,
        end_date: date | None = None,
    ) -> bool:
        """Update an existing benchmark security with latest data.

        Args:
            benchmark_uuid (UUID): UUID of the benchmark to update.
            end_date (date | None): Latest date to calculate through (defaults to today).

        Returns:
            bool: True if updated successfully, False if benchmark not found or error.
        """
        if end_date is None:
            end_date = date.today()

        try:
            # Load existing benchmark
            benchmark = self._load_benchmark_security(benchmark_uuid)
            if not benchmark:
                self.logger.error(f"Benchmark {benchmark_uuid} not found")
                return False

            # Find last price date
            if benchmark.price_history:
                last_price_date = date.fromisoformat(
                    benchmark.price_history[-1]["date"],
                )
                start_date = last_price_date + timedelta(days=1)
            else:
                start_date = benchmark.base_date

            if start_date > end_date:
                self.logger.info(f"Benchmark {benchmark.symbol} already up to date")
                return True

            # Calculate new performance data
            if benchmark.benchmark_type == "reference_portfolio":
                self._calculate_benchmark_performance(benchmark, start_date, end_date)
            elif benchmark.benchmark_type == "custom_index":
                # Would need to reload securities and weights for custom index
                pass

            # Store updated data
            self._store_benchmark_security(benchmark)

            self.logger.info(f"Updated benchmark {benchmark.symbol} through {end_date}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update benchmark {benchmark_uuid}: {e}")
            return False

    def _load_benchmark_security(
        self,
        benchmark_uuid: UUID,
    ) -> SyntheticBenchmarkSecurity | None:
        """Load existing benchmark security from database.

        Args:
            benchmark_uuid (UUID): UUID of the benchmark security to load.

        Returns:
            SyntheticBenchmarkSecurity | None: Loaded benchmark or None if not found.
        """
        # Implementation would load from database tables
        return None

    def get_benchmark_performance_summary(
        self,
        benchmark_uuid: UUID,
        period_days: int = 252,
    ) -> dict[str, Any]:
        """Get performance summary for benchmark security.

        Args:
            benchmark_uuid (UUID): UUID of the benchmark to summarize.
            period_days (int): Number of trading days to include in the summary.

        Returns:
            dict[str, Any]: Performance summary with total_return, avg_daily_return, and metadata.
        """
        benchmark = self._load_benchmark_security(benchmark_uuid)
        if not benchmark or not benchmark.return_history:
            return {}

        # Calculate summary statistics
        returns = [
            Decimal(str(r["portfolio_return"]))
            for r in benchmark.return_history[-period_days:]
        ]

        if not returns:
            return {}

        total_return = returns[-1] if returns else Decimal("0")
        avg_return = sum(returns) / len(returns) if returns else Decimal("0")

        # Convert to annualized metrics
        trading_days = len(returns)
        annualized_return = (
            (1 + avg_return) ** (252 / trading_days) - 1
            if trading_days > 0
            else Decimal("0")
        )

        return {
            "benchmark_symbol": benchmark.symbol,
            "benchmark_name": benchmark.name,
            "period_days": trading_days,
            "total_return": float(total_return),
            "annualized_return": float(annualized_return),
            "underlying_securities": len(benchmark.underlying_securities),
            "last_update": (
                benchmark.price_history[-1]["date"] if benchmark.price_history else None
            ),
        }


# Usage Examples and Testing


async def create_reference_portfolio_benchmark_example():
    """Example: Create benchmark for reference portfolio."""
    generator = BenchmarkSecurityGenerator()

    # Create benchmark that tracks a specific portfolio
    benchmark = generator.create_portfolio_benchmark(
        portfolio_id="portfolio-123-uuid",
        benchmark_name="Balanced Growth Reference",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        base_price=Decimal("100.00"),
        rebalance_frequency="monthly",
    )

    print(f"Created benchmark security: {benchmark.symbol}")
    print(f"Price points generated: {len(benchmark.price_history)}")
    print(f"Return history: {len(benchmark.return_history)}")

    return benchmark


async def create_custom_index_benchmark_example():
    """Example: Create custom weighted index benchmark."""
    generator = BenchmarkSecurityGenerator()

    # Create 60/40 stock/bond benchmark
    securities = ["security-1-uuid", "security-2-uuid"]  # Stock ETF, Bond ETF
    weights = [Decimal("0.60"), Decimal("0.40")]  # 60% stocks, 40% bonds

    benchmark = generator.create_custom_index_benchmark(
        securities=securities,
        weights=weights,
        benchmark_name="Conservative Growth 60/40",
        start_date=date(2024, 1, 1),
        base_price=Decimal("100.00"),
        rebalance_frequency="quarterly",
    )

    print(f"Created custom index benchmark: {benchmark.symbol}")
    return benchmark


def calculate_benchmark_attribution_example():
    """Example: Performance attribution analysis."""
    generator = BenchmarkSecurityGenerator()

    # This would analyze how much each underlying security contributed
    # to the benchmark's performance
    benchmark_uuid = uuid4()  # Would be actual benchmark UUID

    summary = generator.get_benchmark_performance_summary(
        benchmark_uuid=benchmark_uuid,
        period_days=252,  # 1 year
    )

    print("Benchmark Performance Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    # Demonstration of benchmark security generation

    async def main():
        print("=== Benchmark Security Generator Demo ===")

        # Example 1: Reference portfolio benchmark
        print("\n1. Creating reference portfolio benchmark...")
        await create_reference_portfolio_benchmark_example()

        # Example 2: Custom index benchmark
        print("\n2. Creating custom index benchmark...")
        await create_custom_index_benchmark_example()

        # Example 3: Performance attribution
        print("\n3. Performance attribution analysis...")
        calculate_benchmark_attribution_example()

    # asyncio.run(main())
