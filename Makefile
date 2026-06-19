.PHONY: help install setup test test-fast test-pre-commit test-pr test-performance test-smoke test-with-timing lint format security clean

# Default target
.DEFAULT_GOAL := help

# Python interpreter
PYTHON := python3.11
UV := uv

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies with uv
	$(UV) sync

setup: install ## Complete development setup
	$(UV) run pre-commit install
	@echo "Development environment ready!"

test: ## Run tests with coverage
	$(UV) run pytest -v --cov=src --cov-report=html --cov-report=term-missing

test-fast: ## Run fast tests for development (< 1 minute)
	$(UV) run pytest tests/unit/ -m "not slow and not performance and not stress" --maxfail=3 --tb=short

test-pre-commit: ## Run pre-commit validation tests (< 2 minutes)
	$(UV) run pytest tests/unit/ tests/integration/ -m "not performance and not stress and not contract" --maxfail=5

test-pr: ## Run PR validation tests (< 5 minutes)
	$(UV) run pytest -m "not performance and not stress" --maxfail=10

test-performance: ## Run performance tests only
	$(UV) run pytest tests/performance/ -m "performance or stress" --tb=line

test-smoke: ## Run smoke tests for basic functionality
	$(UV) run pytest tests/unit/ -m "smoke or fast" --maxfail=1 -x

test-with-timing: ## Run tests with detailed timing analysis
	$(UV) run pytest --durations=20 --tb=short

lint: ## Run linting checks
	$(UV) run ruff format --check .
	$(UV) run ruff check .
	$(UV) run basedpyright
	markdownlint --config .markdownlint.yml **/*.md
	yamllint .
	$(UV) run darglint src/
	$(UV) run interrogate src/ --fail-under 70
	$(UV) run interrogate scripts/ --fail-under 85

format: ## Format code
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

security: ## Run security checks
	$(UV) run pip-audit
	$(UV) run bandit -r src

db-migrate: ## Run database migrations
	$(UV) run alembic upgrade head

db-reset: ## Reset database (development only)
	$(UV) run alembic downgrade base
	$(UV) run alembic upgrade head

pre-commit: ## Run all pre-commit hooks manually
	$(UV) run pre-commit run --all-files

clean: ## Clean build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	rm -rf .coverage htmlcov coverage.xml
	rm -rf .pytest_cache .basedpyright .ruff_cache
	rm -rf dist build *.egg-info