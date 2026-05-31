"""
Benchmark Security Generator Usage Examples
Demonstrates how to create and use synthetic benchmark securities
"""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from benchmark_security_generator import BenchmarkSecurityGenerator


async def example_1_reference_portfolio_benchmark():
    """
    Example 1: Create a benchmark that tracks a reference portfolio

    Use case: You have a "model portfolio" or "target allocation" that you want
    to use as a benchmark for other portfolios. This creates a single security
    that Portfolio Performance can use as a benchmark.
    """
    print("=== Example 1: Reference Portfolio Benchmark ===")

    generator = BenchmarkSecurityGenerator()

    # Create benchmark for your reference/model portfolio
    benchmark = generator.create_portfolio_benchmark(
        portfolio_id="model-portfolio-uuid-123",
        benchmark_name="Conservative Growth Model",
        start_date=date(2023, 1, 1),
        end_date=date(2024, 12, 31),
        base_price=Decimal("100.00"),
        rebalance_frequency="monthly",  # Rebalance weights monthly
    )

    print(f"✅ Created benchmark security: {benchmark.symbol}")
    print(f"   Name: {benchmark.name}")
    print(f"   ISIN: {benchmark.isin}")
    print(f"   Price points: {len(benchmark.price_history)}")
    print(f"   Tracks portfolio: {benchmark.underlying_portfolio_id}")

    # This benchmark can now be used in Portfolio Performance as a single security
    # for comparison against other portfolios

    return benchmark


async def example_2_custom_index_benchmark():
    """
    Example 2: Create a custom weighted index benchmark

    Use case: You want a specific asset allocation (like 60/40 stocks/bonds)
    as a benchmark, but using specific ETFs or securities.
    """
    print("\n=== Example 2: Custom Index Benchmark ===")

    generator = BenchmarkSecurityGenerator()

    # Define a custom 60/40 allocation
    securities = [
        "vti-etf-uuid-456",  # Vanguard Total Stock Market (60%)
        "bnd-etf-uuid-789",  # Vanguard Total Bond Market (40%)
    ]
    weights = [Decimal("0.60"), Decimal("0.40")]  # 60% stocks  # 40% bonds

    benchmark = generator.create_custom_index_benchmark(
        securities=securities,
        weights=weights,
        benchmark_name="Classic 60/40 Allocation",
        start_date=date(2023, 1, 1),
        end_date=date(2024, 12, 31),
        base_price=Decimal("100.00"),
        rebalance_frequency="quarterly",  # Rebalance quarterly
    )

    print(f"✅ Created custom index: {benchmark.symbol}")
    print(f"   Name: {benchmark.name}")
    print(f"   Components: {len(securities)} securities")
    print(f"   Weights: {[float(w) for w in weights]}")
    print(f"   Price points: {len(benchmark.price_history)}")

    return benchmark


async def example_3_sector_benchmark():
    """
    Example 3: Create a sector-specific benchmark

    Use case: You want to benchmark against a specific sector or theme,
    like "Technology Stocks" or "ESG Funds".
    """
    print("\n=== Example 3: Sector Benchmark ===")

    generator = BenchmarkSecurityGenerator()

    # Technology sector allocation
    tech_securities = [
        "aapl-uuid",  # Apple
        "msft-uuid",  # Microsoft
        "googl-uuid",  # Google
        "nvda-uuid",  # NVIDIA
        "tsla-uuid",  # Tesla
    ]

    # Equal weight allocation
    equal_weights = [Decimal("0.20")] * 5  # 20% each

    benchmark = generator.create_custom_index_benchmark(
        securities=tech_securities,
        weights=equal_weights,
        benchmark_name="Equal Weight Tech 5",
        start_date=date(2023, 6, 1),
        base_price=Decimal("100.00"),
        rebalance_frequency="monthly",
    )

    print(f"✅ Created tech sector benchmark: {benchmark.symbol}")
    print(f"   Equal weight allocation across {len(tech_securities)} tech stocks")
    print("   Monthly rebalancing to maintain equal weights")

    return benchmark


