# Security Master Service - Minimum Viable Product (MVP)

> **Re-baselined 2026-06-19:** The MVP scope below predates the current build state. As of 2026-06-19 the ingestion half (broker parsers, classification, XML import, round-trip, CLI) is not yet implemented. The active phase sequence, starting with a PP XML round-trip walking skeleton, now lives in `ROADMAP_2026-06-19.md` (in `docs/project/`). Use that file for current sequencing.

**Version**: 1.1  
**Date**: 2025-08-23  
**Target Release**: Phase 0-3 (10.5 weeks) - *Updated for project planning refinements*  

> **Related Documents**: [Complete Project Plan](PROJECT_PLAN.md) | [Architecture Decisions](docs/adr/) | [Setup Guide](README.md)

---

## Executive Summary

The MVP delivers **core data sovereignty** for Portfolio Performance users by enabling complete backup generation and institution transaction import. This establishes the foundation for advanced classification and validation features in subsequent releases.

**MVP Value Proposition**: Transform Portfolio Performance from a desktop-only tool into a database-backed system with enterprise-grade backup capabilities and institution data integration.

**Architecture Foundation**: Built on [transaction-centric architecture](docs/adr/ADR-001-transaction-centric-architecture.md) with [complete PP backup restoration capability](docs/adr/ADR-002-portfolio-performance-backup-restoration.md) and [four-tier data sourcing hierarchy](docs/adr/ADR-003-securities-master-data-sourcing-hierarchy.md).

---

## MVP Scope

### ✅ **Included in MVP**

#### **1. Core Database Infrastructure**

- PostgreSQL 17 setup on Unraid with basic security
- Core tables: `securities_master`, `pp_*` tables for complete PP backup capability
- Alembic migrations for schema management

#### **2. Portfolio Performance Integration**

- **Import**: Parse complete PP XML backup files into database
- **Export**: Generate valid PP XML backup files from database
- **Round-trip Validation**: PP XML → Database → PP XML produces identical results
- **Basic CLI**: `pp-master import-xml` and `pp-master export-xml` commands

#### **3. Institution Transaction Import (Core)**

- **Wells Fargo CSV** parser with account hierarchy
- **Interactive Brokers Flex Query** basic transaction import
- **Transaction Consolidation**: Basic consolidated views for PP export
- **Import Tracking**: Batch processing with basic error handling

#### **4. Basic Security Classification**

- **Tier 1 Integration**: Leverage Portfolio Performance native quote feeds and community data
- **Manual Entry**: CLI/database commands for security classification with audit trails
- **PP Securities Import**: Import securities from PP CSV export with existing classifications
- **Basic Taxonomy**: Core GICS Level 1 classification capability with confidence scoring
- **BlackRock Holdings (Basic)**: Simple PDF parsing for iShares ETF quarterly holdings to support asset allocation analysis

### ❌ **Excluded from MVP** *(Future Releases)*

- **Advanced Classification Engine** (OpenFIGI API, pp-portfolio-classifier integration)
- **Advanced BlackRock Processing** (complex PDF layouts, automated quarterly parsing)
- **Kubera Integration** and cross-institution validation
- **Web UI** (FastAPI + React interface)
- **AltoIRA PDF Parsing** (complex OCR workflow)
- **Advanced Analytics** and reporting dashboards
- **User Management** and authentication
- **Real-time Sync** and scheduling

---

## MVP User Stories

### **Primary User**: Portfolio Performance Power User

#### **Story 1: Data Sovereignty**
>
> **As a** PP user,  
> **I want** to generate complete PP backup files from a database,  
> **So that** I have full control over my financial data and can restore my PP instance at any time.

**Acceptance Criteria:**

- Import my existing PP XML backup into the database
- Generate a new PP XML backup from the database
- Restore the generated backup in Portfolio Performance successfully
- All transactions, securities, and account structures preserved

#### **Story 2: Institution Data Import**
>
> **As a** PP user with Wells Fargo and Interactive Brokers accounts,  
> **I want** to import my broker data directly into the database,  
> **So that** I can consolidate my financial data without manual PP entry.

**Acceptance Criteria:**

- Import Wells Fargo CSV exports with account mapping
- Import Interactive Brokers Flex Query data with basic transaction types
- View consolidated transactions in database
- Export consolidated data as PP-compatible XML

