#!/usr/bin/env python3
"""
Schema export utility for visualizing database schema with dbdiagram.io
"""

from pathlib import Path

from sqlalchemy import create_mock_engine
from sqlalchemy.sql.ddl import ExecutableDDLElement

from .models import (
    Base,
)


def generate_postgres_ddl() -> str:
    """Generate PostgreSQL DDL statements from SQLAlchemy models.

    Returns:
        str: DDL SQL string with all CREATE TABLE statements joined by blank lines.
    """
    ddl_statements: list[str] = []

    def _collect_ddl(
        sql: ExecutableDDLElement,
        *_args: object,
        **_kwargs: object,
    ) -> None:
        ddl_statements.append(str(sql.compile(dialect=engine.dialect)))

    engine = create_mock_engine("postgresql://", _collect_ddl)
    Base.metadata.create_all(engine, checkfirst=False)

    return "\n\n".join(ddl_statements)


def generate_mermaid_er_diagram() -> str:
    """Generate Mermaid ER diagram for VS Code preview.

    Returns:
        str: Markdown-fenced Mermaid ER diagram string covering all schema tables.
    """

    return """# Security Master Database Schema

```mermaid
erDiagram
    SECURITIES_MASTER {
        int id PK "Auto-increment primary key"
        varchar name "Security name (required)"
        varchar isin UK "International Securities ID"
        varchar symbol "Trading symbol/ticker"
        varchar wkn "German securities identifier"
        text note "Additional notes"
        varchar currency "Currency code (default USD)"
        decimal latest_price "Current market price"
        decimal delta_percent "Price change %"
        decimal delta_amount "Price change amount"
        date latest_date "Date of latest price"
        date last_historical_date "Last historical data"
        date first_historical_date "First historical data"
        varchar quote_feed_historic "Historical data source"
        varchar quote_feed_latest "Latest price source"
        varchar url_historic_quotes "Historical quotes URL"
        varchar url_latest_quotes "Latest quotes URL"
        date next_ex_date "Next ex-dividend date"
        date next_payment_date "Next dividend payment"
        decimal next_payment_amount "Next dividend amount"
        varchar logo "Logo URL"
        decimal ter "Total Expense Ratio"
        decimal aum "Assets Under Management"
        varchar vendor "Fund company/vendor"
        decimal acquisition_fee "Acquisition fee"
        decimal management_fee "Management fee"
        varchar asset_classes_level1 "Top-level asset class"
        varchar asset_classes "Detailed asset classes"
        varchar sector "Industry sector"
        varchar industry_group "Industry group"
        varchar industry "Industry"
        varchar industries_gics_level4 "GICS Level 4"
        varchar industries_gics "All GICS industries"
        varchar industries_gics_sectors_level1 "GICS top sectors"
        varchar industries_gics_sectors "All GICS sectors"
        varchar asset_allocation_level1 "Asset allocation L1"
        varchar asset_allocation_level2 "Asset allocation L2"
        varchar asset_allocation "Full asset allocation"
        varchar market "Primary trading market"
        varchar region "Geographic region"
        varchar regions_msci_level3 "MSCI Level 3 regions"
        varchar regions_msci "All MSCI regions"
        varchar type_of_security_level1 "Top security type"
        varchar type_of_security "Detailed security type"
        varchar brx_plus_level1 "Byron custom Level 1"
        varchar brx_plus_level2 "Byron custom Level 2"
        varchar brx_plus "Byron custom full"
        timestamp created_at "Record creation"
        timestamp updated_at "Last update"
        varchar data_source "Source system"
        decimal data_quality_score "Quality score 0.00-1.00"
    }

    KUBERA_SHEETS {
        int id PK "Auto-increment primary key"
        varchar sheet_id UK "Kubera sheet UUID"
        varchar sheet_name "Sheet display name"
        varchar pp_group_name "PP group mapping"
        timestamp created_at "Record creation"
        timestamp updated_at "Last update"
    }

    KUBERA_SECTIONS {
        int id PK "Auto-increment primary key"
        varchar section_id UK "Kubera section UUID"
        varchar section_name "Section display name"
        int sheet_id FK "Reference to sheet"
        varchar pp_account_name "PP account mapping"
        timestamp created_at "Record creation"
        timestamp updated_at "Last update"
    }

    KUBERA_HOLDINGS {
        int id PK "Auto-increment primary key"
        varchar kubera_asset_id UK "Kubera asset UUID"
        varchar name "Security name from Kubera"
        int section_id FK "Reference to section"
        varchar ticker "Trading symbol"
        int ticker_id "Kubera ticker ID"
        varchar isin "ISIN from Kubera"
        varchar category "asset or liability"
        varchar sub_type "stock, mutual fund, etf, cash"
        varchar ticker_sub_type "cs, etf, oef, scr"
        varchar asset_class "stock, fund, cash, crypto"
        varchar security_type "investment, other"
        varchar exchange "Trading exchange"
        varchar sector "Industry sector"
        varchar ticker_sector "Kubera sector classification"
        decimal quantity "Number of shares/units"
        decimal current_price "Current market price"
        decimal current_value "Total current value"
        varchar currency "Currency code"
        decimal cost_per_share "Average cost per share"
        decimal cost_basis_total "Total cost basis"
        decimal cost_basis_for_tax "Tax-adjusted cost basis"
        decimal irr "Internal Rate of Return"
        decimal unrealized_gain_loss "Unrealized gain/loss"
        decimal tax_on_unrealized_gain "Tax liability"
        date purchase_date "Original purchase date"
        int holding_period_days "Days since purchase"
        decimal tax_rate "Tax rate percentage"
        varchar tax_status "taxable, tax-deferred, etc"
        varchar geography_country "Country of domicile"
        varchar geography_region "Geographic region"
        varchar liquidity "high, medium, low"
        varchar investable "investable type"
        decimal ownership "Ownership percentage"
        varchar aggregator "finicity, yodlee, manual"
        varchar provider_name "Financial institution"
        varchar provider_account_id "Provider account ID"
        varchar provider_connection_id "Provider connection ID"
        timestamp last_updated "Last provider update"
        boolean is_manual "Manually entered data"
        int holdings_count "Child holdings count"
        varchar parent_id "Parent account ID"
        varchar parent_name "Parent account name"
        date snapshot_date "Data snapshot date"
        varchar data_source "Source system"
        timestamp created_at "Record creation"
        timestamp updated_at "Last update"
    }

    HOLDING_COMPARISONS {
        int id PK "Auto-increment primary key"
        date comparison_date "Comparison run date"
        varchar pp_group "Portfolio Performance group"
        varchar pp_account "Portfolio Performance account"
        varchar security_name "Security name for comparison"
        varchar isin "ISIN for matching"
        varchar ticker "Ticker for matching"
        decimal pp_quantity "PP quantity"
        decimal pp_value "PP total value"
        varchar pp_currency "PP currency"
        decimal kubera_quantity "Kubera quantity"
        decimal kubera_value "Kubera total value"
        varchar kubera_currency "Kubera currency"
        decimal quantity_variance "Quantity difference"
        decimal quantity_variance_percent "Quantity variance %"
        decimal value_variance "Value difference"
        decimal value_variance_percent "Value variance %"
        boolean is_matched "Holdings match within tolerance"
        boolean is_pp_only "Only in Portfolio Performance"
        boolean is_kubera_only "Only in Kubera"
        boolean variance_threshold_exceeded "Variance exceeds tolerance"
        decimal quantity_tolerance_percent "Quantity tolerance %"
        decimal value_tolerance_percent "Value tolerance %"
        text notes "Investigation notes"
        varchar investigation_status "pending, investigating, resolved"
        timestamp created_at "Record creation"
        timestamp updated_at "Last update"
    }

    %% Relationships
    KUBERA_SHEETS ||--o{ KUBERA_SECTIONS : "contains"
    KUBERA_SECTIONS ||--o{ KUBERA_HOLDINGS : "contains"
```

## Table Relationships

- **KUBERA_SHEETS** → **KUBERA_SECTIONS**: One sheet contains multiple sections (e.g., "IRA" sheet contains "Wells Fargo", "Interactive Brokers" sections)
- **KUBERA_SECTIONS** → **KUBERA_HOLDINGS**: One section contains multiple holdings (e.g., "Wells Fargo" section contains individual stock/fund positions)
- **SECURITIES_MASTER**: Independent table for Portfolio Performance securities with complete taxonomy
- **HOLDING_COMPARISONS**: Analysis table comparing PP vs Kubera holdings for data quality validation

## Key Features

### Security Master
- **Complete PP Integration**: All Portfolio Performance securities with full taxonomy classification
- **Multi-level Classifications**: GICS, asset allocation, geographic, custom BRX-Plus taxonomy
- **Data Quality Scoring**: Automated completeness assessment (0.00-1.00)

### Kubera Integration
- **Hierarchical Structure**: Sheet → Section → Holdings mapping
- **Flexible PP Mapping**: Configurable mapping to PP groups and accounts
- **Rich Position Data**: Quantity, value, cost basis, performance metrics, tax implications

### Holdings Comparison
- **Variance Analysis**: Quantity and value differences with configurable tolerances
- **Exception Tracking**: PP-only, Kubera-only, threshold exceeded flags
- **Investigation Workflow**: Status tracking for variance resolution

## Usage Notes

1. **Sheet Mapping**: Kubera sheets (IRA, Crypto) map to Portfolio Performance groups
2. **Section Mapping**: Kubera sections (Wells Fargo, Interactive Brokers) map to PP accounts
3. **Data Quality**: Automated variance detection for holdings reconciliation
4. **Performance**: Strategic indexing on identifiers, dates, and comparison flags
"""


