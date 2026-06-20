# **Portfolio-Performance Security-Master & Classification Project Plan**

> **Re-baselined 2026-06-19:** This document describes the original enterprise-scope vision (14 phases, 30 weeks). Actual implementation is roughly 15 to 20 percent complete: the storage schema layer and a one-directional PP XML exporter exist; extraction, classification, XML import, round-trip, migrations, and the CLI are not yet implemented (the CLI exists only as an entrypoint stub). The active, reality-aligned roadmap and phase sequence now live in `ROADMAP_2026-06-19.md` (this directory). Treat that file as the source of truth for what is being built next; this plan remains the long-range vision.

## (Complete roadmap and technical implementation details)

> **Quick Links**: [MVP Definition](MVP.md) | [Architecture Decisions](docs/adr/) | [Database Schema](schema_exports/) | [Sample Data](sample_data/)

---

## Executive Summary

> **For MVP scope and immediate deliverables, see [MVP.md](MVP.md)**

Portfolio Performance (PP) is an elegant desktop tracker yet ships without an enterprise-grade security master. As positions arrive from Interactive Brokers, Wells Fargo, AltoIRA, and PDFs, inconsistencies creep in: ticker aliases, duplicate ISINs, and missing sector tags hamper analytics. This project erects a dedicated "Security-Master Service" that:

* centralises identifiers and taxonomies in a PostgreSQL 17 instance running natively on your Unraid server,
* re-uses the open-source **pp-portfolio-classifier** to dissect funds and ETFs,
* calls the free OpenFIGI API for equities and bonds,
* offers a browser/CLI for manually classifying private placements, and
* round-trips classifications back into PP via XML or JSON feeds.

The result? New users can **clone → install Postgres via Community Apps → import broker files → run one command** and enjoy a fully-tagged portfolio in under an hour.

---

## 1 Background & Problem Statement

PP recognises only a flat asset-class list and expects users to tag every security by hand. That model collapses when you manage hundreds of ISINs across multiple custodians and want to slice by GICS, TRBC, or CFI. Manual upkeep breeds drift; “APPL” sneaks in beside “AAPL”; a bond masquerades as cash. Meanwhile, Unraid already hosts your home lab and offers a maintained PostgreSQL template, so the infrastructure backbone is one click away. Without a disciplined master you are, metaphorically, building a skyscraper on shifting sand.

### Bullet List

* **Symptoms:** inconsistent tags, duplicate tickers, slow analytics.
* **Root cause:** PP lacks an authoritative master and automated ingestion.
* **Opportunity:** leverage Unraid’s persistent Postgres and open APIs to automate >90 % of tagging.

---

## 2 Project Goals & Success Criteria

### 2.1 Core Classification Goals

1. **Accuracy** – ≥ 95 % of listed securities auto-classified to GICS Level 2 or TRBC Level 3.
2. **Completeness** – 100 % of positions present in PP exist in the master within 24 h of import.
3. **Reproducibility** – every taxonomy snapshot and API payload stored with hash & timestamp.

### 2.2 Portfolio Performance Integration Goals

1. **Complete Backup Restoration** – Generate valid PP XML backup files from database that fully restore PP instances.
2. **Bidirectional Synchronization** – Import complete PP XML backups and export complete restoration files.
3. **Transaction Preservation** – Maintain complete transaction history with all fees, taxes, and cross-references.
4. **Data Sovereignty** – Database becomes authoritative source for all Portfolio Performance data.

### 2.3 Operational Goals  

1. **On-boarding** – a *Quick-Start* doc enabling a new analyst to stand the platform up on Windows/macOS in ≤ 30 min.
2. **Zero Data Loss** – Round-trip validation: PP XML → Database → PP XML produces identical results.
3. **Performance** – Generate complete backup for 10,000+ transactions within 30 seconds.

---

## 3 Solution Overview

**Architecture Decision**: Transaction-centric, four-category data model with institution-specific import tables and consolidated Portfolio Performance export views. (See [ADR-001](docs/adr/ADR-001-transaction-centric-architecture.md))

**External Repository Integration**: Tiered integration strategy for leveraging Portfolio Performance ecosystem libraries while maintaining security and maintainability. (See [ADR-008](docs/adr/ADR-008-external-repository-integration-strategy.md))

