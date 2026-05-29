# Contributing to pp-security-master

Thank you for your interest in contributing! We welcome all contributions that
help improve our code, documentation, and community processes.

## How to Contribute

1. **Review the Code of Conduct**
   Ensure your interactions align with our [Code of Conduct](CODE_OF_CONDUCT.md).

2. **Find or File an Issue**
   - Search existing issues to avoid duplication.
   - To report a bug, use the [bug template](.github/ISSUE_TEMPLATE/bug.yml).
   - To propose a feature, use the [feature template](.github/ISSUE_TEMPLATE/feature.yml).

3. **Fork and Clone**

   ```bash
   git clone https://github.com/williaby/pp-security-master.git
   cd pp-security-master
   git remote add upstream https://github.com/williaby/pp-security-master.git
   ```

## Pull Request Guidelines

- **Branch from main**

  ```bash
  git checkout -b feature/<short-description>
  ```

- **Link your issue**
  Include "Closes #ISSUE-NUMBER" in your PR description to auto-close the issue.

- **Commit messages**
  Use the format:

  ```text
  <type>(<scope>): <subject>
  ```

  where `<type>` is one of `feat`, `fix`, `docs`, `style`, `refactor`, `test`,
  or `chore`.
  Example: `feat(classifier): add GICS sector fallback lookup`

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) and Google-style docstrings.
- Run `uv run ruff format .` for formatting.
- Run `uv run ruff check --fix .` and `uv run basedpyright` for lint and type checks.
- Imports must be grouped: standard library, third-party, local application.

## Local Development Setup

1. **Install dependencies** (requires [uv](https://docs.astral.sh/uv/)):

   ```bash
   uv sync
   ```

2. **Set up environment**:

   ```bash
   cp .env.example .env
   # Edit .env with your PostgreSQL 17 connection details
   ```

3. **Run tests**:

   ```bash
   uv run nox -s unit     # Unit tests only (fast)
   uv run nox             # Full test suite
   ```

4. **Run linting and type checking**:

   ```bash
   uv run ruff format .
   uv run ruff check --fix .
   uv run basedpyright
   ```

5. **Run security checks**:

   ```bash
   uv run nox -s security
   ```

Last updated: 2026-04-20
