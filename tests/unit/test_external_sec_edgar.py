"""Unit tests for the SEC EDGAR client (symbol -> CIK -> SIC)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from security_master.external.cache import ResponseCache
from security_master.external.http import ExternalHTTPClient
from security_master.external.sec_edgar import SECEdgarClient

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_TICKERS = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}


def _make(
    handler: httpx.MockTransport | None, tmp_path: Path
) -> tuple[SECEdgarClient, ExternalHTTPClient, ResponseCache]:
    """Build a (SECEdgarClient, base, cache) triple for testing.

    Args:
        handler: A mock transport; pass ``httpx.MockTransport(fn)`` or a raw transport.
        tmp_path: Pytest-provided temporary directory for the cache database.

    Returns:
        A tuple of (SECEdgarClient, ExternalHTTPClient, ResponseCache) that the
        caller is responsible for closing in teardown.
    """
    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    base = ExternalHTTPClient(
        provider="sec_edgar",
        http=httpx.Client(transport=handler),
        cache=cache,
        min_interval_seconds=0.0,
        max_retries=2,
        sleep=lambda _s: None,
    )
    client = SECEdgarClient(
        base,
        tickers_url="https://sec.example/company_tickers.json",
        submissions_url="https://sec.example/submissions",
        user_agent="pp-security-master test@example.com",
    )
    return client, base, cache


def test_sic_for_known_symbol(tmp_path: Path) -> None:
    """Happy path: AAPL resolves to SIC 3571 via CIK lookup."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "company_tickers" in str(request.url):
            return httpx.Response(200, json=_TICKERS)
        return httpx.Response(200, json={"sic": "3571", "sicDescription": "Computers"})

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        result = client.sic_for_symbol("AAPL")
        assert result == "3571"
    finally:
        base.close()
        cache.close()


def test_unknown_symbol_returns_none(tmp_path: Path) -> None:
    """A symbol not in the tickers map returns None without an error."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TICKERS)

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        result = client.sic_for_symbol("ZZZZ")
        assert result is None
    finally:
        base.close()
        cache.close()


def test_user_agent_header_is_sent(tmp_path: Path) -> None:
    """The descriptive User-Agent required by EDGAR fair-access is forwarded."""
    recorded: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request.headers.get("User-Agent", ""))
        if "company_tickers" in str(request.url):
            return httpx.Response(200, json=_TICKERS)
        return httpx.Response(200, json={"sic": "3571"})

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        client.sic_for_symbol("AAPL")
        assert any("test@example.com" in ua for ua in recorded)
    finally:
        base.close()
        cache.close()


def test_malformed_submissions_returns_none(tmp_path: Path) -> None:
    """A submissions payload missing the 'sic' key returns None gracefully."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "company_tickers" in str(request.url):
            return httpx.Response(200, json=_TICKERS)
        return httpx.Response(200, json={"unexpected": True})

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        result = client.sic_for_symbol("AAPL")
        assert result is None
    finally:
        base.close()
        cache.close()