async def example_4_update_existing_benchmark():
    """
    Example 4: Update an existing benchmark with new data

    Use case: Your benchmark securities need regular updates as new
    price data becomes available.
    """
    print("\n=== Example 4: Update Existing Benchmark ===")

    generator = BenchmarkSecurityGenerator()

    # Assume we have an existing benchmark UUID
    existing_benchmark_uuid = uuid4()  # In practice, this would be from database

    # Update benchmark through current date
    success = generator.update_benchmark_security(
        benchmark_uuid=existing_benchmark_uuid,
        end_date=date.today(),
    )

    if success:
        print(f"✅ Successfully updated benchmark {existing_benchmark_uuid}")

        # Get performance summary
        summary = generator.get_benchmark_performance_summary(
            benchmark_uuid=existing_benchmark_uuid,
            period_days=252,  # Last year
        )

        print("   Performance Summary (Last 252 days):")
        if summary:
            for key, value in summary.items():
                if isinstance(value, float):
                    print(f"     {key}: {value:.4f}")
                else:
                    print(f"     {key}: {value}")
    else:
        print(f"❌ Failed to update benchmark {existing_benchmark_uuid}")


async def example_5_portfolio_performance_integration():
    """
    Example 5: How the benchmark integrates with Portfolio Performance

    This shows the complete workflow from benchmark creation to PP usage.
    """
    print("\n=== Example 5: Portfolio Performance Integration ===")

    generator = BenchmarkSecurityGenerator()

    # Step 1: Create benchmark
    benchmark = generator.create_portfolio_benchmark(
        portfolio_id="client-portfolio-uuid",
        benchmark_name="Client Target Allocation",
        start_date=date(2023, 1, 1),
        base_price=Decimal("100.00"),
        rebalance_frequency="monthly",
    )

    print(f"✅ Step 1: Created benchmark {benchmark.symbol}")

    # Step 2: Benchmark is automatically stored in securities_master table
    print("✅ Step 2: Stored in securities_master as synthetic security")

    # Step 3: Price history is stored in pp_price_history table
    print(f"✅ Step 3: {len(benchmark.price_history)} price points in pp_price_history")

    # Step 4: When PP XML is exported, this security appears as a normal security
    print("✅ Step 4: Will appear in Portfolio Performance XML exports")

    # Step 5: In Portfolio Performance, user can select this as benchmark
    print("✅ Step 5: Available as benchmark security in Portfolio Performance")
    print(f"   Symbol: {benchmark.symbol}")
    print(f"   Name: {benchmark.name}")
    print(f"   ISIN: {benchmark.isin}")

    # Step 6: Performance comparison is now possible
    print("✅ Step 6: Enables portfolio vs benchmark performance comparison")

    return benchmark


async def example_6_advanced_rebalancing_strategies():
    """
    Example 6: Advanced rebalancing strategies

    Shows different rebalancing approaches and their impacts.
    """
    print("\n=== Example 6: Advanced Rebalancing Strategies ===")

    generator = BenchmarkSecurityGenerator()

    securities = ["spy-uuid", "agg-uuid"]  # Stock ETF, Bond ETF
    weights = [Decimal("0.70"), Decimal("0.30")]  # 70/30 allocation

    # Strategy 1: Daily rebalancing (very active)
    daily_benchmark = generator.create_custom_index_benchmark(
        securities=securities,
        weights=weights,
        benchmark_name="70/30 Daily Rebalanced",
        start_date=date(2024, 1, 1),
        rebalance_frequency="daily",
    )

    # Strategy 2: Monthly rebalancing (moderate)
    monthly_benchmark = generator.create_custom_index_benchmark(
        securities=securities,
        weights=weights,
        benchmark_name="70/30 Monthly Rebalanced",
        start_date=date(2024, 1, 1),
        rebalance_frequency="monthly",
    )

    # Strategy 3: Quarterly rebalancing (conservative)
    quarterly_benchmark = generator.create_custom_index_benchmark(
        securities=securities,
        weights=weights,
        benchmark_name="70/30 Quarterly Rebalanced",
        start_date=date(2024, 1, 1),
        rebalance_frequency="quarterly",
    )

    print("✅ Created three benchmarks with different rebalancing frequencies:")
    print(f"   Daily: {daily_benchmark.symbol}")
    print(f"   Monthly: {monthly_benchmark.symbol}")
    print(f"   Quarterly: {quarterly_benchmark.symbol}")
    print("   These can be compared to see rebalancing impact on returns")