**Institutional Analytics**: Implementation of institutional-grade quantitative portfolio analytics to bridge the gap between retail and institutional portfolio management capabilities. (See [ADR-009](docs/adr/ADR-009-institutional-grade-quantitative-portfolio-analytics.md))

### 3.1 Four-Category Data Architecture

1. **Security Master** - Centralized reference data with complete taxonomy classification
2. **Transactions** - Institution-specific transaction imports (Wells Fargo, IBKR, AltoIRA, Kubera)  
3. **Holdings** - Derived position calculations from transaction history
4. **Prices** - Market data and valuation feeds

### 3.2 Data Flow Pattern

```text
Raw Institution Data → Institution Tables → Consolidated Views → PP Export
     (Transactions)    (Per-Institution)    (Group/Account)    (XML/JSON)
```

#### Institution-Specific Benefits

* **Wells Fargo:** CSV import with account hierarchy preservation
* **Interactive Brokers:** Flex Query XML with complex derivatives support  
* **AltoIRA:** PDF parsing with manual review workflow
* **Kubera:** Real-time aggregated data for validation and reconciliation

### 3.3 Core Components

* **Extraction:** Institution-specific parsers maintaining data lineage
* **Classification:** Enhanced taxonomy with data quality scoring  
* **Persistence:** PostgreSQL 17 with institution tables + consolidated views
* **Synchronisation:** Portfolio Performance XML/JSON export from consolidated views

---

## 4 Component Design

### 4.1 Transaction-Centric Database Schema

#### Institution Transaction Tables

* `transactions_wells_fargo` - Wells Fargo CSV imports with account hierarchy
* `transactions_interactive_brokers` - IBKR Flex Query data with derivatives support
* `transactions_altoira` - AltoIRA PDF parsing with manual review workflow  
* `transactions_kubera` - Kubera aggregated data for validation

#### Consolidated Views

* `v_holdings_by_group` - Portfolio Performance group-level positions
* `v_holdings_by_account` - Portfolio Performance account-level positions
* `v_transactions_for_pp_export` - Normalized transactions for PP XML/JSON export
* `v_data_quality_summary` - Cross-institution validation and quality metrics

#### Security Master Table

* Complete taxonomy classification (GICS, TRBC, CFI, BRX-Plus custom)
* Data quality scoring (0.00-1.00) based on completeness
* OpenFIGI API integration for equity/bond classification
* Portfolio Performance securities import compatibility

#### Key Benefits

* **Data Lineage:** Complete traceability from institution source to PP export
* **Quality Validation:** Institution-to-institution comparison for accuracy
* **Flexible Granularity:** Import at vendor detail, export at PP requirements  
* **Audit Trail:** All transactions preserved with import batch tracking

### 4.2 Taxonomy Loader

Loads GICS CSV, TRBC CSV, ISO 10962 CFI list. Files live under `data/` with SHA-256 fingerprint; loader auto-versions snapshots (vYY.MM.DD). ([help.portfolio-performance.info][3], [lseg.com][4])

### 4.3 Institution-Specific Extraction Layer

#### Wells Fargo Adapter

* CSV parser with account type detection (IRA, Taxable, etc.)
* Investment objective and sub-account mapping
* Transaction type normalization (Buy/Sell/Dividend/Transfer)

#### Interactive Brokers Adapter

* Flex Query XML parsing with trade ID preservation
* Complex derivatives support (options, futures, strikes, expiry)
* IBKR fee breakdown (commission, regulatory, exchange fees)

#### AltoIRA Adapter

* PDF statement parsing with OCR confidence scoring
* Manual review workflow for low-confidence extractions
* Page-level transaction extraction with audit trail

#### Kubera Adapter

* JSON API integration with sheet/section hierarchy preservation  
* Real-time aggregated data for cross-validation
* Provider connection tracking (Finicity, Yodlee, manual)

#### Common Features

* Import batch tracking with rollback capabilities
* Raw file archival to `data/raw/{institution}/{YYYYMMDD}`
* Data quality scoring and error flagging

### 4.4 Classification Engine

**Four-Tier Data Sourcing Hierarchy** (See [ADR-003](docs/adr/ADR-003-securities-master-data-sourcing-hierarchy.md))

#### **Tier 1: Portfolio Performance Native Sources**

* **PP Quote Feeds**: Yahoo Finance and PP built-in providers for basic security data
* **PP Community Data**: User-contributed classifications and community templates
* **PP Historical Data**: Existing price feeds and security metadata

