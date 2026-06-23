"""Unit tests for the OpenFIGI client."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from security_master.external.cache import ResponseCache
from security_master.external.http import ExternalHTTPClient
from security_master.external.openfigi import OpenFIGIClient

if TYPE_CHECKING:
    from pathlib import Path


pytestmark = [pytest.mark.unit]


def _make(
    transport: httpx.MockTransport, tmp_path: Path
) -> tuple[OpenFIGIClient, ExternalHTTPClient, ResponseCache]:
    cache = ResponseCache(tmp_path / "c.sqlite3", ttl_days=30)
    base = ExternalHTTPClient(
        provider="openfigi",
        http=httpx.Client(transport=transport),
        cache=cache,
        min_interval_seconds=0.0,
        max_retries=2,
        sleep=lambda _s: None,
    )
    client = OpenFIGIClient(base, base_url="https://api.example/mapping", api_key=None)
    return client, base, cache


def test_maps_isin_to_equity_record(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "data": [
                        {
                            "figi": "BBG",
                            "name": "APPLE INC",
                            "securityType": "Common Stock",
                            "marketSector": "Equity",
                        }
                    ]
                }
            ],
        )

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        rec = client.map_identifier(isin="US0378331005")
        assert rec is not None
        assert rec.figi == "BBG"
        assert rec.is_equity() is True
    finally:
        base.close()
        cache.close()


def test_no_match_returns_none(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"warning": "No identifier found."}],
        )

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        result = client.map_identifier(isin="US0000000000")
        assert result is None
    finally:
        base.close()
        cache.close()


def test_non_equity_market_sector_is_not_equity(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "data": [
                        {
                            "figi": "G",
                            "name": "US TREASURY",
                            "securityType": "Note",
                            "marketSector": "Govt",
                        }
                    ]
                }
            ],
        )

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        rec = client.map_identifier(isin="US912828ZL7")
        assert rec is not None
        assert rec.is_equity() is False
    finally:
        base.close()
        cache.close()


def test_requires_an_identifier(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])  # should never be reached

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        with pytest.raises(ValueError, match="isin or symbol"):
            client.map_identifier(isin=None, symbol=None)
    finally:
        base.close()
        cache.close()


def test_maps_ticker_when_isin_not_provided(tmp_path: Path) -> None:
    import json as _json

    captured: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(_json.loads(request.content))
        return httpx.Response(
            200,
            json=[
                {
                    "data": [
                        {
                            "figi": "BBG",
                            "name": "APPLE INC",
                            "securityType": "Common Stock",
                            "marketSector": "Equity",
                        }
                    ]
                }
            ],
        )

    client, base, cache = _make(httpx.MockTransport(handler), tmp_path)
    try:
        rec = client.map_identifier(symbol="AAPL")
        assert rec is not None
        assert rec.figi == "BBG"
        assert len(captured) == 1
        assert captured[0] == [{"idType": "TICKER", "idValue": "AAPL"}]
    finally:
        base.close()
        cache.close()
