"""IBKR Flex Web Service client: fetch Flex Query statements over HTTPS.

The Flex Web Service returns the same ``FlexQueryResponse`` XML that the
Account Management UI exports, so the output feeds the existing file parsers
(:mod:`security_master.extractor.ibkr_flex`,
:mod:`security_master.extractor.ibkr_positions`) unchanged.

Protocol (version 3), two steps:

1. ``SendRequest?t=<token>&q=<query id>&v=3`` returns a
   ``FlexStatementResponse`` with ``Status`` ``Success`` plus a
   ``ReferenceCode`` and a ``Url`` for step 2, or ``Fail``/``Warn`` with an
   ``ErrorCode``/``ErrorMessage``.
2. ``<Url>?t=<token>&q=<reference code>&v=3`` returns the statement
   (``FlexQueryResponse``), or a ``FlexStatementResponse`` error while the
   statement is still being generated (code 1019) or the token is throttled
   (code 1018). Those transient codes are polled; every other code is fatal.

Responses are untrusted data (OWASP LLM01): they are parsed with defusedxml,
and the step-2 URL IBKR returns is validated before the token is sent to it.
Statements are never cached: they hold account data and change daily.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from security_master.external.errors import ExternalAPIError

if TYPE_CHECKING:
    # stdlib has complete type stubs; defusedxml.ElementTree re-exports the
    # same API at runtime via the safe parser imported in the else branch.
    import xml.etree.ElementTree as ET  # nosec B405  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
    from collections.abc import Callable
    from datetime import date
    from pathlib import Path
else:
    import defusedxml.ElementTree as ET  # noqa: N817  # safe parser at runtime

PROVIDER = "ibkr_flex"

DEFAULT_SEND_REQUEST_URL = (
    "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest"
)

# #ASSUME (external resource): IBKR serves the step-2 GetStatement URL from an
# interactivebrokers.com host (observed: ndcdyn/gdcdyn). #VERIFY: if IBKR moves
# the service to another domain, extend this allowlist rather than dropping
# the check, which keeps the token from being sent to an arbitrary host.
_ALLOWED_HOST_SUFFIX = ".interactivebrokers.com"

# Codes IBKR documents as "please try again shortly". Everything else (expired
# or invalid token 1012/1015, IP restriction 1013, invalid query 1014, ...) is
# fatal and surfaces immediately.
_TRANSIENT_CODES = frozenset(
    {"1001", "1004", "1005", "1006", "1007", "1008", "1009", "1018", "1019", "1021"}
)
_THROTTLED_CODE = "1018"
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_PERIOD_DAYS = 365
_SAFE_QUERY_ID = re.compile(r"^[0-9]{1,20}$")


class IBKRFlexWebError(ExternalAPIError):
    """The Flex Web Service returned an error code or an unusable response.

    Attributes:
        code: IBKR error code (e.g. ``"1012"`` token expired), or ``None`` when
            the failure was not an IBKR-coded error.
    """

    code: str | None

    def __init__(self, message: str, *, code: str | None = None) -> None:
        """Build the error.

        Args:
            message: Human-readable failure detail. Must not contain the token.
            code: Optional IBKR error code.
        """
        self.code = code
        prefix = f"[{code}] " if code else ""
        super().__init__(provider=PROVIDER, message=f"{prefix}{message}")


class _RetryableHTTPError(RuntimeError):
    """Internal signal that an HTTP response is retryable."""


@dataclass(frozen=True)
class _StatementResponse:
    """A parsed ``FlexStatementResponse`` envelope."""

    status: str
    reference_code: str | None
    url: str | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True)
class FlexStatementRequest:
    """Optional date-range override for one SendRequest.

    Leave every field unset to use the period saved on the Flex Query.

    Attributes:
        from_date: Inclusive start date (requires ``to_date``).
        to_date: Inclusive end date (requires ``from_date``).
        period_days: Look-back in days, mutually exclusive with the dates.
    """

    from_date: date | None = None
    to_date: date | None = None
    period_days: int | None = None

    def __post_init__(self) -> None:
        """Validate the override combination.

        Raises:
            ValueError: On a half-open date range, mixed period and dates, a
                reversed range, or a range/period beyond IBKR's 365-day limit.
        """
        has_dates = self.from_date is not None or self.to_date is not None
        if (self.from_date is None) != (self.to_date is None):
            msg = "from_date and to_date must be given together"
            raise ValueError(msg)
        if has_dates and self.period_days is not None:
            msg = "use either period_days or from_date/to_date, not both"
            raise ValueError(msg)
        if self.period_days is not None and not (
            1 <= self.period_days <= _MAX_PERIOD_DAYS
        ):
            msg = f"period_days must be 1..{_MAX_PERIOD_DAYS}"
            raise ValueError(msg)
        if self.from_date is not None and self.to_date is not None:
            span = (self.to_date - self.from_date).days
            if span < 0:
                msg = "from_date must not be after to_date"
                raise ValueError(msg)
            if span > _MAX_PERIOD_DAYS:
                msg = f"date range must be at most {_MAX_PERIOD_DAYS} days"
                raise ValueError(msg)

    def params(self) -> dict[str, str]:
        """Return the SendRequest query parameters for this override.

        Returns:
            The ``p`` or ``fd``/``td`` parameters (empty when unset).
        """
        if self.period_days is not None:
            return {"p": str(self.period_days)}
        if self.from_date is not None and self.to_date is not None:
            return {
                "fd": self.from_date.strftime("%Y%m%d"),
                "td": self.to_date.strftime("%Y%m%d"),
            }
        return {}


class IBKRFlexWebClient:
    """Fetch Flex Query statements from the IBKR Flex Web Service."""

    def __init__(  # injected collaborators keep tests I/O-free
        self,
        *,
        token: str,
        http: httpx.Client,
        send_request_url: str = DEFAULT_SEND_REQUEST_URL,
        poll_interval_seconds: float = 5.0,
        max_polls: int = 20,
        max_retries: int = 4,
        user_agent: str = "pp-security-master",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Build the client.

        Args:
            token: Flex Web Service token. A secret: never logged or echoed.
            http: An ``httpx.Client`` (inject a MockTransport-backed one in
                tests). The caller owns its lifecycle; see :meth:`close`.
            send_request_url: SendRequest endpoint (must be https).
            poll_interval_seconds: Wait between GetStatement polls while IBKR
                is still generating the statement.
            max_polls: GetStatement attempts before giving up.
            max_retries: HTTP-level retries on 429/5xx/transport errors.
            user_agent: User-Agent header sent with every request.
            sleep: Sleep function (injected in tests to avoid real waits).

        Raises:
            ValueError: If the token is empty or the URL is not https.
        """
        if not token:
            msg = "IBKR Flex token is empty; set IBKR_FLEX_TOKEN in .env"
            raise ValueError(msg)
        if not send_request_url.startswith("https://"):
            msg = "send_request_url must be https so the token is never cleartext"
            raise ValueError(msg)
        self._token = token
        self._http = http
        self._send_request_url = send_request_url
        self._poll_interval = poll_interval_seconds
        self._max_polls = max_polls
        self._max_retries = max_retries
        self._headers = {"User-Agent": user_agent}
        self._sleep = sleep

    def close(self) -> None:
        """Close the underlying httpx.Client."""
        self._http.close()

    def fetch_statement(
        self,
        query_id: str,
        request: FlexStatementRequest | None = None,
    ) -> str:
        """Run both protocol steps and return the statement XML.

        Args:
            query_id: Numeric Flex Query ID from Account Management.
            request: Optional date-range override.

        Returns:
            The ``FlexQueryResponse`` XML document as text.

        Raises:
            ValueError: If ``query_id`` is not numeric.
            IBKRFlexWebError: On a fatal IBKR error code, an unexpected
                response, an untrusted step-2 URL, or poll exhaustion.
        """  # DOC NOQA: DOC502, DOC503  # raised by the step helpers
        if not _SAFE_QUERY_ID.match(query_id):
            msg = f"query_id must be numeric, got {query_id!r}"
            raise ValueError(msg)
        extra = request.params() if request else {}
        reference_code, statement_url = self._send_request(query_id, extra)
        return self._poll_statement(reference_code, statement_url)

    def _send_request(self, query_id: str, extra: dict[str, str]) -> tuple[str, str]:
        """Step 1: ask IBKR to generate the statement.

        Args:
            query_id: Flex Query ID.
            extra: Optional date-range parameters.

        Returns:
            The reference code and the step-2 URL.

        Raises:
            IBKRFlexWebError: On an error code or a malformed envelope.
        """  # DOC NOQA: DOC503  # _coded_error() builds an IBKRFlexWebError
        for attempt in range(self._max_polls):
            body = self._get(self._send_request_url, {"q": query_id, **extra})
            envelope = _parse_envelope(body)
            if envelope is None:
                msg = "SendRequest returned an unexpected document"
                raise IBKRFlexWebError(msg)
            if envelope.status == "Success":
                if not envelope.reference_code or not envelope.url:
                    msg = "SendRequest succeeded without ReferenceCode/Url"
                    raise IBKRFlexWebError(msg)
                return envelope.reference_code, _trusted_url(envelope.url)
            if envelope.error_code not in _TRANSIENT_CODES:
                raise _coded_error(envelope)
            if attempt + 1 < self._max_polls:
                self._sleep(self._backoff(envelope.error_code))
        msg = f"SendRequest still busy after {self._max_polls} attempts"
        raise IBKRFlexWebError(msg)

    def _poll_statement(self, reference_code: str, statement_url: str) -> str:
        """Step 2: poll until the statement is ready.

        Args:
            reference_code: Reference code from step 1.
            statement_url: Validated GetStatement URL from step 1.

        Returns:
            The statement XML.

        Raises:
            IBKRFlexWebError: On a fatal code, an unexpected document, or
                poll exhaustion.
        """  # DOC NOQA: DOC503  # _coded_error() builds an IBKRFlexWebError
        for attempt in range(self._max_polls):
            body = self._get(statement_url, {"q": reference_code})
            root_tag = _root_tag(body)
            if root_tag == "FlexQueryResponse":
                return body
            if root_tag != "FlexStatementResponse":
                msg = f"GetStatement returned unexpected root <{root_tag}>"
                raise IBKRFlexWebError(msg)
            envelope = _parse_envelope(body)
            if envelope is None or envelope.error_code not in _TRANSIENT_CODES:
                raise _coded_error(envelope)
            if attempt + 1 < self._max_polls:
                self._sleep(self._backoff(envelope.error_code))
        msg = f"statement not ready after {self._max_polls} polls"
        raise IBKRFlexWebError(msg)

    def _backoff(self, code: str | None) -> float:
        """Return the wait before the next attempt for a transient code.

        Args:
            code: The transient IBKR error code.

        Returns:
            Seconds to wait (doubled when the token is throttled).
        """
        return self._poll_interval * (2 if code == _THROTTLED_CODE else 1)

    def _get(self, url: str, params: dict[str, str]) -> str:
        """GET ``url`` with the token, retrying transient HTTP failures.

        Args:
            url: Target URL.
            params: Query parameters (token and version are added here).

        Returns:
            The response text.

        Raises:
            IBKRFlexWebError: On exhausted retries or a non-retryable status.
                Messages never include the URL, which carries the token.
            RuntimeError: If the retry loop exits without a response (an
                invariant violation that should never occur).
        """
        full = {"v": "3", "t": self._token, **params}
        try:
            for attempt in Retrying(
                retry=retry_if_exception_type(
                    (_RetryableHTTPError, httpx.TransportError)
                ),
                stop=stop_after_attempt(self._max_retries + 1),
                wait=wait_exponential(multiplier=0.5, max=30),
                sleep=self._sleep,
                reraise=True,
            ):
                with attempt:
                    return self._single_attempt(url, full)
        except (_RetryableHTTPError, httpx.TransportError) as exc:
            # #CRITICAL (security): httpx errors can embed the request URL,
            # which carries the token. Report only the exception type.
            # #VERIFY: test_token_never_appears_in_errors.
            msg = f"exhausted retries ({type(exc).__name__})"
            raise IBKRFlexWebError(msg) from None
        msg = "internal: retry loop exited without a response"  # pragma: no cover
        raise RuntimeError(msg)  # pragma: no cover

    def _single_attempt(self, url: str, params: dict[str, str]) -> str:
        """Execute one HTTP GET.

        Args:
            url: Target URL.
            params: Full query parameters, token included.

        Returns:
            The response text on a 2xx response.

        Raises:
            _RetryableHTTPError: On a status worth retrying.
            IBKRFlexWebError: On any other non-2xx status.
        """
        response = self._http.get(url, params=params, headers=self._headers)
        if response.status_code in _RETRYABLE_STATUS:
            msg = f"retryable status {response.status_code}"
            raise _RetryableHTTPError(msg)
        # httpx does not follow redirects by default; treat any non-2xx as an
        # error rather than parsing a redirect stub.
        if response.status_code >= 300:
            msg = f"HTTP status {response.status_code}"
            raise IBKRFlexWebError(msg)
        return response.text


