# GEMINI.md

## Project Overview

This project is a Security-Master Service for Portfolio Performance (PP), a desktop portfolio tracker. The service aims to provide an enterprise-grade security master for consistent asset classification and analytics. It is a Python project that uses Poetry for dependency management and a PostgreSQL database as its authoritative data source.

The project provides a command-line interface (CLI) for various operations, including importing and exporting Portfolio Performance data, and it is designed to be extensible for future features like automated security classification and web UI.

**Key Technologies:**

* **Backend:** Python
* **Database:** PostgreSQL 17
* **Dependency Management:** Poetry
* **CLI Framework:** Click
* **Data Validation:** Pydantic
* **Database Toolkit:** SQLAlchemy, Alembic
* **Testing:** Pytest, Nox
* **Linting & Formatting:** Ruff, Black, MyPy

## Building and Running

### Prerequisites

* Python 3.11+
* Poetry
* PostgreSQL 17

### Setup

1. **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd pp-security-master
    ```

2. **Install dependencies:**

    ```bash
    poetry install
    ```

3. **Configure environment:**
    Copy `.env.example` to `.env` and configure the database connection.

4. **Initialize the database:**

    ```bash
    poetry run alembic upgrade head
    ```

### Running the CLI

The main entry point for the CLI is `src/security_master/cli.py`.

* **Import PP Backup:**

    ```bash
    poetry run python -m src.security_master.cli import-xml your_pp_backup.xml
    ```

* **Export Enhanced Backup:**

    ```bash
    poetry run python -m src.security_master.cli export-xml enhanced_backup.xml
    ```

### Makefile Commands

The `Makefile` provides several convenience commands:

* `make install`: Install dependencies.
* `make setup`: Set up the development environment.
* `make test`: Run tests with coverage.
* `make lint`: Run linting checks.
* `make format`: Format code.
* `make security`: Run security checks.
* `make db-migrate`: Run database migrations.
* `make db-reset`: Reset the database.

## Development Conventions

### Testing

The project uses `pytest` for testing and `nox` for test automation. Tests are organized into different layers (unit, component, integration, e2e) and can be run selectively using `pytest` markers.

* Run all tests: `make test`
* Run fast tests: `make test-fast`
* Run tests with timing analysis: `make test-with-timing`

### Linting and Formatting

The project uses `ruff`, `black`, and `mypy` for linting and formatting.

* Run linters: `make lint`
* Format code: `make format`

### Pre-commit Hooks

The project uses `pre-commit` to run checks before each commit. To install the hooks, run `make setup`.

### Database Migrations

Database migrations are managed with `alembic`.

* Run migrations: `make db-migrate`
* Reset database: `make db-reset`