#### **Story 3: Basic Classification**
>
> **As a** PP user,  
> **I want** to classify my securities with basic taxonomy,  
> **So that** I can organize my portfolio beyond PP's limited categories.

**Acceptance Criteria:**

- Import securities from PP CSV export
- Manually assign basic GICS classifications via CLI
- Export enhanced PP XML with classification data
- View classified securities in restored PP instance

#### **Story 4: Asset Allocation Data Foundation**
>
> **As a** PP user with iShares ETFs,  
> **I want** to import BlackRock quarterly holdings data,  
> **So that** I can perform detailed asset allocation analysis that commercial tools don't provide.

**Acceptance Criteria:**

- Parse BlackRock quarterly holdings PDF for iShares ETFs
- Store underlying asset allocations in database with sector/geographic breakdowns
- Export enhanced PP XML with detailed ETF composition data
- Enable custom asset allocation views beyond standard GICS classifications

---

## MVP Success Criteria

### **Functional Requirements**

1. **Round-trip Validation**: PP XML import/export produces identical results (100% accuracy)
2. **Institution Import**: Successfully import 500+ transactions from Wells Fargo CSV and IBKR Flex Query with data validation
3. **Basic Classification**: Classify 100+ securities with GICS Level 1 categories  
4. **Asset Allocation Foundation**: Parse BlackRock holdings for 5+ iShares ETFs with sector/geographic breakdowns
5. **Performance**: Generate PP backup for 1,000 transactions within 10 seconds with baseline performance metrics established

### **Non-Functional Requirements**

1. **Reliability**: Database operations succeed 99.9% of the time with comprehensive error recovery procedures
2. **Data Integrity**: Zero data loss during import/export operations with automated rollback capabilities  
3. **Monitoring**: Basic health checks and structured logging for production readiness
4. **Documentation**: Complete setup guide enabling new user onboarding in ≤45 minutes
5. **Maintainability**: All code passes linting (Ruff, Black, MyPy) with 80%+ test coverage

### **Business Success Criteria**

1. **User Adoption**: Successfully deploy for 1-3 power users
2. **Feedback Quality**: Collect actionable feedback for advanced features
3. **Technical Validation**: Prove database-centric architecture viability
4. **Foundation Readiness**: MVP can support advanced features in Phase 2

---

## MVP Architecture

### **Technology Stack**

- **Database**: PostgreSQL 17 (Unraid Community Apps)
- **Backend**: Python 3.11+ with SQLAlchemy 2.0
- **CLI**: Click framework for command-line interface
- **Testing**: Pytest with coverage reporting
- **Deployment**: Poetry for dependency management

### **Core Components** *(Minimal Implementation)*

```text
src/security_master/
├── cli.py                  # Basic CLI commands
├── storage/
│   ├── models.py           # Core database models (see PROJECT_PLAN.md §4.1)
│   ├── pp_models.py        # PP-specific models (see ADR-002)  
│   ├── validators.py       # Data quality validation (NEW)
│   └── database.py         # Database connection with pooling
├── external/               # External repository integration (NEW)
│   ├── pp-portfolio-classifier/  # Git subtree integration
│   └── ppxml2db/          # Git subtree integration
├── extractor/
│   ├── pp_xml_parser.py    # PP XML import
│   ├── wells_fargo.py      # Wells Fargo CSV parser (see PROJECT_PLAN.md §4.3)
│   ├── ibkr_flex.py        # Basic IBKR Flex parser (see PROJECT_PLAN.md §4.3)
│   └── blackrock_pdf.py    # Basic BlackRock holdings PDF parser
├── monitoring/             # Basic monitoring framework (NEW)
│   ├── health_checks.py    # Health check endpoints
│   └── logging_config.py   # Structured logging setup
└── patch/
    └── pp_xml_export.py    # PP XML export (see PROJECT_PLAN.md §4.6)
```

> **Technical Details**: See [PROJECT_PLAN.md](PROJECT_PLAN.md) for complete component specifications, infrastructure setup, and advanced features.

### **MVP Data Flow**

```text
Broker Files → Institution Tables → Consolidated Views → PP XML Export
Wells CSV/IBKR XML → DB Storage → Basic Consolidation → Restorable PP Backup
```

---

## MVP Timeline & Milestones