#### **Tier 2: External Library Integration** (See [ADR-008](docs/adr/ADR-008-external-repository-integration-strategy.md))

* **Automated Fund Analysis**: [pp-portfolio-classifier](https://github.com/fizban99/pp-portfolio-classifier) for mutual fund and ETF holdings breakdown
* **XML Data Integration**: [ppxml2db](https://github.com/pfalcon/ppxml2db) for PP XML ⇄ database round-trip conversion
* **Holdings-Based Classification**: Underlying asset analysis for complex instruments
* **Open Source Integration**: Zero-cost, community-maintained classification engines

#### **Tier 3: Custom API Development**

* **OpenFIGI API**: Bloomberg-maintained equity and bond classification ([openfigi.com][6])
* **Alpha Vantage API**: Fundamental data and company profiles
* **Regulatory Sources**: SEC EDGAR, ESMA FIRDS for comprehensive coverage

#### **Tier 4: Manual Processes**

* **Web UI Classification**: Browser-based interface for unmatched securities
* **Expert Review**: Manual override and private investment classification
* **Quality Assurance**: Systematic review with audit trails

*Classification Logic*: Cascade through tiers with confidence scoring and cost optimization

### 4.5 Institutional-Grade Analytics Engine

**Advanced Quantitative Analytics** (See [ADR-009](docs/adr/ADR-009-institutional-grade-quantitative-portfolio-analytics.md))

#### **Core Analytics Capabilities**

* **Risk-Adjusted Metrics**: Sharpe Ratio, Treynor Ratio, Information Ratio, Alpha, Beta, Tracking Error
* **Portfolio Optimization**: Mean-variance optimization, risk parity, factor-based optimization
* **Risk Analysis**: Monte Carlo simulation, VaR/CVaR, stress testing, scenario analysis
* **Performance Attribution**: Factor decomposition, sector/security attribution, style analysis

#### **External Analytics Integration**

* **Monte Carlo Simulation**: [pyscripter/XLRisk](https://github.com/pyscripter/XLRisk) for comprehensive risk modeling
* **Portfolio Optimization**: [lequant40/portfolio_allocation_js](https://github.com/lequant40/portfolio_allocation_js) for modern portfolio theory algorithms
* **Risk Metrics**: [mayest/Portfolio-Performance](https://github.com/mayest/Portfolio-Performance) for Excel-based analytics integration

#### **Analytics Architecture**

```text
src/analytics/
├── core/              # Risk-adjusted performance metrics
├── adapters/          # External library integration adapters  
├── models/            # Factor models and correlation analysis
└── reports/           # Institutional reporting and visualization
```

### 4.6 Architecture Enhancements

#### Event Sourcing & CQRS Implementation

* **Event Sourcing**: Complete transaction audit trail with event sourcing pattern for regulatory compliance
* **CQRS Pattern**: Separate read/write models for classification operations vs. export generation
* **Async Processing**: Asynchronous classification pipeline for large dataset processing (10k+ transactions)
* **Feature Flags**: Graduated rollout system for new classification sources and institution parsers

#### Technical Implementation Patterns

* Async task queues for classification processing with progress tracking
* Event-driven architecture for real-time data quality monitoring
* Feature toggle framework for safe deployment of classification engines
* Distributed caching layer for API rate limit management

### 4.7 Manual Override UI

FastAPI + React micro-frontend served on `https://unraid.lan:5050`; JWT auth bound to Cloudflare Zero-Trust. Fields: security search, taxonomy dropdowns, save button. Changes persist instantly to Postgres and flag PP for next patch run.

### 4.8 Portfolio-Performance Complete Integration

**🎯 Full Backup Restoration Capability** (See [ADR-002](docs/adr/ADR-002-portfolio-performance-backup-restoration.md))

#### PP-Specific Database Tables

* `pp_client_config` - PP version and base currency configuration
* `pp_accounts` / `pp_portfolios` - Account and portfolio hierarchies with UUIDs
* `pp_account_transactions` / `pp_portfolio_transactions` - Complete transaction history
* `pp_transaction_units` - Granular fee and tax breakdown
* `pp_security_prices` - Complete daily price history
* `pp_settings` / `pp_bookmarks` - User configuration and preferences

**XML Export Engine:** (`pp_xml_export.py`)

* Generate complete, restorable PP XML backup files from database
* Preserve all UUIDs, cross-references, and transaction relationships  
* Include complete price history and user settings
* Support multiple PP versions and configurations

#### Bidirectional Synchronization

1. **Import Capability** - Parse complete PP XML backups into database
2. **Export Capability** - Generate valid PP XML backups from database  
3. **Round-trip Validation** - PP XML → Database → PP XML produces identical results

#### Integration Benefits

* **Data Sovereignty**: Database becomes authoritative source for PP data
* **Disaster Recovery**: Generate PP backups from database at any time
* **Advanced Analytics**: SQL access to complete portfolio history
* **Multi-Instance Support**: Manage multiple PP configurations from single database

---

## 5 Infrastructure & Operations

### 5.1 PostgreSQL 17 on Unraid

Install **PostgreSQL 17 – Official** via Apps; map `/var/lib/postgresql/data` to `/mnt/user/appdata/pp_postgres/data`; set `POSTGRES_USER=pp_user`, `POSTGRES_DB=pp_master`, strong password, and `TZ=America/Los_Angeles`. Auto-start and activate “Update notifications”. ([unraid.net][8], [forums.unraid.net][9])

#### Bullet List

* Backups: CA-Backup nightly at 02:00, WAL-quiesce script for consistency.
* Monitoring: optional pgAdmin container on port 5051.

### 5.2 Service Deployment Options

* **Local Dev:** `poetry install && uvicorn security_master.api:app`
* **Production:** Unraid Apps template (Phase 5) pointing to the same data share; environment file provides `DATABASE_URL`.

---

## 6 Repository & Code Organisation

```text
portfolio-master/
├─ data/                    # taxonomies, raw archives
├─ docs/
│  └─ adr/                  # Architecture Decision Records
├─ sample_data/             # Sample CSV/JSON files for development
├─ schema_exports/          # Generated database visualizations
├─ src/security_master/
│  ├─ extractor/            # Institution-specific parsers
│  ├─ classifier/           # fund.py, equity.py, bond.py
│  ├─ analytics/            # Institutional-grade quantitative analytics
│  │  ├─ core/              # Risk-adjusted performance metrics
│  │  ├─ adapters/          # External library integration adapters
│  │  ├─ models/            # Factor models and correlation analysis
│  │  └─ reports/           # Institutional reporting
│  ├─ external/             # Forked external repositories (subtrees)
│  │  ├─ pp-portfolio-classifier/  # Classification engine
│  │  └─ ppxml2db/          # PP XML ⇄ database conversion
│  ├─ storage/              
│  │  ├─ models.py          # Core tables (securities_master, kubera_*)
│  │  ├─ transaction_models.py  # Institution transaction tables
│  │  ├─ views.py           # Consolidated PP export views
│  │  ├─ validators.py      # Data quality validation
│  │  ├─ mappers.py         # Institution mapping utilities
│  │  └─ schema_export.py   # PlantUML/Mermaid/DBML generators
│  ├─ patch/                # pp_writer.py
│  ├─ cli.py
│  └─ utils.py
├─ tests/
├─ pyproject.toml
├─ noxfile.py
└─ .env.example
```

### Bullet List

* Ruff + Black + MyPy enforced in Nox; CycloneDX SBOM published on CI.

---

## 7 DevOps & CI/CD

GitHub Actions workflows: **lint-test**, **security-scan** (Bandit, Trivy), **snyk-oss**, **build-container**, **integration-pp**. Matrix Python 3.9-3.12. Secrets in SOPS-encrypted files; Cosign signs images, Renovate bumps dependencies automatically.

---

## 8 Documentation Set

| Document                 | Purpose          | Sections                                                                                  |
| ------------------------ | ---------------- | ----------------------------------------------------------------------------------------- |
| `README.md`              | 3-min overview   | prerequisites, single-line install, demo GIF                                              |
| `quickstart.rst`         | end-to-end guide | Postgres install via Apps, PP install, taxonomy enable, broker import, first classify run |
| `operations.rst`         | ops handbook     | backup/restore, upgrades, monitoring, disaster recovery                                   |
| `adr/0005-db-backend.md` | decision record  | rationale for Postgres on Unraid                                                          |

---

## 9 Risk Management & Mitigations

### Bullet List

* **Vendor HTML shifts** break fund scraper → unit tests with live URLs & fallback to cached X-Ray JSON.
* **API throttling** from OpenFIGI → local result cache + back-off logic.
* **User mis-tags private assets** → dual-review queue before commit.
* **Disk failure** on Unraid cache → CA-Backup plus off-site rclone to Backblaze.

---

## 10 Project Timeline & Milestones

| Phase                        | Duration | Key Deliverables                                    | Exit Criteria & Phase Gates      |
| ---------------------------- | -------- | --------------------------------------------------- | -------------------------------- |
| 0 Design & Repo Bootstrap    | 1 wk     | architecture doc, repo skeleton, ADRs               | sign-off by CAO                  |
| 1 Postgres Provisioning & Performance | 1 wk | CA-Postgres 17 running, Alembic baseline, performance benchmarks (10k+ transactions), connection pooling | `psql` connects, baseline metrics established, performance framework operational |
| 2 External Repository Integration | 2.5 wk | Fork pp-portfolio-classifier & ppxml2db, integrate as subtrees, connection pooling | External libraries functional, performance tested |
| 3 Institution Transaction Import | 3.5 wk | Institution-specific parsers, consolidated views, comprehensive data validation framework | **PHASE GATE 1**: Wells Fargo/IBKR/AltoIRA imports, data quality validation operational |
| 4 PP XML Integration         | 3 wk     | Complete PP XML import/export capability, round-trip testing | Round-trip validation passes, automated testing |
| 5 Taxonomy & Classification  | 3.5 wk   | Tier 1-4 integration, caching layer, API circuit breakers, manual override procedures | >90% fund/ETF classification rate, API resilience, fallback strategy operational |
| 6 Institutional Analytics   | 4.5 wk   | Risk metrics, portfolio optimization, Monte Carlo, async processing | **PHASE GATE 2**: Core analytics suite functional, performance benchmarks |
| 7 Data Migration & Legacy Support | 2.5 wk | Migration tools, data quality validation, rollback procedures | Migration strategy validated, rollback tested |
| 8 Kubera Comparison Engine   | 2 wk     | Cross-institution validation, variance detection    | Data quality dashboards          |
| 9 Manual UI & Auth           | 2.5 wk   | FastAPI + React, JWT via Cloudflare, user roles    | UX demo accepted, security tested |
| 9.5 Integration Testing      | 2 wk     | Cross-system integration, API contract validation, data lineage testing | **PHASE GATE 3**: All institution → PP export flows validated |
| 9.6 System Performance Testing | 2 wk   | Database performance benchmarks (10k+ transactions), load testing, concurrent user validation | Performance requirements met under production load |
| 10 Advanced Analytics Reports | 2 wk    | Institutional reporting, analytics API endpoints    | Analytics API <2s p95 response   |
| 11 Production Monitoring     | 1.5 wk   | Observability framework, health checks, alerting   | Production monitoring operational |
| 12 CI/CD & Security Hardening | 1.5 wk  | GA workflows, Cosign, SCA scans, penetration testing of authentication and data access | zero high-sev vulns, security penetration testing completed |
| 13 Docs & Handoff            | 1.5 wk   | README, quick-start, ADRs, operation guides, runbooks | new analyst setup ≤30 min        |

**Total: 30 weeks** (+25% buffer for complexity and integration challenges)

### Phase Gate Requirements

**Phase Gate 1 (After Phase 3):** Go/No-Go decision based on:

* All institution parsers operational with data validation
* Database performance meets baseline requirements
* Data quality framework operational

**Phase Gate 2 (After Phase 6):** Go/No-Go decision based on:

* Analytics engine performance validated
* API integration resilience demonstrated  
* Database schema stable and optimized

**Phase Gate 3 (After Phase 9.6):** Go/No-Go decision based on:

* End-to-end integration fully validated across all institution → PP export flows
* Performance requirements met under production load (10k+ transaction datasets)
* Security penetration testing completed successfully
* Complete rollback procedures tested and validated

### Must-Have Before Production

#### Critical Production Requirements

* Automated integration test suite covering all institution → PP export flows
* Performance benchmarks validated for datasets matching target user scale (10k+ transactions)
* Complete rollback procedures implemented for all destructive operations
* Security penetration testing completed for authentication and data access paths
* Data validation framework operational with comprehensive quality checks
* Classification fallback strategy implemented with manual override procedures

### Parallel Execution Strategy

* Phase 2 & early Phase 3 can overlap (external integration while starting parsers)
* Phase 4 & 5 can partially overlap (PP integration while building classification)
* Phase 7 can start during Phase 6 (migration planning while analytics development)
* Phase 11 can start during Phase 9.5 (monitoring setup during integration testing)

---

## Next Steps

1. Install PostgreSQL 17 via Unraid Apps, map data share, and create `pp_user/pp_master`.
2. **Execute ADR-008**: Fork **pp-portfolio-classifier** and **ppxml2db**, integrate as git subtrees.
3. **Execute ADR-010**: Implement performance testing framework with baseline metrics collection.
4. **Execute ADR-011**: Set up production monitoring and observability foundation.
5. Add `.env.example`, generate Alembic baseline, and commit under `feat(db-schema)`.
6. Implement data validation framework and error recovery procedures.
7. Draft `quickstart.rst` with screenshots of Unraid template and PP taxonomy view.
8. Create comprehensive data migration procedures and rollback capabilities.
9. Schedule Phase Gate reviews and establish acceptance criteria for go/no-go decisions.
10. **Execute ADR-009**: Set up analytics module structure with external library adapters (Phase 6).

---

## References

* Unraid Community-Apps PostgreSQL 17 template documentation. ([unraid.net][8])
* Forum thread on upgrading Postgres containers on Unraid. ([forums.unraid.net][9])
* PP Manual – Taxonomies view and custom classifications. ([help.portfolio-performance.info][3])
* PP Manual – CSV & PDF import wizard. ([help.portfolio-performance.info][10])
* PP Manual – Classifying assets guide. ([help.portfolio-performance.info][11])
* CA-Backup plugin reference for appdata snapshots. ([forums.unraid.net][2])
* OpenFIGI API documentation & rate-limit FAQ. ([openfigi.com][1], [openfigi.com][6])
* Morningstar Portfolio X-Ray overview. ([morningstar.com][5])
* LSEG TRBC sector hierarchy overview. ([lseg.com][4])
* PP source XML example illustrating `<assetClass>` tags. ([github.com][12])

---

**Ready to roll?** Once Postgres is humming on Unraid you can pull the first broker file, run `pp-master classify`, and watch Portfolio Performance snap into focus: no manual tagging, no hidden YAML, just clean, verifiable data.

[1]: https://www.openfigi.com/api/documentation?utm_source=chatgpt.com "Documentation | OpenFIGI"
[2]: https://forums.unraid.net/topic/137710-plugin-appdatabackup/?utm_source=chatgpt.com "[Plugin] Appdata.Backup - Plugin Support - Forums - Unraid"
[3]: https://help.portfolio-performance.info/en/reference/view/taxonomies/?utm_source=chatgpt.com "Taxonomies - Portfolio Performance Manual"
[4]: https://www.lseg.com/en/data-analytics/financial-data/indices/global-equity-indices?utm_source=chatgpt.com "Global Equity Indices - LSEG"
[5]: https://www.morningstar.com/help-center/portfolio/xray?utm_source=chatgpt.com "X-Ray | Help - Morningstar"
[6]: https://www.openfigi.com/about/faq?utm_source=chatgpt.com "FAQ - OpenFIGI"
[8]: https://unraid.net/community/apps/p54?srsltid=AfmBOoqPgRGM-1JGaXIzi8OTXWNWfS0UPFcw4OBQzb53lUCxJJ6aXxRF&token=-keAFncVqtwn2BPR3rxp3bD-ryfAD8jk&utm_source=chatgpt.com "Community Apps - Unraid"
[9]: https://forums.unraid.net/topic/190277-upgrading-postgresql-v15-v17-for-teslamate/?utm_source=chatgpt.com "Upgrading PostgreSQL v15 ->v17 (for TeslaMate) - Forums - Unraid"
[10]: https://help.portfolio-performance.info/en/reference/file/import/csv-import/?utm_source=chatgpt.com "Importing a CSV file - Portfolio Performance Manual"
[11]: https://help.portfolio-performance.info/en/getting-started/classify-assets/?utm_source=chatgpt.com "Classifying your assets - Portfolio Performance Manual"
[12]: https://github.com/buchen/portfolio/blob/master/name.abuchen.portfolio.ui/src/name/abuchen/portfolio/ui/parts/kommer.xml?utm_source=chatgpt.com "kommer.xml - GitHub"
