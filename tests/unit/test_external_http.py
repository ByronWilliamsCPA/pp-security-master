"""Unit tests for the ExternalHTTPClient base (retry, rate limit, cache)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from security_master.external.cache import ResponseCache
from security_master.external.errors import ExternalAPIError
from security_master.external.http import ExternalHTTPClient

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _client(transport: httpx.MockTransport, cache: ResponseCache) -> ExternalHTTPClient:
    return ExternalHTTPClient(
        provider="openfigi",
        http=httpx.Client(transport=transport),
        cache=cache,
        min_interval_seconds=0.0,
        max_retries=3,
        sleep=lambda _seconds: None,  # no real sleeping in tests
    )


def test_get_json_returns_payload_and_caches(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"ok": True})

    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    client = _client(httpx.MockTransport(handler), cache)
    first = client.get_json("https://api.example/x", cache_key="k")
    second = client.get_json("https://api.example/x", cache_key="k")
    assert first == {"ok": True}
    assert second == {"ok": True}
    assert calls["n"] == 1  # second served from cache
    cache.close()


def test_retries_then_succeeds(tmp_path: Path) -> None:
    seq = [429, 200]

    def handler(_request: httpx.Request) -> httpx.Response:
        code = seq.pop(0)
        return httpx.Response(code, json={"ok": True})

    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    client = _client(httpx.MockTransport(handler), cache)
    assert client.get_json("https://api.example/x", cache_key="k") == {"ok": True}
    cache.close()


def test_retry_exhaustion_raises_external_api_error(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    client = _client(httpx.MockTransport(handler), cache)
    with pytest.raises(ExternalAPIError):
        client.get_json("https://api.example/x", cache_key="k")
    cache.close()
