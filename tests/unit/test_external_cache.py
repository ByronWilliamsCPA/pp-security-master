"""Unit tests for the on-disk SQLite response cache."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from security_master.external.cache import ResponseCache

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[ResponseCache]:
    c = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    try:
        yield c
    finally:
        c.close()


def test_store_then_get_round_trips(cache: ResponseCache) -> None:
    cache.store("openfigi", "ID_ISIN:US0378331005", '{"figi":"X"}')
    assert cache.get("openfigi", "ID_ISIN:US0378331005") == '{"figi":"X"}'


def test_missing_key_returns_none(cache: ResponseCache) -> None:
    assert cache.get("openfigi", "absent") is None


def test_expired_entry_returns_none(cache: ResponseCache) -> None:
    cache.store("sec_edgar", "k", "v", now=0.0)
    assert cache.get("sec_edgar", "k", now=10**12) is None


def test_providers_are_isolated(cache: ResponseCache) -> None:
    cache.store("openfigi", "k", "a")
    assert cache.get("sec_edgar", "k") is None


def test_invalidate_removes_entry(cache: ResponseCache) -> None:
    cache.store("openfigi", "k", "v")
    cache.invalidate("openfigi", "k")
    assert cache.get("openfigi", "k") is None


def test_invalidate_absent_key_is_noop(cache: ResponseCache) -> None:
    cache.invalidate("openfigi", "absent")  # must not raise


def test_non_positive_ttl_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ttl_days must be positive"):
        ResponseCache(tmp_path / "bad.sqlite3", ttl_days=0)