async def example_7_benchmark_quality_validation():
    """
    Example 7: Benchmark quality validation and monitoring

    Shows how to validate that benchmarks are calculating correctly.
    """
    print("\n=== Example 7: Benchmark Quality Validation ===")

    generator = BenchmarkSecurityGenerator()

    # Create a simple 50/50 benchmark for easy validation
    securities = ["security-a-uuid", "security-b-uuid"]
    weights = [Decimal("0.50"), Decimal("0.50")]

    benchmark = generator.create_custom_index_benchmark(
        securities=securities,
        weights=weights,
        benchmark_name="50/50 Test Benchmark",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),  # Short period for validation
        rebalance_frequency="daily",
    )

    print(f"✅ Created validation benchmark: {benchmark.symbol}")

    # Manual validation example (in practice, this would be automated)
    print("   Validation checks to perform:")
    print("   ✓ Weights sum to 1.0 on rebalance dates")
    print("   ✓ Price movements match weighted security returns")
    print("   ✓ No gaps or anomalies in price history")
    print("   ✓ Returns are consistent with component returns")

    # In production, these would be automated database functions
    print("   Database validation functions available:")
    print("   - validate_benchmark_price_consistency()")
    print("   - get_benchmark_composition()")
    print("   - calculate_benchmark_return()")


async def main():
    """Run all benchmark examples."""
    print("🎯 Benchmark Security Generator Examples")
    print("=" * 50)

    # Run examples
    await example_1_reference_portfolio_benchmark()
    await example_2_custom_index_benchmark()
    await example_3_sector_benchmark()
    await example_4_update_existing_benchmark()
    await example_5_portfolio_performance_integration()
    await example_6_advanced_rebalancing_strategies()
    await example_7_benchmark_quality_validation()

    print("\n" + "=" * 50)
    print("🎉 All benchmark examples completed!")
    print("\nKey Benefits:")
    print("✅ Portfolio Performance can use any multi-asset allocation as benchmark")
    print("✅ Synthetic securities replicate complex portfolio performance")
    print("✅ Automatic rebalancing with configurable frequencies")
    print("✅ Performance attribution shows contribution by underlying assets")
    print("✅ Quality validation ensures benchmark accuracy")
    print("✅ Easy integration with existing PP workflows")


if __name__ == "__main__":
    asyncio.run(main())


# ==========================================
# PORTFOLIO PERFORMANCE USAGE INSTRUCTIONS
# ==========================================

"""
How to Use Generated Benchmark Securities in Portfolio Performance:

1. BENCHMARK CREATION:
   - Run benchmark generator to create synthetic security
   - Security is automatically added to securities_master table
   - Price history is populated in pp_price_history table

2. XML EXPORT:
   - Generated benchmarks appear in PP XML exports as normal securities
   - Include complete price history and metadata
   - ISIN format: SYNTH[SYMBOL] for easy identification

3. PORTFOLIO PERFORMANCE IMPORT:
   - Import XML containing benchmark securities
   - Benchmarks appear in securities list with "Synthetic" designation
   - Can be used like any other security

4. BENCHMARK ASSIGNMENT:
   - In Portfolio Performance: Portfolio → Properties → Benchmark
   - Select your generated benchmark security from the list
   - PP will calculate relative performance automatically

5. PERFORMANCE ANALYSIS:
   - Portfolio Performance shows portfolio vs benchmark returns
   - Relative performance charts available
   - All standard PP analytics work with synthetic benchmarks

6. UPDATING BENCHMARKS:
   - Use update_benchmark_security() to add new data
   - Re-export XML and import into Portfolio Performance
   - Historical data is preserved and extended

7. MULTIPLE BENCHMARKS:
   - Create different benchmarks for different time periods
   - Use sector-specific benchmarks for focused analysis
   - Compare portfolios against multiple benchmark strategies

8. VALIDATION:
   - Database functions validate benchmark calculations
   - Quality checks ensure price consistency
   - Performance attribution tracks component contributions
"""
