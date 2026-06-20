# Repository Guidelines

## Project Structure & Module Organization

- `src/security_master/`: service code
  - `storage/`: DB models, views, schema export
  - `extractor/`: broker/import parsers
  - `classifier/`: taxonomy engines
  - `patch/pp_xml_export.py`: PP XML generation
  - `cli.py`, `utils.py`: CLI entrypoints/utilities
- `tests/`: pytest suite (unit/integration, markers)
- `docs/adr/`: Architecture Decision Records
- `sample_data/`, `schema_exports/`: examples and diagrams
- `scripts/`: tooling (coverage hook, helpers)

## Build, Test, and Development Commands

- Install: `poetry install` or `make install`
- Setup dev: `make setup` (installs pre-commit)
- Test (coverage): `make test`
- Fast tests: `make test-fast`
- Lint/typecheck: `make lint`
- Format: `make format`
- Security scan: `make security`
- DB migrate/reset: `make db-migrate` / `make db-reset`
- Nox alternatives: `nox -s tests|unit|lint|security`
- Run CLI example: `poetry run python -m src.security_master.cli import-xml path/to/backup.xml`

## Coding Style & Naming Conventions

- Python 3.11–3.12; format with Black (88 cols) and isort (black profile).
- Lint with Ruff; type-check with MyPy (strict settings for `src`).
- Naming: `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE` constants.
- Follow `.editorconfig` (4-space Python; LF; final newline). Avoid `print`; prefer `structlog`/`rich`.

## Testing Guidelines

- Framework: `pytest` with markers (`unit`, `component`, `integration`, `e2e`, `perf`, `security`, `smoke`).
- Naming: files `test_*.py`, classes `Test*`, functions `test_*`.
- Coverage: target ≥80% (`pyproject` fail_under=80, Codecov patch target 85%). Run: `make test`.
- Use markers to scope runs (e.g., `pytest -m "not slow"`).

## Commit & Pull Request Guidelines

- History is minimal; adopt Conventional Commits (e.g., `feat:`, `fix:`, `docs:`).
- PRs: clear description, linked issue, test coverage for changes, update docs, screenshots/logs for CLI output if relevant.
- Before pushing: `make format && make lint && make test` should pass.

## Security & Configuration Tips

- Never commit secrets; copy `.env.example` to `.env` and fill locally.
- Validate with `make security` (Safety, Bandit) and `pre-commit` hooks.
- PostgreSQL 17 expected; apply migrations via `alembic` (`make db-migrate`).
- Large samples/exports live in `sample_data/` and `schema_exports/` (excluded from coverage).