def generate_plantuml_er_diagram() -> str:
    """Generate PlantUML ER diagram for VS Code preview.

    Returns:
        str: PlantUML diagram source string covering all schema tables and relationships.
    """

    return """@startuml Security Master Database Schema

!define TABLE(name,desc) class name as "desc" << (T,#FFAAAA) >>
!define PRIMARY_KEY(x) <u>x</u>
!define FOREIGN_KEY(x) <i>x</i>
!define UNIQUE_KEY(x) <b>x</b>

skinparam class {
    BackgroundColor<<(T,#FFAAAA)>> #FFEEEE
    BorderColor #FF6666
    ArrowColor #333333
}

' Securities Master Table
entity "securities_master" as SM {
    PRIMARY_KEY(+id) : INTEGER
    --
    name : VARCHAR(255) NOT NULL
    UNIQUE_KEY(isin) : VARCHAR(12)
    symbol : VARCHAR(20)
    wkn : VARCHAR(20)
    note : TEXT
    currency : VARCHAR(3) DEFAULT 'USD'
    --
    ==Pricing Data==
    latest_price : DECIMAL(12,4)
    delta_percent : DECIMAL(8,4)
    delta_amount : DECIMAL(12,4)
    latest_date : DATE
    last_historical_date : DATE
    first_historical_date : DATE
    --
    ==Data Feeds==
    quote_feed_historic : VARCHAR(100)
    quote_feed_latest : VARCHAR(100)
    url_historic_quotes : VARCHAR(500)
    url_latest_quotes : VARCHAR(500)
    --
    ==Corporate Actions==
    next_ex_date : DATE
    next_payment_date : DATE
    next_payment_amount : DECIMAL(12,4)
    --
    ==Fund/ETF Data==
    logo : VARCHAR(500)
    ter : DECIMAL(6,4)
    aum : DECIMAL(15,2)
    vendor : VARCHAR(100)
    acquisition_fee : DECIMAL(6,4)
    management_fee : DECIMAL(6,4)
    --
    ==Asset Classifications==
    asset_classes_level1 : VARCHAR(100)
    asset_classes : VARCHAR(200)
    sector : VARCHAR(100)
    industry_group : VARCHAR(100)
    industry : VARCHAR(100)
    --
    ==GICS Classifications==
    industries_gics_level4 : VARCHAR(200)
    industries_gics : VARCHAR(200)
    industries_gics_sectors_level1 : VARCHAR(100)
    industries_gics_sectors : VARCHAR(200)
    --
    ==Asset Allocation==
    asset_allocation_level1 : VARCHAR(100)
    asset_allocation_level2 : VARCHAR(100)
    asset_allocation : VARCHAR(200)
    --
    ==Geographic==
    market : VARCHAR(100)
    region : VARCHAR(100)
    regions_msci_level3 : VARCHAR(100)
    regions_msci : VARCHAR(200)
    --
    ==Security Types==
    type_of_security_level1 : VARCHAR(100)
    type_of_security : VARCHAR(200)
    --
    ==Custom BRX-Plus==
    brx_plus_level1 : VARCHAR(100)
    brx_plus_level2 : VARCHAR(100)
    brx_plus : VARCHAR(200)
    --
    ==Audit Fields==
    created_at : TIMESTAMP DEFAULT NOW()
    updated_at : TIMESTAMP DEFAULT NOW()
    data_source : VARCHAR(50) DEFAULT 'portfolio_performance'
    data_quality_score : DECIMAL(3,2)
}

' Kubera Sheets Table
entity "kubera_sheets" as KS {
    PRIMARY_KEY(+id) : INTEGER
    --
    UNIQUE_KEY(sheet_id) : VARCHAR(50) NOT NULL
    sheet_name : VARCHAR(100) NOT NULL
    pp_group_name : VARCHAR(100)
    --
    ==Audit Fields==
    created_at : TIMESTAMP DEFAULT NOW()
    updated_at : TIMESTAMP DEFAULT NOW()
}

' Kubera Sections Table
entity "kubera_sections" as KSE {
    PRIMARY_KEY(+id) : INTEGER
    --
    UNIQUE_KEY(section_id) : VARCHAR(50) NOT NULL
    section_name : VARCHAR(100) NOT NULL
    FOREIGN_KEY(sheet_id) : INTEGER NOT NULL
    pp_account_name : VARCHAR(100)
    --
    ==Audit Fields==
    created_at : TIMESTAMP DEFAULT NOW()
    updated_at : TIMESTAMP DEFAULT NOW()
}

' Kubera Holdings Table
entity "kubera_holdings" as KH {
    PRIMARY_KEY(+id) : INTEGER
    --
    UNIQUE_KEY(kubera_asset_id) : VARCHAR(100) NOT NULL
    name : VARCHAR(255) NOT NULL
    FOREIGN_KEY(section_id) : INTEGER NOT NULL
    --
    ==Security Identifiers==
    ticker : VARCHAR(20)
    ticker_id : INTEGER
    isin : VARCHAR(12)
    --
    ==Classification==
    category : VARCHAR(50) NOT NULL
    sub_type : VARCHAR(50) NOT NULL
    ticker_sub_type : VARCHAR(20)
    asset_class : VARCHAR(50) NOT NULL
    security_type : VARCHAR(50) NOT NULL
    --
    ==Market Data==
    exchange : VARCHAR(50)
    sector : VARCHAR(100)
    ticker_sector : VARCHAR(100)
    --
    ==Position Data==
    quantity : DECIMAL(18,8) NOT NULL
    current_price : DECIMAL(12,4)
    current_value : DECIMAL(15,2) NOT NULL
    currency : VARCHAR(3) DEFAULT 'USD'
    --
    ==Cost Basis==
    cost_per_share : DECIMAL(12,4)
    cost_basis_total : DECIMAL(15,2)
    cost_basis_for_tax : DECIMAL(15,2)
    --
    ==Performance==
    irr : DECIMAL(12,6)
    unrealized_gain_loss : DECIMAL(15,2)
    tax_on_unrealized_gain : DECIMAL(15,2)
    --
    ==Dates==
    purchase_date : DATE
    holding_period_days : INTEGER
    --
    ==Tax Info==
    tax_rate : DECIMAL(5,2)
    tax_status : VARCHAR(20)
    --
    ==Geography & Liquidity==
    geography_country : VARCHAR(50)
    geography_region : VARCHAR(50)
    liquidity : VARCHAR(20)
    investable : VARCHAR(50)
    ownership : DECIMAL(3,2) DEFAULT 1.0
    --
    ==Data Connection==
    aggregator : VARCHAR(50)
    provider_name : VARCHAR(100)
    provider_account_id : VARCHAR(50)
    provider_connection_id : VARCHAR(50)
    last_updated : TIMESTAMP
    --
    ==Metadata==
    is_manual : BOOLEAN DEFAULT FALSE
    holdings_count : INTEGER DEFAULT 0
    parent_id : VARCHAR(100)
    parent_name : VARCHAR(255)
    snapshot_date : DATE NOT NULL
    data_source : VARCHAR(50) DEFAULT 'kubera'
    --
    ==Audit Fields==
    created_at : TIMESTAMP DEFAULT NOW()
    updated_at : TIMESTAMP DEFAULT NOW()
}

' Holding Comparisons Table
entity "holding_comparisons" as HC {
    PRIMARY_KEY(+id) : INTEGER
    --
    ==Comparison Metadata==
    comparison_date : DATE NOT NULL
    pp_group : VARCHAR(100) NOT NULL
    pp_account : VARCHAR(100) NOT NULL
    --
    ==Security Identification==
    security_name : VARCHAR(255) NOT NULL
    isin : VARCHAR(12)
    ticker : VARCHAR(20)
    --
    ==Portfolio Performance Data==
    pp_quantity : DECIMAL(18,8)
    pp_value : DECIMAL(15,2)
    pp_currency : VARCHAR(3)
    --
    ==Kubera Data==
    kubera_quantity : DECIMAL(18,8)
    kubera_value : DECIMAL(15,2)
    kubera_currency : VARCHAR(3)
    --
    ==Variance Analysis==
    quantity_variance : DECIMAL(18,8)
    quantity_variance_percent : DECIMAL(8,4)
    value_variance : DECIMAL(15,2)
    value_variance_percent : DECIMAL(8,4)
    --
    ==Status Flags==
    is_matched : BOOLEAN DEFAULT FALSE
    is_pp_only : BOOLEAN DEFAULT FALSE
    is_kubera_only : BOOLEAN DEFAULT FALSE
    variance_threshold_exceeded : BOOLEAN DEFAULT FALSE
    --
    ==Tolerance Settings==
    quantity_tolerance_percent : DECIMAL(5,2) DEFAULT 0.01
    value_tolerance_percent : DECIMAL(5,2) DEFAULT 0.50
    --
    ==Investigation==
    notes : TEXT
    investigation_status : VARCHAR(50) DEFAULT 'pending'
    --
    ==Audit Fields==
    created_at : TIMESTAMP DEFAULT NOW()
    updated_at : TIMESTAMP DEFAULT NOW()
}

' Relationships
KS ||--o{ KSE : "contains sections"
KSE ||--o{ KH : "contains holdings"

note top of SM : Portfolio Performance Securities\\nComplete taxonomy classification\\nData quality scoring

note top of KS : Kubera Account Sheets\\nMap to PP Groups\\n(IRA, Crypto, Real Estate)

note top of KSE : Kubera Account Sections\\nMap to PP Securities Accounts\\n(Wells Fargo, Interactive Brokers)

note top of KH : Individual Security Holdings\\nReal-time position data\\nPerformance metrics

note top of HC : Holdings Variance Analysis\\nPP vs Kubera comparison\\nData quality validation

note as N1
**Security Master Service Architecture**
====
* **Securities Master**: PP securities with complete taxonomy
* **Kubera Integration**: Real-time holdings with hierarchical mapping
* **Variance Analysis**: Automated data quality monitoring
* **Flexible Mapping**: Configurable PP group/account alignment
end note

@enduml"""


