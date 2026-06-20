# ADR-001: Transaction-Centric Data Import Architecture

**Date**: 2025-08-22  
**Status**: Accepted  
**Deciders**: Byron, Development Team  
**Consulted**: Portfolio Performance Integration Requirements  
**Informed**: Data Quality Team  

## Context

The Security Master Service needs to import financial data from multiple institutions (Wells Fargo, Interactive Brokers, AltoIRA, etc.) and provide consolidated views for Portfolio Performance XML/JSON exports. Initial analysis revealed that each institution provides data at different levels of granularity and with varying schemas.

Key requirements:

- Import transaction-level data from multiple financial institutions
- Maintain data lineage and quality traceability  
- Support Portfolio Performance group and account hierarchies
- Enable data quality validation through institutional data comparison
- Provide consolidated views for XML/JSON export to Portfolio Performance

## Decision

We will implement a **transaction-centric, four-category table architecture** with institution-specific import tables and consolidated views.

### Four Main Categories

1. **Security Master** - Centralized security reference data with complete taxonomy
2. **Transactions** - Institution-specific transaction imports  
3. **Holdings** - Derived position calculations from transactions
4. **Prices** - Market data and valuation feeds

### Architecture Pattern

```text
Raw Institution Data → Institution Tables → Consolidated Views → PP Export
     (Transactions)    (Per-Institution)    (Group/Account)    (XML/JSON)
```

### Table Structure

#### Institution-Specific Transaction Tables

- `transactions_wells_fargo` - Wells Fargo transaction imports
- `transactions_interactive_brokers` - IBKR Flex Query imports
- `transactions_altoira` - AltoIRA PDF/CSV imports  
- `transactions_kubera` - Kubera aggregated data (for comparison)

#### Consolidated Views

- `v_holdings_by_group` - Portfolio Performance group-level holdings
- `v_holdings_by_account` - Portfolio Performance account-level holdings  
- `v_transactions_consolidated` - All transactions normalized for PP export

## Rationale

### Benefits

1. **Data Lineage**: Complete traceability from institution source to PP export
2. **Flexible Granularity**: Import at vendor-provided detail level, export at PP-required level
3. **Data Quality**: Institution-to-institution comparison for validation
4. **Scalability**: Easy addition of new institutions without schema changes
5. **Backfill Capability**: Missing data can be populated from reference sources
6. **Performance**: Optimized views for specific export requirements

### Institution-Specific Benefits

- **Wells Fargo**: Import CSV exports with account hierarchy
- **Interactive Brokers**: Process Flex Query XML with complex derivatives
- **AltoIRA**: Parse PDF statements with manual data entry support
- **Kubera**: Real-time aggregated data for validation and reconciliation

### Portfolio Performance Integration

- **Group Mapping**: Kubera sheets → PP Groups (IRA, Taxable, etc.)
- **Account Mapping**: Institution accounts → PP Securities Accounts  
- **Transaction Types**: Normalized buy/sell/dividend/transfer operations
- **Security Matching**: ISIN/Symbol-based security resolution

## Consequences

### Positive

- **Maintainable**: Clear separation of concerns by institution
- **Auditable**: Full transaction history preserved
- **Flexible**: Support for varying institution data formats
- **Quality**: Built-in validation through cross-institution comparison

### Negative

- **Complexity**: More tables to maintain than single consolidated approach
- **Storage**: Duplication between raw and consolidated data
- **Processing**: ETL pipeline required for view generation

### Neutral

- **Development Time**: Upfront investment for long-term maintainability
- **Documentation**: Requires clear mapping documentation for each institution

## Implementation Notes

### Phase 1: Core Infrastructure

1. Security Master table (complete taxonomy)
2. Institution transaction table templates
3. Basic consolidated views

### Phase 2: Institution Integrations  

1. Wells Fargo CSV parser → `transactions_wells_fargo`
2. Interactive Brokers Flex Query → `transactions_interactive_brokers`
3. AltoIRA PDF parser → `transactions_altoira`

### Phase 3: Validation & Export

1. Kubera comparison → `transactions_kubera`
2. Data quality validation views
3. Portfolio Performance XML/JSON export

### Data Quality Strategy

- **Institutional Validation**: Compare holdings across institutions
- **Reference Data Backfill**: Populate missing security classifications
- **Temporal Consistency**: Validate transaction sequences and dates
- **Value Reconciliation**: Cross-check position values with market data

## Related Decisions

- **ADR-002**: Portfolio Performance Backup and Restoration (Accepted)
- **ADR-003**: Securities Master Data Sourcing Hierarchy (Deferred)  
- **ADR-004**: Data Quality Validation Framework (Accepted)

## References

- Portfolio Performance XML Import Documentation
- Interactive Brokers Flex Query API
- Wells Fargo Account Export Formats
- AltoIRA Statement Parsing Requirements
- Kubera API Integration Guide