def _root_tag(body: str) -> str:
    """Return the root element tag of an XML body.

    Args:
        body: Response text.

    Returns:
        The root tag.

    Raises:
        IBKRFlexWebError: If the body is not well-formed XML.
    """
    try:
        return ET.fromstring(body).tag
    except ET.ParseError as exc:
        msg = f"response is not well-formed XML: {exc}"
        raise IBKRFlexWebError(msg) from None


def _parse_envelope(body: str) -> _StatementResponse | None:
    """Parse a ``FlexStatementResponse`` envelope.

    Args:
        body: Response text.

    Returns:
        The parsed envelope, or ``None`` if the root is something else.

    Raises:
        IBKRFlexWebError: If the body is not well-formed XML.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        msg = f"response is not well-formed XML: {exc}"
        raise IBKRFlexWebError(msg) from None
    if root.tag != "FlexStatementResponse":
        return None

    def text(tag: str) -> str | None:
        node = root.find(tag)
        value = node.text.strip() if node is not None and node.text else ""
        return value or None

    return _StatementResponse(
        status=text("Status") or "",
        reference_code=text("ReferenceCode"),
        url=text("Url"),
        error_code=text("ErrorCode"),
        error_message=text("ErrorMessage"),
    )


def _coded_error(envelope: _StatementResponse | None) -> IBKRFlexWebError:
    """Build the error for a fatal envelope.

    Args:
        envelope: The parsed envelope, or ``None`` if it could not be parsed.

    Returns:
        An :class:`IBKRFlexWebError` carrying IBKR's code and message.
    """
    if envelope is None:
        return IBKRFlexWebError("GetStatement returned an unparseable envelope")
    detail = envelope.error_message or f"status {envelope.status or 'unknown'}"
    return IBKRFlexWebError(detail, code=envelope.error_code)


def _trusted_url(url: str) -> str:
    """Validate the step-2 URL before the token is sent to it.

    Args:
        url: The ``Url`` element from the SendRequest envelope.

    Returns:
        The URL, unchanged.

    Raises:
        IBKRFlexWebError: If the URL is not https on an IBKR host.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host.endswith(_ALLOWED_HOST_SUFFIX):
        msg = f"refusing untrusted GetStatement host {host!r}"
        raise IBKRFlexWebError(msg)
    return url


