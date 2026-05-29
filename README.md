# Portfolio-Performance Security-Master & Classification

> **📋 Start Here**: [MVP Definition](docs/project/MVP.md) | [Complete Project Plan](docs/project/PROJECT_PLAN.md) | [Architecture Decisions](docs/adr/)

[Portfolio Performance App](https://www.portfolio-performance.info/en/) | [Forum](https://forum.portfolio-performance.info/) | [Manual](https://help.portfolio-performance.info/en/)

---

## Overview

Portfolio Performance (PP) is a powerful open-source desktop portfolio tracker. However, it lacks an enterprise-grade security master for consistent asset classification and analytics. This project provides a dedicated Security-Master Service that:

- **Data Sovereignty**: Complete Portfolio Performance backup generation and restoration
- **Institution Integration**: Import transactions from Wells Fargo, Interactive Brokers, AltoIRA
- **Advanced Classification**: Automated taxonomy assignment via OpenFIGI and pp-portfolio-classifier
- **Cross-Validation**: Compare institution data with Kubera aggregated holdings
- **Database-Centric**: PostgreSQL 17 as authoritative source for all financial data

**Goal:** Transform Portfolio Performance from desktop-only to enterprise-grade with complete data control.

---

## Key Features

### **MVP (8 weeks)**

- **Complete PP Backup Restoration**: Generate/import full Portfolio Performance XML backups
- **Institution Transaction Import**: Wells Fargo CSV and Interactive Brokers Flex Query parsing
- **Basic Security Classification**: Manual taxonomy assignment with database storage
- **CLI Interface**: Command-line tools for all import/export operations

### **Future Releases** *(See [MVP.md](docs/project/MVP.md) for timeline)*

- **Automated Classification**: OpenFIGI API and pp-portfolio-classifier integration
- **Kubera Integration**: Cross-institution validation and variance detection
- **Web UI**: Browser-based classification and account management
- **Advanced Analytics**: SQL-based reporting and data quality monitoring

---

## Quick Start *(Development Phase)*

> **Current Status**: Foundation phase - Core architecture and database models implemented

### Prerequisites

- **PostgreSQL 17**: Running on Unraid server (see [Database Setup](#database-setup) below)
- **Python**: 3.11+ with [uv](https://docs.astral.sh/uv/) installed
- **Network**: Connectivity to PostgreSQL server (default port 5436)

### Development Setup

1. **Clone Repository**: `git clone [repository-url] && cd pp-security-master`
2. **Install Dependencies**: `uv sync`
3. **Install qlty CLI**: `curl https://qlty.sh | bash` (standalone quality runner, not a Python package)
4. **Configure Environment**: Copy `.env.example` to `.env` and configure database connection
5. **Verify Database**: `uv run python tests/test_db_connection.py`
6. **Run Tests**: `uv run pytest -v --cov=src --cov-report=html`
7. **Code Quality**: `uv run nox -s lint` for formatting and linting

> **Note**: Database migrations and CLI commands are currently under development

### Database Setup

#### PostgreSQL 17 on Unraid

1. **Install via Unraid Community Apps**:
   - Search for "PostgreSQL" in Community Applications
   - Select PostgreSQL 17 container
   - Configure environment variables:

     ```env
     POSTGRES_DB=pp_master
     POSTGRES_USER=pp_user
     POSTGRES_PASSWORD=[secure_password]
     ```

   - Map port: `5436:5432` (or preferred external port)
   - Set persistent storage: `/mnt/user/appdata/pp_postgres/data:/var/lib/postgresql/data`

2. **Verify Installation**:

   ```bash
   # Test network connectivity
   nc -zv [unraid-server-ip] 5436
   
   # Test database connection
   uv run python tests/test_db_connection.py
   ```

3. **Troubleshooting**: See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues

> **Detailed Setup**: See [MVP.md](docs/project/MVP.md) for complete MVP scope and [PROJECT_PLAN.md](docs/project/PROJECT_PLAN.md) for infrastructure details.

---

## Repository Structure

```text
pp-security-master/
├─ README.md                        # This file
├─ CLAUDE.md                        # Claude Code configuration
├─ LICENSE                          # MIT License
├─ Makefile                         # Build automation
├─ pyproject.toml                   # Dependencies and project configuration
├─ uv.lock                          # Dependency lock file
├─ noxfile.py                       # Test automation
├─ codecov.yaml                     # Coverage configuration
├─ docs/
│  ├─ adr/                          # Architecture Decision Records
│  ├─ planning/                     # Phase-based development plans
│  └─ project/                      # Project documentation
│     ├─ MVP.md                     # Minimum viable product definition
│     ├─ PROJECT_PLAN.md            # Complete roadmap and technical details
│     ├─ TAXONOMY_GUIDE.md          # Classification standards
│     └─ ...                        # Additional project docs
├─ src/security_master/
│  ├─ storage/
│  │  ├─ models.py                  # Core database models
│  │  ├─ pp_models.py               # Portfolio Performance models
│  │  ├─ transaction_models.py      # Institution transaction models
│  │  ├─ views.py                   # Consolidated export views
│  │  └─ schema_export.py           # Database visualization generators
│  ├─ extractor/                    # Institution-specific parsers
│  ├─ classifier/                   # Classification engines
│  ├─ patch/
│  │  └─ pp_xml_export.py           # PP XML backup generation
│  ├─ cli.py                        # Command-line interface
│  └─ utils.py                      # Shared utilities
├─ tests/                           # Test suite
├─ sample_data/                     # Portfolio Performance and broker samples
├─ schema_exports/                  # Database visualizations (PlantUML, DBML, SQL)
├─ scripts/                         # Setup and utility scripts
├─ sql/                             # Database migrations and schema
└─ pytest_plugins/                  # Custom pytest extensions
```

---

## Documentation

- **📋 [MVP Definition](docs/project/MVP.md)** - Immediate deliverables and success criteria
- **📊 [Complete Project Plan](docs/project/PROJECT_PLAN.md)** - Full roadmap and technical specifications  
- **🏗️ [Architecture Decisions](docs/adr/)** - Technical design rationale
- **📈 [Development Planning](docs/planning/)** - Phase-based execution guides
- **🏷️ [Taxonomy Guide](docs/project/TAXONOMY_GUIDE.md)** - Classification standards (GICS, TRBC, CFI)
- **🗄️ [Database Schema](schema_exports/)** - Visual database diagrams (PlantUML, DBML, SQL)
- **📂 [Sample Data](sample_data/)** - Portfolio Performance and broker examples

---

## License

This project is open-source and available under the MIT License.

---

## References

- [Portfolio Performance App](https://www.portfolio-performance.info/en/)
- [Portfolio Performance Forum](https://forum.portfolio-performance.info/)
- [Portfolio Performance Manual](https://help.portfolio-performance.info/en/)
