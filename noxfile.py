"""Nox sessions for testing, linting, and security checks."""

import nox

# Python versions to test
PYTHON_VERSIONS = ["3.11", "3.12", "3.13"]

# Source locations
SRC_LOCATIONS = ["src", "tests", "noxfile.py"]


def install(session):
    """Install the project and dev dependencies into the session virtualenv.

    Uses uv as the dependency manager. UV_PROJECT_ENVIRONMENT points uv at the
    nox session virtualenv so installed tools resolve when invoked via
    session.run.

    Args:
        session: Nox session providing install and run helpers.
    """
    session.run_install(
        "uv",
        "sync",
        "--frozen",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
        external=True,
    )


@nox.session(python=PYTHON_VERSIONS)
def tests(session):
    """Run the full test suite (all layers).

    Args:
        session: Nox session providing install and run helpers.
    """
    args = session.posargs or [
        "--cov",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-fail-under=80",
    ]
    install(session)
    session.run("pytest", *args)


# ==========================================
# LAYERED TESTING SESSIONS (Test Pyramid)
# ==========================================


@nox.session(python=PYTHON_VERSIONS)
def unit(session):
    """Run unit tests only (fast development cycle).

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "not component and not contract and not integration and not e2e and not perf "
        "and not chaos and not slow",
        "--cov=src",
        "--cov-branch",
        "--cov-fail-under=80",
        "-v",
        *session.posargs,
    )


@nox.session
def component(session):
    """Run component tests (with mocks).

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "component",
        "--cov=src",
        "--cov-branch",
        "--cov-fail-under=75",
        "-v",
        *session.posargs,
    )


@nox.session
def db_tests(session):
    """Run database tests (PostgreSQL integration).

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "database",
        "--cov=src/security_master/storage",
        "--cov-branch",
        "--cov-fail-under=75",
        "-v",
        *session.posargs,
    )


@nox.session
def classifier_tests(session):
    """Run classification engine tests.

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "classifier",
        "--cov=src/security_master/classifier",
        "--cov-branch",
        "--cov-fail-under=85",
        "-v",
        *session.posargs,
    )


@nox.session
def extractor_tests(session):
    """Run broker file extraction tests.

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "extractor",
        "--cov=src/security_master/extractor",
        "--cov-branch",
        "--cov-fail-under=85",
        "-v",
        *session.posargs,
    )


@nox.session
def fast(session):
    """Fast development loop - exclude slow tests.

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "not slow",
        "--cov=src",
        "--cov-branch",
        "--cov-fail-under=75",  # Slightly lower for fast feedback
        "--maxfail=5",
        "-v",
        *session.posargs,
    )


@nox.session
def security_tests(session):
    """Run security assertion tests.

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "security",
        "-v",
        *session.posargs,
    )


@nox.session
def integration(session):
    """Run integration tests (slower, real services).

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "integration",
        "--cov=src",
        "--cov-branch",
        "-v",
        *session.posargs,
    )


@nox.session
def e2e(session):
    """Run end-to-end tests (full user journeys).

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "e2e",
        "-v",
        "--tb=short",
        *session.posargs,
    )


@nox.session
def perf(session):
    """Run performance and load tests.

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run(
        "pytest",
        "-m",
        "perf or performance",  # Include legacy marker
        "-v",
        "--tb=short",
        "--durations=10",
        *session.posargs,
    )


@nox.session
def lint(session):
    """Run linters.

    Args:
        session: Nox session providing install and run helpers.
    """
    args = session.posargs or SRC_LOCATIONS
    install(session)
    session.run("ruff", "format", "--check", *args)
    session.run("ruff", "check", *args)

    # Markdown linting
    session.run(
        "markdownlint", "--config", ".markdownlint.yml", "**/*.md", external=True
    )

    # YAML linting
    session.run("yamllint", ".", external=True)

    # Docstring quality gates
    session.run("pydoclint", "src/")
    session.run("interrogate", "src/", "--fail-under", "80")
    session.run("interrogate", "scripts/", "--fail-under", "85")


@nox.session
def type_check(session):
    """Run type checking with basedpyright.

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run("basedpyright")


@nox.session
def security(session):
    """Run security checks.

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)

    # Run bandit for code security issues
    session.run("bandit", "-r", "src", "-ll")

    # Audit pip packages
    # Accepted unfixable CVEs documented in docs/known-vulnerabilities.md
    session.run(
        "pip-audit",
        "--ignore-vuln",
        "GHSA-4xh5-x5gv-qwph",  # pip 25.2 -- system pip, outside project control
        "--ignore-vuln",
        "GHSA-6vgw-5pg2-w6jp",  # pip 25.2 -- system pip, outside project control
        "--ignore-vuln",
        "GHSA-58qw-9mgm-455v",  # pip 25.2 -- system pip, outside project control
        "--ignore-vuln",
        "PYSEC-2022-42969",  # py 1.11.0 -- transitive via interrogate, ReDoS not triggered
    )


@nox.session
def format_code(session):
    """Format code.

    Args:
        session: Nox session providing install and run helpers.
    """
    args = session.posargs or SRC_LOCATIONS
    install(session)
    session.run("ruff", "format", *args)
    session.run("ruff", "check", "--fix", *args)


@nox.session
def pre_commit(session):
    """Run pre-commit on all files.

    Args:
        session: Nox session providing install and run helpers.
    """
    install(session)
    session.run("pre-commit", "install", external=True)
    session.run("pre-commit", "install", "--hook-type", "commit-msg", external=True)
    session.run("pre-commit", "run", "--all-files", external=True)
