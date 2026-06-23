"""Unit tests for the ExternalHTTPClient base (retry, rate limit, cache)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from security_master.external.cache import ResponseCache
from security_master.external.errors import ExternalAPIError
from security_master.external.http import ExternalHTTPClient

if TYPE_CHECKING:
    from collections.abc import Callable
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
    client.close()
    cache.close()


def test_retries_then_succeeds(tmp_path: Path) -> None:
    seq = [429, 200]

    def handler(_request: httpx.Request) -> httpx.Response:
        code = seq.pop(0)
        return httpx.Response(code, json={"ok": True})

    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    client = _client(httpx.MockTransport(handler), cache)
    assert client.get_json("https://api.example/x", cache_key="k") == {"ok": True}
    client.close()
    cache.close()


def test_retry_exhaustion_raises_external_api_error(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    client = _client(httpx.MockTransport(handler), cache)
    with pytest.raises(ExternalAPIError):
        client.get_json("https://api.example/x", cache_key="k")
    client.close()
    cache.close()


def test_non_retryable_4xx_raises_immediately(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    client = _client(httpx.MockTransport(handler), cache)
    with pytest.raises(ExternalAPIError):
        client.get_json("https://api.example/x", cache_key="k")
    assert calls["n"] == 1  # 404 is not retried
    client.close()
    cache.close()


def test_transport_error_retried_then_succeeds(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            msg = "boom"
            raise httpx.ConnectError(msg, request=request)
        return httpx.Response(200, json={"ok": True})

    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    client = _client(httpx.MockTransport(handler), cache)
    assert client.get_json("https://api.example/x", cache_key="k") == {"ok": True}
    assert calls["n"] == 2  # first attempt failed, second succeeded
    client.close()
    cache.close()


def test_rate_limiter_sleeps_remaining_interval(tmp_path: Path) -> None:
    # Monotonic returns a controlled, increasing sequence. Each request consumes
    # readings: _respect_rate_limit reads once when _last_call is set, then once
    # to record the call. The first request reads 0.0 (records last_call); the
    # second reads 0.3 (elapsed since 0.0), so it must sleep 1.0 - 0.3 = 0.7.
    times = [0.0, 0.3, 0.3]
    monotonic_calls = {"n": 0}

    def fake_monotonic() -> float:
        value = times[monotonic_calls["n"]]
        monotonic_calls["n"] += 1
        return value

    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    sleep_fn: Callable[[float], None] = fake_sleep
    monotonic_fn: Callable[[], float] = fake_monotonic
    client = ExternalHTTPClient(
        provider="openfigi",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        cache=cache,
        min_interval_seconds=1.0,
        max_retries=3,
        sleep=sleep_fn,
        monotonic=monotonic_fn,
    )
    client.get_json("https://api.example/x", cache_key="k1")
    client.get_json("https://api.example/x", cache_key="k2")
    assert len(slept) == 1
    assert slept[0] == pytest.approx(0.7)
    client.close()
    cache.close()