def archive_statement(xml: str, raw_dir: Path, query_id: str, stamp: str) -> Path:
    """Write a fetched statement under ``raw_dir/YYYYMMDD/``.

    Keeps the project's raw-file retention convention
    (``data/raw/{broker}/{YYYYMMDD}``) so an API fetch leaves the same audit
    trail as a manual export.

    Args:
        xml: Statement XML.
        raw_dir: Broker raw directory (e.g. ``data/raw/ibkr``).
        query_id: Flex Query ID (part of the file name).
        stamp: ``YYYYMMDDTHHMMSS`` timestamp; the date part names the folder.

    Returns:
        The written file path.

    Raises:
        ValueError: If ``query_id`` is not numeric or ``stamp`` is malformed
            (both reach the file name, so they must not carry path segments).
    """
    if not _SAFE_QUERY_ID.match(query_id):
        msg = f"query_id must be numeric, got {query_id!r}"
        raise ValueError(msg)
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}", stamp):
        msg = f"stamp must be YYYYMMDDTHHMMSS, got {stamp!r}"
        raise ValueError(msg)
    day_dir = raw_dir / stamp[:8]
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"flex_{query_id}_{stamp}.xml"
    # #CRITICAL (security): statements carry account numbers and balances.
    # Owner-only permissions; data/ is gitignored.
    # #VERIFY: test_archive_statement_writes_owner_only_file.
    path.write_text(xml, encoding="utf-8")
    path.chmod(0o600)
    return path
