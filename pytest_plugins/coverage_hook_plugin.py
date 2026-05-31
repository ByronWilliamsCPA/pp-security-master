#!/usr/bin/env python3
"""
Pytest Coverage Hook Plugin for PP Security-Master

Automatically detects when tests are run with coverage and triggers
enhanced coverage report generation. Integrates with VS Code workflow.

Features:
- Auto-detects coverage runs via pytest hooks
- Triggers enhanced report generation after test completion
- Works with CLI and VS Code test execution
- Handles security-master specific test types
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def pytest_configure(config: Any) -> None:
    """Called after command line options have been parsed.

    Args:
        config (Any): Pytest configuration object used to register markers and inspect CLI options.
    """
    # Register custom marker
    config.addinivalue_line(
        "markers",
        "coverage_hook: Mark tests that trigger coverage report generation",
    )

    # Detect coverage enablement
    cov_enabled = False
    try:
        cov_enabled = (
            config.getoption("--cov") is not None
            or config.getoption("--cov-report") is not None
            or any("--cov" in str(arg) for arg in config.invocation_params.args)
        )
    except ValueError:
        # pytest-cov not installed, check command line directly
        cov_enabled = any("--cov" in str(arg) for arg in config.invocation_params.args)

    config._coverage_enabled = cov_enabled


def pytest_sessionfinish(session: Any) -> None:
    """Called after test run completion to trigger coverage reports.

    Args:
        session (Any): Pytest session object providing access to config and collected test counts.
    """
    # Only run if coverage was enabled and tests ran
    if not getattr(session.config, "_coverage_enabled", False):
        return

    # Skip if no tests collected
    if hasattr(session, "testscollected") and session.testscollected == 0:
        return

    try:
        # Find project root
        project_root = Path.cwd()
        while project_root.parent != project_root:
            if (project_root / "pyproject.toml").exists():
                break
            project_root = project_root.parent
        else:
            project_root = Path.cwd()

        # Look for coverage hook script
        hook_script = project_root / "scripts" / "vscode_coverage_hook.py"
        if not hook_script.exists():
            return

        # Execute coverage hook (safe as hook_script is internal and not user-provided)
        result = subprocess.run(
            [sys.executable, str(hook_script)],
            check=False,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,
        )

        if result.returncode == 0 and "✅" in result.stdout:
            logger.info("✅ Coverage reports updated")

    except Exception:
        logger.exception("Coverage hook failed")


def pytest_runtest_makereport(item: Any, call: Any) -> None:
    """Set coverage context based on test type for better tracking.

    Args:
        item (Any): Pytest test item whose file path determines the coverage context label.
        call (Any): Pytest call info object indicating which phase (setup, call, teardown) is executing.
    """
    if (
        call.when == "call"
        and hasattr(item.config, "_coverage_enabled")
        and item.config._coverage_enabled
    ):
        test_path = str(item.fspath)

        # Security-master specific test type classification
        if "/tests/unit/" in test_path:
            context = "unit"
        elif "/tests/integration/" in test_path:
            context = "integration"
        elif "/tests/database/" in test_path:
            context = "database"
        elif "/tests/classifier/" in test_path:
            context = "classifier"
        elif "/tests/extractor/" in test_path:
            context = "extractor"
        elif "/tests/api/" in test_path:
            context = "api"
        elif "/tests/security/" in test_path:
            context = "security"
        elif "/tests/performance/" in test_path:
            context = "performance"
        else:
            context = "other"

        # Set coverage context
        os.environ["COVERAGE_CONTEXT"] = context
