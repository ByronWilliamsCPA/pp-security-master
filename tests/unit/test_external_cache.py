"""Unit tests for the on-disk SQLite response cache."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from security_master.external.cache import ResponseCache

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def test_store_then_get_round_trips(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    cache.store("openfigi", "ID_ISIN:US0378331005", '{"figi":"X"}')
    assert cache.get("openfigi", "ID_ISIN:US0378331005") == '{"figi":"X"}'


def test_missing_key_returns_none(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    assert cache.get("openfigi", "absent") is None


def test_expired_entry_returns_none(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    cache.store("sec_edgar", "k", "v", now=0.0)
    assert cache.get("sec_edgar", "k", now=10**12) is None


def test_providers_are_isolated(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    cache.store("openfigi", "k", "a")
    assert cache.get("sec_edgar", "k") is None
