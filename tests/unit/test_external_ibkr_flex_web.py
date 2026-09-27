"""Unit tests for the IBKR Flex Web Service client (MockTransport, no network)."""

from __future__ import annotations

import stat
from datetime import date
from typing import TYPE_CHECKING

import httpx
import pytest

from security_master.external.ibkr_flex_web import (
    FlexStatementRequest,
    IBKRFlexWebClient,
    IBKRFlexWebError,
    archive_statement,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_TOKEN = "123456789012345678901234"  # noqa: S105  # fake test token
_SEND_URL = (
    "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest"
)
_GET_URL = (
    "https://gdcdyn.interactivebrokers.com/AccountManagement/"
    "FlexWebService/GetStatement"
)
_STATEMENT = (
    '<?xml version="1.0"?><FlexQueryResponse queryName="daily" type="AF">'
    '<FlexStatements count="1"><FlexStatement accountId="U1"/>'
    "</FlexStatements></FlexQueryResponse>"
)


def _success(url: str = _GET_URL) -> str:
    return (
        '<FlexStatementResponse timestamp="27 September, 2026 09:00 AM EDT">'
        "<Status>Success</Status><ReferenceCode>987654321</ReferenceCode>"
        f"<Url>{url}</Url></FlexStatementResponse>"
    )


def _error(code: str, message: str, status: str = "Warn") -> str:
    return (
        '<FlexStatementResponse timestamp="27 September, 2026 09:00 AM EDT">'
        f"<Status>{status}</Status><ErrorCode>{code}</ErrorCode>"
        f"<ErrorMessage>{message}</ErrorMessage></FlexStatementResponse>"
    )


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_polls: int = 5,
    sleeps: list[float] | None = None,
) -> IBKRFlexWebClient:
    recorded = sleeps if sleeps is not None else []
    return IBKRFlexWebClient(
        token=_TOKEN,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        send_request_url=_SEND_URL,
        poll_interval_seconds=1.0,
        max_polls=max_polls,
        max_retries=2,
        sleep=recorded.append,
    )