| Week | Milestone | Deliverable | Success Metric |
|------|-----------|-------------|----------------|
| 1-2  | **Database Foundation & Performance** | PostgreSQL setup, core models, migrations, performance benchmarks | Database schema validated, baseline metrics established |
| 3-4  | **External Repository Integration** | pp-portfolio-classifier & ppxml2db as git subtrees, connection pooling | External libraries functional, performance tested |
| 5-6.5| **Institution Transaction Import** | Wells Fargo + IBKR parsers, consolidated views, data validation | 500+ transactions imported, validation framework operational *(PHASE GATE 1)* |
| 7-8  | **PP XML Integration** | Complete PP XML import/export, round-trip testing | Round-trip validation passes, automated testing |
| 9-10.5| **MVP Validation & Documentation** | End-to-end testing, performance validation, documentation | All success criteria met, production readiness validated |

**Total MVP Duration**: 10.5 weeks (updated from 8 weeks to account for project planning improvements)

### **Phase Gate 1 (Week 6.5): MVP Go/No-Go Decision**

- All institution parsers operational with data validation  
- Database performance meets baseline requirements
- Data quality framework operational
- Decision point: Continue to advanced features or refine MVP foundation

---

## MVP Limitations & Future Work

### **Known MVP Limitations**

- **Manual Classification**: No automated GICS/TRBC assignment
- **Basic Institution Support**: Limited transaction types from Wells Fargo/IBKR
- **CLI Only**: No web interface for user interactions
- **Single User**: No multi-user or authentication support
- **No Real-time Sync**: Batch processing only

### **Planned Future Releases** *(See [PROJECT_PLAN.md](PROJECT_PLAN.md) for complete roadmap)*

#### **Release 2.0: Advanced Classification** *(+6 weeks)*

- **Tier 2**: pp-portfolio-classifier integration for automated fund/ETF analysis
- **Tier 3**: OpenFIGI API integration for comprehensive equity/bond classification (see PROJECT_PLAN.md §4.4)
- **Enhanced Confidence Scoring**: Multi-tier data validation and quality metrics
- Kubera integration for data validation (see ADR-001)

#### **Release 3.0: User Experience** *(+4 weeks)*

- Web UI for security classification and account management (see PROJECT_PLAN.md §4.5)
- AltoIRA PDF parsing with manual review workflow (see PROJECT_PLAN.md §4.3)
- Advanced analytics and reporting dashboards

#### **Release 4.0: Enterprise Features** *(+3 weeks)*

- Multi-user support with authentication
- Automated scheduling and real-time sync
- Advanced data quality monitoring and alerting (see PROJECT_PLAN.md §5)

---

## MVP Risk Assessment

### **High-Risk Items** *(Mitigation Required)*

1. **PP XML Complexity**: Complex cross-references and UUID management
   - *Mitigation*: Extensive testing with real PP backup files
2. **Institution Data Variability**: Different CSV/XML formats over time
   - *Mitigation*: Flexible parsers with fallback error handling
3. **Database Performance**: Large transaction datasets
   - *Mitigation*: Strategic indexing and query optimization

### **Medium-Risk Items** *(Monitor)*

1. **User Adoption**: Learning curve for CLI-based workflow
2. **Data Quality**: Manual classification accuracy
3. **Documentation**: Comprehensive setup instructions

---

## MVP Definition of Done

### **Technical Completion**

- [ ] All MVP user stories pass acceptance criteria
- [ ] Round-trip validation achieves 100% accuracy
- [ ] Performance benchmarks met (1K transactions <10s with baseline metrics established)
- [ ] Data validation framework operational with error recovery procedures
- [ ] Basic monitoring and health checks implemented
- [ ] Code quality standards met (linting, typing, testing)
- [ ] External repository integration functional (pp-portfolio-classifier, ppxml2db)
- [ ] Documentation complete (setup, usage, troubleshooting, error recovery)

### **User Validation**  

- [ ] Successfully deployed for 1-3 power users
- [ ] User feedback collected and categorized
- [ ] No critical bugs reported in 2-week validation period
- [ ] Users can complete end-to-end workflow independently
- [ ] Phase Gate 1 criteria met (institution parsers, database performance, data quality)

### **Business Readiness**

- [ ] MVP demonstrates clear value proposition  
- [ ] Foundation ready for Release 2.0 advanced features
- [ ] Technical architecture validated for scale with performance testing
- [ ] Production monitoring foundation established
- [ ] Go/no-go decision data available for continued investment

---

**Ready for MVP Development?** This focused scope provides immediate value while establishing the foundation for comprehensive Portfolio Performance data management.
