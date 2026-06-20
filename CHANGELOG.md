# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add the PP XML round-trip importer: `patch/pp_xml_import.py` with `parse_client()` (DB-free, unit-testable parser) and `PPXMLImportService` (idempotent persistence by ISIN, account/portfolio uuid, and bookmark label+pattern); the `pp-master` Click CLI with `import-xml` / `export-xml` console entry point; and the Alembic baseline migration (`sql/versions/`, 21 tables) with `alembic.ini` and `sql/env.py`
- Add unique constraints backing importer idempotency: `pp_client_config.config_name` (`uq_pp_client_config_name`) and `pp_bookmarks (label, pattern)` (`uq_pp_bookmark_label_pattern`)
- Add `.pre-commit-config.yaml` with SHA-pinned remote hooks (ruff v0.15.12, detect-secrets v1.5.0, commitizen v4.13.10, yamllint v1.38.0, markdownlint-cli v0.48.0) and local `poetry run` hooks (basedpyright, bandit, darglint, interrogate, no-em-dash pygrep); add `pre_commit` nox session that installs and runs hooks
- Add `.markdownlint.yml` and `.yamllint.yml` project-level linting configuration files
- Add `[tool.commitizen]` configuration block to `pyproject.toml` with `version_provider = "pep621"`
- Add `darglint` and `interrogate` docstring quality gates to `noxfile.py` with per-directory coverage thresholds (`src/` at 70%, `scripts/` at 85%)
- Add `qlty` CLI integration with `.qlty/qlty.toml` configuration covering bandit, ruff, and basedpyright plugins
- Expand Ruff rule set to PyStrict-aligned standard: `ANN`, `ARG`, `ASYNC`, `C4`, `DTZ`, `ERA`, `FBT`, `FLY`, `FURB`, `G`, `ICN`, `INT`, `ISC`, `LOG`, `PERF`, `PGH`, `PIE`, `PL`, `PT`, `PTH`, `PYI`, `Q`, `RET`, `RSE`, `RUF`, `S`, `SIM`, `SLOT`, `T10`, `T20`, `TC`, `TID`, `TRY`, `UP`, `W` rule groups added to `[tool.ruff.lint] select`
- Document accepted pip-audit CVE exceptions in `docs/known-vulnerabilities.md` (GHSA-4xh5-x5gv-qwph (no CVE assigned), GHSA-6vgw-5pg2-w6jp (no CVE assigned), PYSEC-2022-42969 (CVE-2022-42969))

### Changed

- Migrate the project from Poetry to uv with a PEP 621 `[project]` table and PEP 735 `[dependency-groups]`; convert the build backend to `hatchling` with `[tool.hatch.build.targets.wheel]` packages set to `src/security_master`, port all dependencies and dev dependencies, replace `poetry.lock` with `uv.lock`, and switch CI, the Makefile, pre-commit local hooks, `scripts/generate_requirements.sh`, and docs to `uv sync` / `uv run`
- Add `renovate.json` extending `config:recommended` with `enabledManagers` set to `pep621`, `github-actions`, `pre-commit`, and `pip_requirements`
- Replace `mypy` with `basedpyright` in strict mode across `pyproject.toml`, `noxfile.py`, `Makefile`, and `.github/workflows/ci.yml`
- Remove `[tool.mypy]`, `[[tool.mypy.overrides]]`, and `[tool.pydantic-mypy]` config blocks from `pyproject.toml`; add `[tool.basedpyright]` block with `typeCheckingMode = "strict"`
- Replace `datetime.utcnow` (deprecated) with `lambda: datetime.now(UTC).replace(tzinfo=None)` across all model `server_default` fields in `models.py`, `pp_models.py`, and `transaction_models.py`
- Upgrade to SQLAlchemy 2.x `create_mock_engine` in `schema_export.py`; add `checkfirst=False` to `Base.metadata.create_all` so mock engine emits all CREATE TABLE statements
- Tighten type annotations in `mappers.py` (bare `dict` and `list[dict]` to `dict[str, Any]` / `list[dict[str, Any]]`) and `validators.py` (`list[str]` annotations on local variables)
- Switch XML generation in `pp_xml_export.py` to use `defusedxml.ElementTree` for all runtime XML operations; use `TYPE_CHECKING` guard so BasedPyright reads stdlib stubs while the runtime import stays on defusedxml
- Replace `black` formatter with `ruff format` across `noxfile.py`, `Makefile`, and CI workflow
- Replace `safety` vulnerability scanner with `pip-audit` in `noxfile.py`, `Makefile`, and CI workflow
- Fix CI `Run linting` step to call `ruff format --check` instead of removed `black` binary
- Correct `[tool.ruff.lint.isort]` `known-first-party` from `"src"` to `"security_master"` (actual importable package name)
- Correct planning docs: `"ruff"` is not a valid isort profile; keep `profile = "black"` in `[tool.isort]`
- Add `COM812` to `lint.ignore`; ruff format and COM812 conflict by design (ruff's own warning)

### Fixed

- Fix `pp_xml_export.py` building XML through `defusedxml.ElementTree`, which omits the writer API (`Element`/`SubElement`/`tostring`) and raised `AttributeError` at runtime; it now builds with stdlib `ElementTree` and parses untrusted input with `defusedxml`
- Widen `PPSecurityPrice.price_value` from `Integer` to `BigInteger`: PP stores prices as value * 1e8, which overflows a 32-bit integer above ~$21
- Set `viewonly=True` on the two `PPTransactionUnit` navigation relationships to resolve an overlapping-foreign-key mapper error on the soft-polymorphic `transaction_type` key
- Fix the PP XML round-trip integration test skipping only when `DATABASE_URL` is unset, which the autouse conftest fixture always sets; it now probes connectivity and skips when PostgreSQL is unreachable, so CI legs without a database service skip instead of erroring
- Add `# nosemgrep: python.lang.maintainability.return.return-not-in-function` to all SQLAlchemy `mapped_column` lambda defaults in `models.py`, `pp_models.py`, and `transaction_models.py`; semgrep misreads the implicit lambda return as a bare return-not-in-function
- Broaden `except` clause in `PPXMLExportService.validate_export` to catch `defusedxml.DefusedXmlException` in addition to `ET.ParseError`; defusedxml security violations do not inherit from `ParseError`
- Add `try/except defusedxml.DefusedXmlException` around `defused_minidom.parseString()` in `_prettify_xml` to convert XML security violations to `ValueError` instead of propagating unhandled
- Correct `qlty.toml` format and add path exclusions for qlty 0.612.0 compatibility

### Security

- Reassess `docs/known-vulnerabilities.md` (review date 2026-06-19, next due 2026-08-18): confirm `uv run pip-audit` reports no known vulnerabilities after the `msgpack` 1.2.1 / `pydantic-settings` 2.14.2 patches (GHSA-6v7p-g79w-8964, GHSA-4xgf-cpjx-pc3j); refresh the four pip/py advisories, which are no longer surfaced by pip-audit and remain documented as accepted tooling/transitive exceptions
- SHA-pin all GitHub Actions tags across ci.yml, codeql.yml,
  renovate-auto-merge.yml, and scorecard.yml to immutable commit SHAs
  (actions/checkout v4.2.2, actions/setup-python v5.4.0,
  actions/cache v4.2.3, actions/upload-artifact v4.6.2,
  codecov/codecov-action v4.6.0, github/codeql-action v3.29.0,
  step-security/harden-runner v2.12.2, snok/install-poetry v1.4.1,
  fountainhead/action-wait-for-check v1.2.0, ossf/scorecard-action v2.4.3)