def _router(
    get_bodies: list[str], send_body: str | None = None
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    """Serve one SendRequest response, then GetStatement bodies in order."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("SendRequest"):
            return httpx.Response(200, text=send_body or _success())
        return httpx.Response(200, text=get_bodies.pop(0))

    return handler, seen


def test_fetch_statement_runs_both_steps() -> None:
    handler, seen = _router([_STATEMENT])
    client = _client(handler)
    assert client.fetch_statement("123456") == _STATEMENT
    send, get = seen
    assert send.url.params["t"] == _TOKEN
    assert send.url.params["q"] == "123456"
    assert send.url.params["v"] == "3"
    assert get.url.host == "gdcdyn.interactivebrokers.com"
    assert get.url.params["q"] == "987654321"
    assert "pp-security-master" in get.headers["User-Agent"]
    client.close()


def test_polls_while_statement_is_generating() -> None:
    sleeps: list[float] = []
    handler, seen = _router(
        [
            _error("1019", "Statement generation in progress."),
            _error("1018", "Too many requests."),
            _STATEMENT,
        ]
    )
    client = _client(handler, sleeps=sleeps)
    assert client.fetch_statement("123456") == _STATEMENT
    assert len(seen) == 4
    assert sleeps == [1.0, 2.0]  # throttled code doubles the wait


def test_send_request_retries_transient_code() -> None:
    bodies = [_error("1009", "Server under heavy load.", "Fail"), _success()]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("SendRequest"):
            return httpx.Response(200, text=bodies.pop(0))
        return httpx.Response(200, text=_STATEMENT)

    assert _client(handler).fetch_statement("123456") == _STATEMENT


@pytest.mark.parametrize("code", ["1012", "1014", "1015"])
def test_fatal_send_request_code_raises_with_code(code: str) -> None:
    handler, _ = _router([], send_body=_error(code, "bad config", "Fail"))
    with pytest.raises(IBKRFlexWebError) as info:
        _client(handler).fetch_statement("123456")
    assert info.value.code == code
    assert "bad config" in str(info.value)


def test_fatal_get_statement_code_raises() -> None:
    handler, _ = _router([_error("1017", "Reference code is invalid.")])
    with pytest.raises(IBKRFlexWebError) as info:
        _client(handler).fetch_statement("123456")
    assert info.value.code == "1017"


def test_poll_exhaustion_raises() -> None:
    handler, _ = _router([_error("1019", "in progress")] * 3)
    with pytest.raises(IBKRFlexWebError, match="not ready after 3 polls"):
        _client(handler, max_polls=3).fetch_statement("123456")


def test_untrusted_statement_host_is_refused_before_sending_token() -> None:
    handler, seen = _router([], send_body=_success("https://evil.example/steal"))
    with pytest.raises(IBKRFlexWebError, match="untrusted"):
        _client(handler).fetch_statement("123456")
    assert len(seen) == 1  # token never sent to the untrusted host


def test_cleartext_statement_url_is_refused() -> None:
    plain = "http://gdcdyn.interactivebrokers.com/GetStatement"
    handler, _ = _router([], send_body=_success(plain))
    with pytest.raises(IBKRFlexWebError, match="untrusted"):
        _client(handler).fetch_statement("123456")


def test_lookalike_host_is_refused() -> None:
    handler, _ = _router(
        [], send_body=_success("https://notinteractivebrokers.com/GetStatement")
    )
    with pytest.raises(IBKRFlexWebError, match="untrusted"):
        _client(handler).fetch_statement("123456")


def test_http_503_is_retried() -> None:
    codes = [503, 200]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("SendRequest"):
            return httpx.Response(codes.pop(0), text=_success())
        return httpx.Response(200, text=_STATEMENT)

    assert _client(handler).fetch_statement("123456") == _STATEMENT


def test_token_never_appears_in_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        detail = f"cannot reach {request.url}"
        raise httpx.ConnectError(detail, request=request)

    with pytest.raises(IBKRFlexWebError) as info:
        _client(handler).fetch_statement("123456")
    assert _TOKEN not in str(info.value)
    assert info.value.__cause__ is None


def test_non_retryable_status_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    with pytest.raises(IBKRFlexWebError, match="HTTP status 403"):
        _client(handler).fetch_statement("123456")


def test_malformed_xml_raises() -> None:
    handler, _ = _router([], send_body="<html><body>oops")
    with pytest.raises(IBKRFlexWebError, match="not well-formed"):
        _client(handler).fetch_statement("123456")


def test_unexpected_root_raises() -> None:
    handler, _ = _router(["<html><body>maintenance</body></html>"])
    with pytest.raises(IBKRFlexWebError, match="unexpected root"):
        _client(handler).fetch_statement("123456")


def test_success_without_reference_code_raises() -> None:
    body = "<FlexStatementResponse><Status>Success</Status></FlexStatementResponse>"
    handler, _ = _router([], send_body=body)
    with pytest.raises(IBKRFlexWebError, match="without ReferenceCode"):
        _client(handler).fetch_statement("123456")


def test_date_override_params_are_sent() -> None:
    handler, seen = _router([_STATEMENT])
    request = FlexStatementRequest(
        from_date=date(2026, 1, 1), to_date=date(2026, 3, 31)
    )
    _client(handler).fetch_statement("123456", request)
    assert seen[0].url.params["fd"] == "20260101"
    assert seen[0].url.params["td"] == "20260331"


def test_period_override_param_is_sent() -> None:
    handler, seen = _router([_STATEMENT])
    _client(handler).fetch_statement("123456", FlexStatementRequest(period_days=7))
    assert seen[0].url.params["p"] == "7"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"from_date": date(2026, 1, 1)},
        {"from_date": date(2026, 1, 1), "to_date": date(2026, 1, 2), "period_days": 3},
        {"period_days": 0},
        {"period_days": 366},
        {"from_date": date(2026, 2, 1), "to_date": date(2026, 1, 1)},
        {"from_date": date(2025, 1, 1), "to_date": date(2026, 1, 2)},
    ],
)
def test_invalid_request_overrides_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011  # message varies per case
        FlexStatementRequest(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("query_id", ["", "abc", "12;rm", "../1"])
def test_non_numeric_query_id_is_rejected(query_id: str) -> None:
    handler, seen = _router([_STATEMENT])
    with pytest.raises(ValueError, match="numeric"):
        _client(handler).fetch_statement(query_id)
    assert seen == []


def test_empty_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="token"):
        IBKRFlexWebClient(token="", http=httpx.Client())


def test_cleartext_send_request_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="https"):
        IBKRFlexWebClient(
            token=_TOKEN, http=httpx.Client(), send_request_url="http://x.test"
        )


def test_archive_statement_writes_owner_only_file(tmp_path: Path) -> None:
    path = archive_statement(_STATEMENT, tmp_path / "ibkr", "123456", "20260927T130000")
    assert path == tmp_path / "ibkr" / "20260927" / "flex_123456_20260927T130000.xml"
    assert path.read_text(encoding="utf-8") == _STATEMENT
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    ("query_id", "stamp"),
    [("../x", "20260927T130000"), ("123", "2026/09/27"), ("123", "../../etc")],
)
def test_archive_statement_rejects_path_segments(
    tmp_path: Path, query_id: str, stamp: str
) -> None:
    with pytest.raises(ValueError):  # noqa: PT011  # message varies per case
        archive_statement(_STATEMENT, tmp_path, query_id, stamp)
