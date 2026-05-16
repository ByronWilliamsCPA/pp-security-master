# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Security-Master Service for Portfolio Performance (PP), providing centralized asset classification and taxonomy management. The system extracts securities from broker files, classifies them using multiple sources (OpenFIGI API, pp-portfolio-classifier), stores them in PostgreSQL 17, and syncs classifications back to Portfolio Performance via XML/JSON feeds.

## Architecture

```text
src/security_master/
├── extractor/        # Broker file parsers (PP XML, IBKR Flex, Wells CSV, AltoIRA PDF)
├── classifier/       # Classification engine (fund.py, equity.py, bond.py)  
├── storage/          # Database layer: models, mappers, validators, views, schema exports
├── patch/            # PP XML/JSON writers for sync back to Portfolio Performance
├── cli.py           # Main CLI interface
└── utils.py         # Shared utilities

Additional directories:
├── docs/adr/         # Architecture Decision Records (ADRs)
├── sql/versions/     # Alembic database migrations
├── schema_exports/   # Database schema exports (DBML, SQL, PlantUML, Markdown)
├── scripts/          # Utility scripts (requirements generation, VS Code hooks)
├── pytest_plugins/  # Custom pytest plugins (coverage hooks)
└── sample_data/      # Test fixtures and sample broker files
```

## Essential Commands

### Development Setup

```bash
# Install dependencies (assumes Poetry is available)
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your PostgreSQL 17 connection details
```

### Database Operations

```bash
# Run Alembic migrations (when implemented)
poetry run alembic upgrade head

# Test database connection
poetry run python -m pytest tests/test_db_connection.py -v
```

### Code Quality

```bash
# Format and lint
poetry run ruff format --check .
poetry run ruff check --fix .
markdownlint --config .markdownlint.yml **/*.md
yamllint .

# Run tests with coverage
poetry run pytest -v --cov=src --cov-report=html --cov-report=term-missing

# Security scanning
poetry run bandit -r src
poetry run pip-audit

# Run pre-commit on all files
poetry run pre-commit run --all-files
# Or via nox (also installs hooks)
poetry run nox -s pre_commit
```

### Task Automation

```bash
# Use Nox for automated testing and linting
poetry run nox                    # Run all tests
poetry run nox -s fast           # Fast development cycle
poetry run nox -s unit           # Unit tests only
poetry run nox -s lint           # Linting and formatting
poetry run nox -s security       # Security checks
poetry run nox -s type_check     # basedpyright type checking

# Specific component tests
poetry run nox -s db_tests        # Database tests
poetry run nox -s classifier_tests # Classification engine tests
poetry run nox -s extractor_tests  # Broker file parser tests

# Make-based automation
make help                         # View available Make targets
```

## Key Dependencies & APIs

- **PostgreSQL 17**: Core persistence layer (configured via Unraid Community Apps)
- **OpenFIGI API**: Equity and bond classification lookups
- **pp-portfolio-classifier**: Open-source fund/ETF analysis
- **Portfolio Performance**: Target application for XML/JSON imports

## Development Notes

- **Database**: Assumes PostgreSQL 17 running on Unraid with connection details in `.env`
- **Classification Chain**: fund → equity → bond → fallback (manual UI classification)
- **Taxonomies**: Supports GICS, TRBC, CFI classification standards
- **Data Retention**: Raw broker files archived to `data/raw/{broker}/{YYYYMMDD}`
- **API Rate Limits**: OpenFIGI requires exponential backoff; implement caching for repeated lookups

## Testing Strategy

### Test Pyramid Architecture

- **Unit tests**: Pure functions/classes (no I/O, no network) - fast development cycle
- **Component tests**: Single bounded context with DB/container mocks
- **Contract tests**: API contract verifications
- **Integration tests**: Cross-service integration with real databases
- **E2E tests**: Full user journeys via CLI
- **Performance tests**: Benchmarks, stress, timing assertions
- **Security tests**: Runtime security assertions

### Coverage Requirements

- **Unit/Component**: >80% coverage target
- **Classification Accuracy**: >95% on listed securities
- **Fast tests**: Exclude slow markers for development cycle

### Pytest Markers

Use markers for selective test execution:

```bash
pytest -m "unit"                # Unit tests only
pytest -m "not slow"           # Fast development cycle
pytest -m "database"           # Database-related tests
pytest -m "classifier"         # Classification engine tests
pytest -m "security"           # Security assertion tests
```

## Security Considerations

- **Secrets Management**: No sensitive data (API keys, tokens) in code or commits
- **Environment Security**: Encrypt `.env` files using GPG before archiving
- **API Security**: Rate limiting and caching for external API calls
- **Input Validation**: Validate all broker file inputs before processing
- **Dependency Security**: Regular `safety check` and `pip-audit` scans
- **Code Security**: Bandit static analysis for security vulnerabilities

## Documentation & Architecture

- **ADRs**: Architecture decisions documented in `docs/adr/`
- **Schema Exports**: Database schema available in multiple formats (`schema_exports/`)
- **Project References**: See `PP_REPOS_REFERENCE.md` for related repositories
- **Taxonomy Guide**: Classification standards documented in `TAXONOMY_GUIDE.md`

## Package Overrides

- **Dependency manager**: `uv` is the canonical dependency manager as of the
  Phase 1 CI modernization (PR #34). `pyproject.toml` uses PEP 621
  `[project.dependencies]` and PEP 735 `[dependency-groups]`; `uv.lock` is
  committed. Use `uv sync --frozen --dev` for setup and `uv run <tool>` to
  invoke dev tooling. Legacy Poetry-only references in `Makefile`,
  `noxfile.py`, and `.pre-commit-config.yaml` are tracked for cleanup in a
  follow-up phase.

## Global Rule References

This project is governed by the following global rules in addition to this file:

- `~/.claude/.claude/rules/python.md` -- linting, type checking, function quality gates
- `~/.claude/.claude/rules/git-workflow.md` -- branch strategy, SHA pinning, pre-commit
- `~/.claude/.claude/rules/pre-commit.md` -- pre-commit hook requirements
- `~/.claude/.claude/rules/testing.md` -- coverage thresholds, test scope
- `~/.claude/.claude/rules/writing.md` -- em-dash ban, AI pattern blacklist
- `~/.claude/.claude/standards/packages.md` -- canonical package choices
