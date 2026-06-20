# ADR-008: External Repository Integration Strategy

**Status:** Deferred (accepted in principle; not yet implemented as of 2026-06-19)  
**Date:** 2025-01-22  
**Deciders:** Development Team  
**Technical Story:** Integration of external Portfolio Performance ecosystem repositories

> **Feasibility note (2026-06-19):** This decision assumes cross-language library integration (JavaScript, Excel, C#). That assumption is under review for a single-language Python + uv project and may be revised before implementation.

## Context

The Portfolio Performance ecosystem contains numerous high-quality open-source repositories that provide functionality overlapping with our Security-Master Service. We need a consistent strategy for leveraging these external repositories while maintaining code quality, security, and long-term maintainability.

Key repositories identified for integration:

- **pp-portfolio-classifier** (fizban99) - ETF/stock classification using Morningstar data
- **ppxml2db** (pfalcon) - PP XML ⇄ SQLite round-trip converter  
- **pyscripter/XLRisk** - Monte Carlo simulation for risk analysis
- **lequant40/portfolio_allocation_js** - Portfolio optimization algorithms
- **mayest/Portfolio-Performance** - Risk-adjusted performance metrics
- **Official PP repositories** - Reference implementation and documentation

## Decision

We will adopt a **tiered integration strategy** based on repository criticality, maintenance status, and integration complexity:

### Tier 1: Critical Dependencies (Fork + Integrate)

**Repositories:** pp-portfolio-classifier, ppxml2db

**Strategy:**

- Fork repository to our organization
- Integrate fork as git subtree into `src/external/`
- Maintain upstream sync via automated PR process
- Apply security patches and customizations to fork
- Vendor dependencies to ensure build reproducibility

**Rationale:** These provide core functionality critical to our service. Forking ensures we control security updates and can customize as needed.

### Tier 2: Enhanced Analytics (Library Integration)

**Repositories:** pyscripter/XLRisk, lequant40/portfolio_allocation_js, mayest/Portfolio-Performance  

**Strategy:**

- Use as external dependencies via package managers (npm, pip, nuget)
- Pin to specific versions with security scanning
- Create adapter layers in `src/adapters/` for integration
- Implement fallback functionality for critical paths
- Monitor for security updates and compatibility

**Rationale:** These provide advanced analytics features that enhance our service but aren't core to basic functionality.

### Tier 3: Reference Implementation (Documentation Only)

**Repositories:** portfolio-performance/portfolio, portfolio-performance/portfolio-help

**Strategy:**

- Reference for understanding data structures and workflows
- No direct code integration
- Document compatibility requirements
- Use for testing data format compliance

**Rationale:** Official repositories provide reference implementation but direct integration would create unnecessary coupling.

### Tier 4: Future Consideration (Track Only)

**Repositories:** Docker containers, specialized parsers, broker-specific tools

**Strategy:**

- Track in PP_REPOS_REFERENCE.md with priority rankings
- Evaluate for integration based on user demand
- Consider for Phase 3/4 roadmap items

## Integration Guidelines

### Security Requirements

- All external code must pass security scanning (bandit, safety, npm audit)
- Dependencies must be pinned to specific versions
- Fork repositories must have branch protection enabled
- Security patches must be applied within 30 days

### Code Quality Standards

- External code must meet our linting standards (Black, Ruff, MyPy)
- Adapter layers must have >80% test coverage
- Integration points must have comprehensive error handling
- Documentation must explain external dependency usage

### Maintenance Responsibilities

- Monthly upstream sync reviews for Tier 1 repositories
- Quarterly security updates for Tier 2 dependencies  
- Annual evaluation of Tier 4 repositories for promotion
- Deprecation plan required before removing any integration

## Implementation Plan

### Phase 1: Core Integration (Sprint 1-2)

```text
src/external/
├── pp-portfolio-classifier/     # Fork + subtree
├── ppxml2db/                   # Fork + subtree
└── README.md                   # Integration documentation
```

### Phase 2: Analytics Integration (Sprint 3-4)

```text
src/adapters/
├── risk_analysis.py           # XLRisk adapter
├── optimization.py            # portfolio_allocation_js adapter  
└── performance_metrics.py     # Portfolio-Performance adapter
```

### Phase 3: Production Hardening (Sprint 5-6)

- Automated security scanning pipeline
- Upstream sync automation
- Fallback implementation for critical paths
- Integration testing suite

## Consequences

### Positive

- **Reduced Development Time**: Leverage proven implementations instead of building from scratch
- **Improved Quality**: Use battle-tested code from Portfolio Performance ecosystem
- **Feature Acceleration**: Advanced analytics capabilities available immediately
- **Community Alignment**: Stay compatible with Portfolio Performance standards

### Negative  

- **Security Complexity**: More attack surface through external dependencies
- **Maintenance Overhead**: Ongoing upstream sync and security monitoring required
- **Version Conflicts**: Potential dependency hell with multiple external libraries
- **Code Bloat**: Additional code that may not be fully utilized

### Mitigation Strategies

- Comprehensive security scanning and monitoring
- Clear deprecation policies for unused integrations
- Adapter pattern to isolate external dependencies
- Regular audit of external code usage

## Compliance

This ADR aligns with:

- **ADR-005**: External API Integration Strategy (dependency management patterns)
- **ADR-006**: Security and Authentication Architecture (security scanning requirements)
- **ADR-007**: Deployment and Infrastructure Strategy (containerization considerations)

## References

- [PP_REPOS_REFERENCE.md](../../PP_REPOS_REFERENCE.md) - Comprehensive repository analysis
- [PROJECT_PLAN.md](../../PROJECT_PLAN.md) - Integration roadmap alignment
- [pp-portfolio-classifier](https://github.com/fizban99/pp-portfolio-classifier) - Core classification dependency
- [ppxml2db](https://github.com/pfalcon/ppxml2db) - XML/database integration