def generate_dbdiagram_schema() -> str:
    """Generate dbdiagram.io DBML format from SQLAlchemy models.

    Returns:
        str: DBML schema string suitable for import into dbdiagram.io.
    """

    return """// Database Schema for Security Master Service
// Generated from SQLAlchemy models for Portfolio Performance and Kubera integration

Project SecurityMaster {
  database_type: 'PostgreSQL'
  Note: '''
    Security Master Service for Portfolio Performance (PP)
    Centralized asset classification and taxonomy management
    Compares PP holdings with Kubera real-time data
  '''
}

Table securities_master {
  id integer [pk, increment]
  name varchar(255) [not null, note: 'Security name']
  isin varchar(12) [unique, note: 'International Securities Identification Number']
  symbol varchar(20) [note: 'Trading symbol/ticker']
  wkn varchar(20) [note: 'German securities identifier']
  note text [note: 'Additional notes']
  currency varchar(3) [not null, default: 'USD']

  // Pricing data
  latest_price decimal(12,4) [note: 'Current market price']
  delta_percent decimal(8,4) [note: 'Price change percentage']
  delta_amount decimal(12,4) [note: 'Price change amount']
  latest_date date [note: 'Date of latest price']
  last_historical_date date
  first_historical_date date

  // Data feeds
  quote_feed_historic varchar(100) [note: 'Historical data source']
  quote_feed_latest varchar(100) [note: 'Latest price data source']
  url_historic_quotes varchar(500)
  url_latest_quotes varchar(500)

  // Corporate actions
  next_ex_date date [note: 'Next ex-dividend date']
  next_payment_date date [note: 'Next dividend payment date']
  next_payment_amount decimal(12,4) [note: 'Next dividend amount']

  // Fund/ETF specific
  logo varchar(500)
  ter decimal(6,4) [note: 'Total Expense Ratio']
  aum decimal(15,2) [note: 'Assets Under Management']
  vendor varchar(100) [note: 'Fund company/vendor']
  acquisition_fee decimal(6,4)
  management_fee decimal(6,4)

  // Asset Classifications
  asset_classes_level1 varchar(100) [note: 'Top-level asset class']
  asset_classes varchar(200) [note: 'Detailed asset classes']
  sector varchar(100) [note: 'Industry sector']
  industry_group varchar(100)
  industry varchar(100)

  // GICS Classifications
  industries_gics_level4 varchar(200) [note: 'GICS Level 4 industries']
  industries_gics varchar(200) [note: 'All GICS industries']
  industries_gics_sectors_level1 varchar(100) [note: 'GICS top-level sectors']
  industries_gics_sectors varchar(200) [note: 'All GICS sectors']

  // Asset Allocation
  asset_allocation_level1 varchar(100)
  asset_allocation_level2 varchar(100)
  asset_allocation varchar(200)

  // Geographic Classifications
  market varchar(100) [note: 'Primary trading market']
  region varchar(100) [note: 'Geographic region']
  regions_msci_level3 varchar(100) [note: 'MSCI Level 3 regions']
  regions_msci varchar(200) [note: 'All MSCI regions']

  // Security Type Classifications
  type_of_security_level1 varchar(100) [note: 'Top-level security type']
  type_of_security varchar(200) [note: 'Detailed security type']

  // Custom Classifications (BRX-Plus taxonomy)
  brx_plus_level1 varchar(100) [note: 'Byron custom Level 1']
  brx_plus_level2 varchar(100) [note: 'Byron custom Level 2']
  brx_plus varchar(200) [note: 'Byron custom full taxonomy']

  // Audit fields
  created_at timestamp [default: `now()`, note: 'Record creation timestamp']
  updated_at timestamp [default: `now()`, note: 'Last update timestamp']
  data_source varchar(50) [default: 'portfolio_performance', note: 'Source system']
  data_quality_score decimal(3,2) [note: 'Data completeness score 0.00-1.00']

  indexes {
    (name) [name: 'idx_securities_name']
    (isin) [name: 'idx_securities_isin']
    (symbol) [name: 'idx_securities_symbol']
    (wkn) [name: 'idx_securities_wkn']
    (sector) [name: 'idx_securities_sector']
    (type_of_security_level1) [name: 'idx_securities_type']
  }
}

Table kubera_sheets {
  id integer [pk, increment]
  sheet_id varchar(50) [unique, not null, note: 'Kubera sheet UUID']
  sheet_name varchar(100) [not null, note: 'Sheet display name (e.g. IRA, Crypto)']
  pp_group_name varchar(100) [note: 'Mapped Portfolio Performance group']
  created_at timestamp [default: `now()`]
  updated_at timestamp [default: `now()`]

  indexes {
    (sheet_name) [name: 'idx_kubera_sheets_name']
    (pp_group_name) [name: 'idx_kubera_sheets_pp_group']
  }
}

Table kubera_sections {
  id integer [pk, increment]
  section_id varchar(50) [unique, not null, note: 'Kubera section UUID']
  section_name varchar(100) [not null, note: 'Section name (e.g. Wells Fargo, Interactive Brokers)']
  sheet_id integer [ref: > kubera_sheets.id, not null]
  pp_account_name varchar(100) [note: 'Mapped Portfolio Performance account']
  created_at timestamp [default: `now()`]
  updated_at timestamp [default: `now()`]

  indexes {
    (section_name) [name: 'idx_kubera_sections_name']
    (pp_account_name) [name: 'idx_kubera_sections_pp_account']
  }
}

Table kubera_holdings {
  id integer [pk, increment]
  kubera_asset_id varchar(100) [unique, not null, note: 'Kubera asset UUID']
  name varchar(255) [not null, note: 'Security name from Kubera']
  section_id integer [ref: > kubera_sections.id, not null]

  // Security identifiers
  ticker varchar(20) [note: 'Trading symbol']
  ticker_id integer [note: 'Kubera internal ticker ID']
  isin varchar(12) [note: 'ISIN from Kubera']

  // Classification
  category varchar(50) [not null, note: 'asset or liability']
  sub_type varchar(50) [not null, note: 'stock, mutual fund, etf, cash']
  ticker_sub_type varchar(20) [note: 'cs, etf, oef, scr']
  asset_class varchar(50) [not null, note: 'stock, fund, cash, crypto']
  security_type varchar(50) [not null, note: 'investment, other']

  // Market data
  exchange varchar(50) [note: 'Trading exchange']
  sector varchar(100) [note: 'Industry sector']
  ticker_sector varchar(100) [note: 'Kubera sector classification']

  // Position data
  quantity decimal(18,8) [not null, note: 'Number of shares/units']
  current_price decimal(12,4) [note: 'Current market price per share']
  current_value decimal(15,2) [not null, note: 'Total current market value']
  currency varchar(3) [not null, default: 'USD']

  // Cost basis
  cost_per_share decimal(12,4) [note: 'Average cost per share']
  cost_basis_total decimal(15,2) [note: 'Total cost basis']
  cost_basis_for_tax decimal(15,2) [note: 'Tax-adjusted cost basis']

  // Performance metrics
  irr decimal(12,6) [note: 'Internal Rate of Return']
  unrealized_gain_loss decimal(15,2) [note: 'Unrealized gain/loss']
  tax_on_unrealized_gain decimal(15,2) [note: 'Tax liability on gains']

  // Dates
  purchase_date date [note: 'Original purchase date']
  holding_period_days integer [note: 'Days since purchase']

  // Tax information
  tax_rate decimal(5,2) [note: 'Tax rate percentage']
  tax_status varchar(20) [note: 'taxable, tax-deferred, etc.']

  // Geographic and liquidity
  geography_country varchar(50) [note: 'Country of domicile']
  geography_region varchar(50) [note: 'Geographic region']
  liquidity varchar(20) [note: 'high, medium, low']
  investable varchar(50) [note: 'investable_easy_convert, investable_cash']
  ownership decimal(3,2) [default: 1.0, note: 'Ownership percentage']

  // Data connection info
  aggregator varchar(50) [note: 'finicity, yodlee, manual']
  provider_name varchar(100) [note: 'Financial institution name']
  provider_account_id varchar(50) [note: 'Provider account ID']
  provider_connection_id varchar(50) [note: 'Provider connection ID']
  last_updated timestamp [note: 'Last data update from provider']

  // Manual data flag
  is_manual boolean [default: false, note: 'Manually entered data']
  holdings_count integer [default: 0, note: 'Child holdings count for accounts']

  // Parent relationship (for account summaries)
  parent_id varchar(100) [note: 'Parent account ID']
  parent_name varchar(255) [note: 'Parent account name']

  // Snapshot metadata
  snapshot_date date [not null, note: 'Date of data snapshot']
  data_source varchar(50) [default: 'kubera']
  created_at timestamp [default: `now()`]
  updated_at timestamp [default: `now()`]

  indexes {
    (name) [name: 'idx_kubera_holdings_name']
    (ticker) [name: 'idx_kubera_holdings_ticker']
    (isin) [name: 'idx_kubera_holdings_isin']
    (sub_type) [name: 'idx_kubera_holdings_subtype']
    (asset_class) [name: 'idx_kubera_holdings_asset_class']
    (sector) [name: 'idx_kubera_holdings_sector']
    (snapshot_date) [name: 'idx_kubera_holdings_snapshot']
  }
}

Table holding_comparisons {
  id integer [pk, increment]
  comparison_date date [not null, note: 'Date of comparison run']
  pp_group varchar(100) [not null, note: 'Portfolio Performance group']
  pp_account varchar(100) [not null, note: 'Portfolio Performance account']

  // Security identification
  security_name varchar(255) [not null, note: 'Security name for comparison']
  isin varchar(12) [note: 'ISIN for matching']
  ticker varchar(20) [note: 'Ticker for matching']

  // Portfolio Performance data
  pp_quantity decimal(18,8) [note: 'PP quantity']
  pp_value decimal(15,2) [note: 'PP total value']
  pp_currency varchar(3) [note: 'PP currency']

  // Kubera data
  kubera_quantity decimal(18,8) [note: 'Kubera quantity']
  kubera_value decimal(15,2) [note: 'Kubera total value']
  kubera_currency varchar(3) [note: 'Kubera currency']

  // Variance analysis
  quantity_variance decimal(18,8) [note: 'Quantity difference (Kubera - PP)']
  quantity_variance_percent decimal(8,4) [note: 'Quantity variance percentage']
  value_variance decimal(15,2) [note: 'Value difference (Kubera - PP)']
  value_variance_percent decimal(8,4) [note: 'Value variance percentage']

  // Status flags
  is_matched boolean [default: false, note: 'Holdings match within tolerance']
  is_pp_only boolean [default: false, note: 'Only exists in Portfolio Performance']
  is_kubera_only boolean [default: false, note: 'Only exists in Kubera']
  variance_threshold_exceeded boolean [default: false, note: 'Variance exceeds tolerance']

  // Tolerance settings used
  quantity_tolerance_percent decimal(5,2) [default: 0.01, note: 'Quantity tolerance %']
  value_tolerance_percent decimal(5,2) [default: 0.50, note: 'Value tolerance %']

  // Notes and investigation
  notes text [note: 'Investigation notes']
  investigation_status varchar(50) [default: 'pending', note: 'pending, investigating, resolved']

  created_at timestamp [default: `now()`]
  updated_at timestamp [default: `now()`]

  indexes {
    (comparison_date) [name: 'idx_comparisons_date']
    (pp_group) [name: 'idx_comparisons_pp_group']
    (pp_account) [name: 'idx_comparisons_pp_account']
    (isin) [name: 'idx_comparisons_isin']
    (ticker) [name: 'idx_comparisons_ticker']
    (is_matched) [name: 'idx_comparisons_matched']
    (is_pp_only) [name: 'idx_comparisons_pp_only']
    (is_kubera_only) [name: 'idx_comparisons_kubera_only']
    (variance_threshold_exceeded) [name: 'idx_comparisons_variance']
  }
}

// Relationships and Notes
Note: "Securities Master contains all Portfolio Performance securities with complete taxonomy classification"
Note: "Kubera Holdings captures real-time position data from client aggregated accounts"
Note: "Holding Comparisons provides variance analysis between PP and Kubera for data quality validation"
Note: "Sheet/Section mapping enables flexible Portfolio Performance group/account alignment"
"""


def export_schema_files() -> None:
    """Export PostgreSQL DDL, dbdiagram.io DBML, Mermaid, and PlantUML ER diagram files."""
    # Create exports directory
    export_dir = Path("schema_exports")
    export_dir.mkdir(exist_ok=True)

    # Export PostgreSQL DDL
    (export_dir / "security_master_schema.sql").write_text(generate_postgres_ddl())

    # Export dbdiagram.io DBML
    (export_dir / "security_master_schema.dbml").write_text(generate_dbdiagram_schema())

    # Export Mermaid ER diagram for VS Code
    (export_dir / "security_master_schema.md").write_text(generate_mermaid_er_diagram())

    # Export PlantUML ER diagram for VS Code
    (export_dir / "security_master_schema.puml").write_text(
        generate_plantuml_er_diagram(),
    )


if __name__ == "__main__":
    export_schema_files()
