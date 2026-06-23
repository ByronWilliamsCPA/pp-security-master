# ADR-003: Securities Master Data Sourcing Hierarchy

**Date**: 2025-08-22  
**Status**: Partially Accepted (Tier 4 manual classification implemented in Phase D3 / PR #114, 2026-06-21; Tiers 1-3 automated sourcing deferred pending ADR-005)  
**Deciders**: Byron, Development Team  
**Consulted**: Portfolio Performance API Documentation, pp-portfolio-classifier Analysis  
**Informed**: Data Quality Team, Classification Engine Team  

## Context

The Securities Master Service requires comprehensive, accurate, and up-to-date security reference data to support classification, taxonomy assignment, and Portfolio Performance integration. Multiple data sources are available with varying levels of reliability, cost, coverage, and maintenance requirements.

The challenge is establishing a clear hierarchy that maximizes data quality while minimizing operational complexity and external dependencies. We need a systematic approach that leverages existing Portfolio Performance capabilities first, then supplements with progressively more specialized sources.

## Decision

We will implement a **four-tier hierarchical data sourcing strategy** for securities master data, proceeding from most reliable/native sources to manual processes as needed.

### Tier 1: Portfolio Performance Native APIs and Feeds

**Priority**: Highest (Tier 1)  
**Rationale**: Leverage existing, maintained data sources that PP users already rely on  
**Maintenance**: Zero additional overhead - PP team maintains these sources  

#### **1.1 Portfolio Performance Built-in Quote Providers**

- **Yahoo Finance Integration**: PP's primary price and basic data source
- **Portfolio Performance Historical Data**: Existing price feeds and basic security metadata
- **PP Security Database**: Securities already known to Portfolio Performance ecosystem

#### **1.2 Portfolio Performance Quote Feed APIs**

- **Feed Types**: PP supports multiple quote providers (Yahoo, Alpha Vantage, etc.)
- **Coverage**: Basic OHLC pricing, fundamental security identification (ISIN, symbol, name)
- **Integration**: Direct integration with PP's existing quote feed infrastructure

#### **1.3 Portfolio Performance Community Data**

- **Taxonomy Classifications**: User-contributed classifications in PP ecosystem
- **Security Master Imports**: PP XML imports from other users with enhanced classifications
- **Community Templates**: Shared classification schemas from PP forum/community

### Tier 2: pp-portfolio-classifier Integration

**Priority**: High (Tier 2)  
**Rationale**: Proven open-source tool specifically designed for Portfolio Performance ecosystem  
**Maintenance**: Community-maintained, direct integration possible  

#### **2.1 pp-portfolio-classifier Core Functionality**

- **GitHub Repository**: <https://github.com/fizban99/pp-portfolio-classifier>
- **Fund Analysis**: Mutual fund and ETF holdings breakdown and classification
- **Data Sources**: Morningstar, fund prospectuses, regulatory filings
- **Output Format**: Direct compatibility with Portfolio Performance taxonomy structure

#### **2.2 Enhanced pp-portfolio-classifier Integration**

- **Automated Classification**: Batch processing of fund/ETF portfolios
- **Holdings Analysis**: Underlying asset classification for complex instruments
- **Sector Mapping**: GICS sector assignment based on underlying holdings
- **Custom Integration**: Enhanced version with database persistence and API wrapper

#### **2.3 pp-portfolio-classifier Data Coverage**

- **Mutual Funds**: Comprehensive analysis of fund holdings and objectives
- **ETFs**: Index tracking and holdings-based classification
- **Complex Instruments**: REITs, closed-end funds, structured products
- **Geographic Coverage**: Primarily US/European funds with some international coverage

#### **2.4 BlackRock Quarterly Holdings Reports (PDF Integration)**

- **Data Source**: Quarterly holdings reports published by BlackRock for iShares ETFs
- **Asset Allocation Focus**: Detailed sector and geographic breakdowns for asset allocation analysis
- **Coverage**: Comprehensive holdings data for iShares ETF portfolio
- **Processing**: PDF parsing with structured data extraction for classification updates
- **Frequency**: Quarterly updates aligned with regulatory filing requirements
- **Quality**: Authoritative source directly from fund manager with regulatory validation

### Tier 3: Custom API Development and External Sources

**Priority**: Medium (Tier 3)  
**Rationale**: Fill gaps not covered by PP native sources or pp-portfolio-classifier  
**Maintenance**: Project team responsibility - sustainable API integrations only  

#### **3.1 OpenFIGI API Integration**

- **Coverage**: Comprehensive equity and bond identification and classification
- **Cost Model**: Free tier with rate limits, paid tiers for higher volume
- **Data Quality**: Bloomberg-maintained, institutional-grade reference data
- **Classification**: GICS sectors, industry groups, security types

#### **3.2 Alpha Vantage API Integration**

- **Coverage**: Fundamental data, company profiles, financial statements
- **Cost Model**: Free tier with daily limits, affordable paid tiers
- **Data Quality**: Good coverage for US/major international equities
- **Use Case**: Supplement OpenFIGI for fundamental analysis data

#### **3.3 Financial Modeling Prep API**

- **Coverage**: Company profiles, financial ratios, ESG data
- **Cost Model**: Freemium model with reasonable paid tiers
- **Data Quality**: Good for US equities, growing international coverage
- **Use Case**: Enhanced fundamental data and ESG classifications

#### **3.4 Government and Regulatory Sources**

- **SEC EDGAR**: US regulatory filings, fund prospectuses
- **ESMA FIRDS**: European regulatory reference data
- **National Regulators**: Country-specific regulatory databases
- **Cost Model**: Free access, but requires parsing and maintenance

### Tier 4: Manual Data Entry and Curation Processes

**Priority**: Lowest (Tier 4)  
**Rationale**: Handle edge cases, private investments, and data gaps that automation cannot address  
**Maintenance**: Manual processes with workflow management and audit trails  

#### **4.1 Manual Classification Interface**

- **Web UI**: Browser-based classification interface for unmatched securities
- **Workflow Management**: Assignment, review, approval processes
- **Data Validation**: Cross-reference checks against other sources
- **Audit Trail**: Complete history of manual classifications and changes

#### **4.2 Private Investment Processing**

- **Private Equity**: Manual classification with industry/sector assignment
- **Real Estate**: Property type, geographic, and asset class classification
- **Alternative Investments**: Commodities, collectibles, cryptocurrency
- **Documentation Requirements**: Supporting documentation for manual entries

#### **4.3 Expert Review and Override Capability**

- **Automated Override**: Manual corrections to automated classifications
- **Expert Validation**: Subject matter expert review of complex classifications
- **Quality Assurance**: Systematic review of high-value or high-risk classifications
- **Documentation**: Rationale and supporting evidence for manual overrides

#### **4.3.1 Phase D3 Realization (provenance and override-lock model)**

Phase D3 realized this override capability concretely. The abstract "automated
override" and "audit trail" requirements above are now backed by six columns on
the `securities_master` table (migration `d3a1c0ffee01`):

- `classification_tier` (Integer, nullable): the sourcing tier that set the
  classification; 4 = manual.
- `classification_source` (String(50), nullable): provenance label, e.g. `manual`.
- `classification_confidence` (Numeric(3,2), nullable): 0.00-1.00; manual
  assignments use 1.00.
- `classification_locked` (Boolean, NOT NULL, server_default false): the
  load-bearing integration contract. Automated tiers (1-3) MUST skip locked rows
  so a later automated run cannot silently overwrite a human classification.
- `classified_by` (String(100), nullable): audit trail (operator).
- `classified_at` (DateTime, nullable): audit trail (timestamp).

`classification_locked` is the part that makes the four-tier cascade safe: it
converts "manual overrides automated" from a workflow convention into a schema
enforced contract. See ADR-015 for the coverage map and licensing posture that
scope what Tier-4 manual classification covers.

## Implementation Strategy

### Data Source Cascade Logic

```python
def classify_security(security_identifier):
    """
    Hierarchical classification with fallback logic
    """
    # Tier 1: PP Native Sources
    classification = query_pp_native_sources(security_identifier)
    if classification.is_complete():
        return classification.mark_source("pp_native")
    
    # Tier 2: pp-portfolio-classifier and BlackRock Holdings
    if security.is_fund_or_etf():
        classification = pp_portfolio_classifier.classify(security_identifier)
        if classification.is_complete():
            return classification.mark_source("pp_classifier")
    
    # Tier 2: BlackRock Quarterly Holdings (for iShares ETFs)
    if security.is_ishares_etf():
        classification = blackrock_holdings_parser.classify(security_identifier)
        if classification.is_complete():
            return classification.mark_source("blackrock_holdings")
    
    # Tier 3: Custom APIs
    classification = query_external_apis(security_identifier)
    if classification.is_complete():
        return classification.mark_source("external_api")
    
    # Tier 4: Manual Process
    return queue_for_manual_classification(security_identifier)
```

### Data Quality and Confidence Scoring

#### **Confidence Levels by Tier**

- **Tier 1 (PP Native)**: Confidence 0.95+ (proven, community-validated)
- **Tier 2 (pp-classifier)**: Confidence 0.90+ (specialized tool, maintained)
- **Tier 2 (BlackRock Holdings)**: Confidence 0.95+ (authoritative fund manager source)
- **Tier 3 (External APIs)**: Confidence 0.80+ (institutional sources, rate-limited)
- **Tier 4 (Manual)**: Confidence variable (depends on expertise and documentation)

#### **Data Freshness Requirements**

- **Tier 1**: Real-time or daily updates (PP managed)
- **Tier 2**: Weekly batch processing (fund holdings change infrequently)
- **Tier 2 (BlackRock)**: Quarterly updates (aligned with regulatory filing schedule)
- **Tier 3**: Daily API calls with caching (respect rate limits)
- **Tier 4**: On-demand with review cycles (manual oversight)

### Cost Management Strategy

#### **Budget Allocation by Tier**

- **Tier 1**: $0/month (leverages existing PP infrastructure)
- **Tier 2**: $0/month (open source, community maintained)
- **Tier 3**: $200-500/month (API costs, primarily OpenFIGI and Alpha Vantage)
- **Tier 4**: Staff time allocation (2-4 hours/week for manual classification)

#### **Cost Controls**

- API rate limiting and intelligent caching
- Batch processing during off-peak hours
- Quarterly cost review and optimization
- Clear escalation criteria for expensive manual processes

## Rationale

### Benefits of Hierarchical Approach

1. **Reliability**: Start with most proven, maintained sources
2. **Cost Efficiency**: Minimize expensive API calls and manual effort
3. **Data Quality**: Higher tiers generally provide better data quality
4. **Maintainability**: Reduce dependency on project team for data source maintenance
5. **Scalability**: Clear escalation path as data volume grows

### PP Native Sources Advantages

- **Zero Additional Cost**: No new API fees or subscriptions
- **Proven Reliability**: Already battle-tested by PP user community
- **Seamless Integration**: Native compatibility with PP data formats
- **Community Validation**: Crowd-sourced data quality and error correction

### pp-portfolio-classifier Advantages

- **Specialized Tool**: Purpose-built for Portfolio Performance ecosystem
- **Fund Expertise**: Deep analysis of fund/ETF holdings and classifications
- **Open Source**: No licensing costs, community contributions
- **Proven Track Record**: Established user base and success stories

## Consequences

### Positive

- **Cost Control**: Minimize expensive external API usage
- **Quality Assurance**: Start with highest-quality, proven sources
- **Maintainability**: Reduce project team burden for data source maintenance
- **Community Alignment**: Leverage existing Portfolio Performance ecosystem
- **Scalability**: Clear path for handling increasing data volume

### Negative

- **Complexity**: Multiple integration points and fallback logic
- **Initial Development**: Time investment to integrate multiple tiers
- **Data Latency**: Some sources may not provide real-time updates
- **Coverage Gaps**: Some exotic securities may require manual classification

### Risk Mitigation

- **API Rate Limiting**: Intelligent caching and batch processing
- **Data Validation**: Cross-tier validation for data quality assurance
- **Fallback Logic**: Graceful degradation when higher tiers are unavailable
- **Cost Monitoring**: Automated alerts for unexpected API usage spikes

## Success Metrics

### Coverage Targets by Tier

- **Tier 1 (PP Native)**: Cover 60-70% of common securities (stocks, major ETFs)
- **Tier 2 (pp-classifier)**: Cover 80-90% of funds and ETFs
- **Tier 3 (External APIs)**: Cover 95-98% of all public securities
- **Tier 4 (Manual)**: Handle remaining 2-5% edge cases and private investments

### Quality Metrics

- **Classification Accuracy**: >98% for Tier 1, >95% for Tier 2, >92% for Tier 3
- **Data Freshness**: <24 hours for price data, <7 days for reference data
- **Coverage Completeness**: >95% of securities have basic classification within 48 hours
- **Cost Efficiency**: <$500/month total external API costs for 10,000+ securities

### Performance Targets

- **Classification Speed**: <30 seconds average for new security classification
- **Batch Processing**: Process 1,000+ securities overnight
- **API Response Time**: <5 seconds for individual security lookups
- **Manual Processing**: <2 hours average for manual classification queue

## Related Decisions

- **ADR-001**: Transaction-Centric Architecture (provides data volume estimates)
- **ADR-002**: Portfolio Performance Backup Restoration (defines integration requirements)
- **ADR-004**: Data Quality and Validation Framework (pending)

## References

- Portfolio Performance Quote Feed Documentation
- pp-portfolio-classifier GitHub Repository: <https://github.com/fizban99/pp-portfolio-classifier>
- OpenFIGI API Documentation: <https://www.openfigi.com/api>
- Alpha Vantage API Documentation: <https://www.alphavantage.co/documentation/>
- Portfolio Performance Community Forum Classification Discussions
