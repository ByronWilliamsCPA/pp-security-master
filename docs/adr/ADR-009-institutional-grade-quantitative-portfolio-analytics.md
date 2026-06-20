# ADR-009: Institutional-Grade Quantitative Portfolio Analytics

**Status:** Deferred (accepted in principle; not yet implemented as of 2026-06-19)  
**Date:** 2025-01-22  
**Deciders:** Development Team, Product Owner  
**Technical Story:** Implementation of advanced quantitative analytics for institutional-quality portfolio management

> **Feasibility note (2026-06-19):** This decision assumes cross-language library integration (JavaScript, Excel, C#). That assumption is under review for a single-language Python + uv project and may be revised before implementation.

## Context

Portfolio Performance, while excellent for retail investors, lacks the sophisticated quantitative analytics capabilities expected in institutional portfolio management. Our Security-Master Service has the opportunity to bridge this gap by implementing institutional-grade analytics that leverage our centralized data architecture and external quantitative libraries.

Current Portfolio Performance analytics limitations:

- Basic performance metrics (returns, volatility)
- Limited risk analysis capabilities  
- No portfolio optimization features
- Absence of Monte Carlo simulation
- Missing modern portfolio theory implementations
- No factor analysis or attribution
- Limited benchmark comparison capabilities

Target institutional capabilities identified:

- **Risk-Adjusted Metrics**: Sharpe Ratio, Treynor Ratio, Information Ratio, Alpha, Beta, Tracking Error
- **Portfolio Optimization**: Mean-variance optimization, risk parity, factor-based optimization
- **Risk Analysis**: Monte Carlo simulation, VaR/CVaR, stress testing, scenario analysis
- **Performance Attribution**: Factor decomposition, sector/security attribution, style analysis
- **Advanced Analytics**: Efficient frontier modeling, correlation analysis, drawdown analysis

## Decision

We will implement **institutional-grade quantitative portfolio analytics** as a core differentiating feature of the Security-Master Service, leveraging external libraries and building proprietary algorithms where necessary.

### Analytics Architecture

```text
src/analytics/
├── core/
│   ├── metrics.py              # Risk-adjusted performance metrics
│   ├── optimization.py         # Portfolio optimization algorithms
│   ├── risk_models.py          # Risk modeling and VaR calculations
│   └── attribution.py          # Performance attribution analysis
├── adapters/
│   ├── xlrisk_adapter.py       # Monte Carlo simulation via XLRisk
│   ├── js_optimizer.py         # Portfolio optimization via portfolio_allocation_js
│   └── excel_metrics.py        # Risk metrics via Portfolio-Performance C# add-in
├── models/
│   ├── factor_models.py        # Fama-French, custom factor models
│   ├── correlation_models.py   # Correlation analysis and modeling
│   └── benchmark_models.py     # Benchmark comparison and tracking
└── reports/
    ├── risk_reports.py         # Institutional risk reporting
    ├── attribution_reports.py  # Performance attribution reports
    └── optimization_reports.py # Portfolio optimization recommendations
```

### External Library Integration Strategy

**Primary Libraries** (per ADR-008 Tier 2):

- **pyscripter/XLRisk** - Monte Carlo simulation and risk analysis
- **lequant40/portfolio_allocation_js** - Modern portfolio optimization algorithms  
- **mayest/Portfolio-Performance** - Excel-based risk metrics and calculations

**Implementation Approach:**

1. **Adapter Pattern**: Isolate external dependencies behind clean interfaces
2. **Fallback Algorithms**: Implement native Python versions for critical calculations
3. **Performance Optimization**: Cache expensive calculations, use vectorized operations
4. **API Design**: RESTful endpoints for analytics consumption by web/mobile clients

### Core Analytics Capabilities

#### 1. Risk-Adjusted Performance Metrics

```python
# Target metrics implementation
- Sharpe Ratio (risk-free rate adjusted)
- Treynor Ratio (beta-adjusted returns)  
- Information Ratio (tracking error adjusted)
- Alpha (benchmark-adjusted excess return)
- Beta (systematic risk measure)
- Tracking Error (standard deviation of excess returns)
- Maximum Drawdown and recovery analysis
- Calmar Ratio (return/max drawdown)
```

#### 2. Portfolio Optimization

```python
# Optimization algorithms
- Mean-Variance Optimization (Markowitz)
- Risk Parity (equal risk contribution)
- Minimum Variance Portfolio
- Maximum Sharpe Ratio Portfolio  
- Black-Litterman Model (views incorporation)
- Factor-Based Optimization (multi-factor models)
- Constrained Optimization (sector/security limits)
```

#### 3. Risk Analysis & Simulation

```python
# Risk modeling capabilities  
- Monte Carlo Portfolio Simulation (10,000+ paths)
- Value at Risk (VaR) - Historical, Parametric, Monte Carlo
- Conditional Value at Risk (CVaR/Expected Shortfall)
- Stress Testing (custom scenarios)
- Correlation Analysis (rolling, regime-based)
- Fat-tail Risk Analysis (extreme events)
```

#### 4. Performance Attribution

```python
# Attribution analysis
- Factor Attribution (Fama-French, custom factors)
- Sector/Security Attribution  
- Asset Allocation Attribution
- Security Selection Attribution
- Style Analysis (growth/value, size, momentum)
- Currency Attribution (for international portfolios)
```

### Data Requirements

**Enhanced Database Schema:**

```sql
-- Risk metrics storage
CREATE TABLE portfolio_risk_metrics (
    portfolio_id UUID REFERENCES portfolios(id),
    calculation_date DATE,
    sharpe_ratio DECIMAL(10,4),
    treynor_ratio DECIMAL(10,4), 
    information_ratio DECIMAL(10,4),
    alpha DECIMAL(10,4),
    beta DECIMAL(10,4),
    tracking_error DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    var_95 DECIMAL(15,2),
    cvar_95 DECIMAL(15,2)
);

-- Monte Carlo simulation results
CREATE TABLE monte_carlo_simulations (
    id UUID PRIMARY KEY,
    portfolio_id UUID REFERENCES portfolios(id),
    simulation_date DATE,
    time_horizon_days INTEGER,
    num_simulations INTEGER,
    percentile_5 DECIMAL(15,2),
    percentile_95 DECIMAL(15,2),
    expected_value DECIMAL(15,2),
    confidence_intervals JSONB
);
```

### Integration with Security-Master Service

**Analytics Pipeline:**

1. **Data Ingestion**: Portfolio positions from PP XML imports
2. **Price Enrichment**: Historical price data from OpenFIGI, Yahoo Finance
3. **Benchmark Data**: Index data for comparison and beta calculations
4. **Analytics Computation**: Scheduled calculation of all metrics
5. **Result Storage**: Persistence in PostgreSQL with time-series optimization
6. **API Exposure**: REST endpoints for consumption by PP and web clients

## Implementation Plan

### Phase 1: Foundation (Sprint 1-3)

- Core metrics calculation engine (Sharpe, Alpha, Beta, etc.)
- Database schema for analytics storage
- Basic REST API for metrics retrieval
- Integration with existing portfolio data

### Phase 2: External Library Integration (Sprint 4-6)  

- XLRisk adapter for Monte Carlo simulation
- portfolio_allocation_js adapter for optimization
- Excel metrics adapter for advanced calculations
- Comprehensive error handling and fallbacks

### Phase 3: Advanced Analytics (Sprint 7-9)

- Portfolio optimization algorithms
- Performance attribution analysis  
- Factor model implementation
- Stress testing and scenario analysis

### Phase 4: Institutional Features (Sprint 10-12)

- Risk reporting suite
- Optimization recommendations
- Benchmark analysis and tracking
- Multi-currency portfolio support

## Performance Requirements

- **Calculation Speed**: Risk metrics < 5 seconds for 1000-security portfolio
- **Monte Carlo**: 10,000 simulations < 30 seconds
- **Portfolio Optimization**: Mean-variance optimization < 10 seconds  
- **Data Freshness**: Daily recalculation of all metrics
- **API Response**: Analytics endpoints < 2 second p95 response time

## Security Considerations

- **Data Privacy**: Analytics calculations on encrypted data where possible
- **Access Control**: Role-based access to advanced analytics features
- **Audit Trail**: Full logging of analytics calculations and parameters
- **Input Validation**: Comprehensive validation of portfolio and benchmark data

## Success Metrics

- **Functional**: 100% parity with institutional analytics platforms
- **Performance**: Sub-second response times for standard metrics
- **Accuracy**: <0.1% variance from established financial libraries  
- **Adoption**: 80% of users leverage advanced analytics within 6 months
- **User Satisfaction**: 4.5+ rating for analytics features

## Consequences

### Positive

- **Differentiation**: Unique institutional-grade capabilities in retail-focused ecosystem
- **Market Position**: Bridge between retail (PP) and institutional portfolio management
- **Revenue Potential**: Premium analytics features for advanced users
- **Data Value**: Rich analytics increase platform stickiness

### Negative

- **Complexity**: Significant increase in codebase and maintenance complexity
- **Performance**: Heavy computational requirements for advanced analytics
- **Dependencies**: Reliance on external quantitative libraries
- **User Experience**: Risk of overwhelming retail users with complex features

### Risk Mitigation

- **Progressive Disclosure**: Basic metrics by default, advanced features opt-in
- **Performance Optimization**: Caching, async computation, result pre-calculation
- **Documentation**: Comprehensive help for understanding analytics concepts
- **Testing**: Extensive validation against established financial benchmarks

## Compliance

This ADR builds upon:

- **ADR-008**: External Repository Integration Strategy (library integration approach)
- **ADR-001**: Transaction-Centric Architecture (data foundation for analytics)
- **ADR-003**: Securities Master Data Sourcing (price data for calculations)
- **ADR-005**: External API Integration (benchmark and price data sources)

## References

- [Modern Portfolio Theory](https://en.wikipedia.org/wiki/Modern_portfolio_theory) - Markowitz optimization foundation
- [pyscripter/XLRisk](https://github.com/pyscripter/XLRisk) - Monte Carlo simulation library
- [lequant40/portfolio_allocation_js](https://github.com/lequant40/portfolio_allocation_js) - Portfolio optimization algorithms
- [mayest/Portfolio-Performance](https://github.com/mayest/Portfolio-Performance) - Risk-adjusted performance metrics
- [CFA Institute Standards](https://www.cfainstitute.org/) - Professional analytics standards
