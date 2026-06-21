"""Unit tests for :mod:`security_master.storage.views`.

The view DDL is PostgreSQL-specific (``STRING_AGG``, ``BOOL_OR``, CTEs), so the
``create_all_views``/``drop_all_views`` helpers are exercised against a mock
engine to cover their control flow without running PostgreSQL. Importing the
module also covers the module-level ``text(...)`` view definitions.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from security_master.storage import views

pytestmark = pytest.mark.storage


def test_view_definitions_are_present() -> None:
    """All four consolidation view statements are defined at import time."""
    for statement in (
        views.VIEW_HOLDINGS_BY_GROUP,
        views.VIEW_HOLDINGS_BY_ACCOUNT,
        views.VIEW_TRANSACTIONS_FOR_PP_EXPORT,
        views.VIEW_DATA_QUALITY_SUMMARY,
    ):
        assert "CREATE OR REPLACE VIEW" in str(statement)


def test_create_all_views_executes_each_statement_and_commits() -> None:
    """create_all_views runs all four view statements then commits once."""
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value

    views.create_all_views(engine)

    assert conn.execute.call_count == 4
    conn.commit.assert_called_once()


def test_drop_all_views_executes_each_drop_and_commits() -> None:
    """drop_all_views issues a DROP for each view then commits once."""
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value

    views.drop_all_views(engine)

    assert conn.execute.call_count == 4
    conn.commit.assert_called_once()
