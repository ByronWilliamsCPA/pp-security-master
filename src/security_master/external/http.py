"""Synchronous HTTP base: cache read-through, rate limiting, retry/backoff.

Treats provider responses as untrusted data (OWASP LLM01): callers parse and
validate the returned JSON before use. On exhausted retries this raises
``ExternalAPIError`` so callers degrade to the next tier or the manual queue
rather than crash a batch.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, cast

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from security_master.external.errors import ExternalAPIError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from security_master.external.cache import ResponseCache

# Status codes worth retrying: throttling + transient server faults.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class _RetryableHTTPError(RuntimeError):
    """Internal signal that a response is retryable (converted to ExternalAPIError)."""


class ExternalHTTPClient:
    """A per-provider HTTP client with cache, rate limit, and retry/backoff."""

    def __init__(
        self,
        *,
        provider: str,
        http: httpx.Client,
        cache: ResponseCache,
        min_interval_seconds: float,
        max_retries: int,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build the client.

        Args:
            provider: Provider label (cache namespace + error attribution).
            http: An ``httpx.Client`` (inject a MockTransport-backed one in tests).
                The caller owns its lifecycle; close via ``ExternalHTTPClient.close()``.
            cache: Response cache.
            min_interval_seconds: Minimum spacing between live calls.
            max_retries: Retry attempts on 429/5xx/transport errors.
            sleep: Sleep function (injected in tests to avoid real waits).
            monotonic: Monotonic clock (injected in tests).
        """
        self._provider = provider
        self._http = http
        self._cache = cache
        self._min_interval = min_interval_seconds
        self._max_retries = max_retries
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_call: float | None = None

    def close(self) -> None:
        """Close the underlying httpx.Client. Callers own the client lifecycle."""
        self._http.close()

    def get_json(
        self,
        url: str,
        *,
        cache_key: str,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        json_body: object | None = None,
    ) -> object:
        """Fetch and JSON-decode a response, with cache read-through.

        Args:
            url: Target URL.
            cache_key: Provider-scoped cache key.
            method: HTTP method (``"GET"`` or ``"POST"``).
            headers: Optional request headers.
            json_body: Optional JSON request body (for POST).

        Returns:
            The decoded JSON (object). Treat as untrusted data.

        Raises:
            ExternalAPIError: On exhausted retries, a non-retryable HTTP error,
                or a response body that is not valid JSON.
        """  # DOC NOQA: DOC502
        cached = self._cache.get(self._provider, cache_key)
        if cached is not None:
            return self._decode(cached, cache_key, cached=True)
        body = self._fetch_with_retry(url, method, headers, json_body)
        self._cache.store(self._provider, cache_key, body)
        return self._decode(body, cache_key, cached=False)

    def _decode(self, body: str, cache_key: str, *, cached: bool) -> object:
        """JSON-decode a body, converting a non-JSON payload to ExternalAPIError.

        A provider returning a 2xx with a non-JSON body (HTML error page, gateway
        interstitial, truncated payload) would otherwise raise ``JSONDecodeError``,
        which callers do not catch, crashing the batch. Converting it to the
        framework's typed error lets callers degrade gracefully. A poisoned cache
        row is invalidated so it does not keep failing for the full TTL.

        Args:
            body: The raw response or cached body.
            cache_key: Provider-scoped cache key (for invalidation + diagnostics).
            cached: Whether ``body`` came from the cache (drives invalidation).

        Returns:
            The decoded JSON (object). Treat as untrusted data.

        Raises:
            ExternalAPIError: If the body is not valid JSON.
        """
        try:
            return cast("object", json.loads(body))
        except json.JSONDecodeError as exc:
            if cached:
                self._cache.invalidate(self._provider, cache_key)
            msg = f"non-JSON body for {cache_key} (cached={cached}): {exc}"
            raise ExternalAPIError(provider=self._provider, message=msg) from exc

    def _fetch_with_retry(
        self,
        url: str,
        method: str,
        headers: Mapping[str, str] | None,
        json_body: object | None,
    ) -> str:
        """Perform the live request with rate limiting and retry/backoff.

        Args:
            url: Target URL.
            method: HTTP method.
            headers: Optional request headers.
            json_body: Optional JSON request body.

        Returns:
            The raw response text.

        Raises:
            ExternalAPIError: On exhausted retries or a non-retryable HTTP error.
            RuntimeError: If the retry loop exits without setting the body
                (an invariant violation that should never occur in practice).
        """
        body: str | None = None
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
                    body = self._single_attempt(url, method, headers, json_body)
        except (_RetryableHTTPError, httpx.TransportError) as exc:
            msg = f"exhausted retries: {exc}"
            raise ExternalAPIError(provider=self._provider, message=msg) from exc
        # body is always set when the loop exits without exception.
        if body is None:  # pragma: no cover -- invariant: loop never exits unset
            msg = "internal: response body unset after retry loop"
            raise RuntimeError(msg)
        return body

    def _single_attempt(
        self,
        url: str,
        method: str,
        headers: Mapping[str, str] | None,
        json_body: object | None,
    ) -> str:
        """Execute a single HTTP attempt after respecting the rate limit.

        Args:
            url: Target URL.
            method: HTTP method.
            headers: Optional request headers.
            json_body: Optional JSON request body.

        Returns:
            The raw response text on a successful (2xx) response.

        Raises:
            _RetryableHTTPError: When the response status is in
                ``_RETRYABLE_STATUS`` (tenacity will retry).
            ExternalAPIError: When the response is a non-retryable non-2xx
                (3xx/4xx/5xx).
        """
        self._respect_rate_limit()
        response = self._http.request(
            method, url, headers=dict(headers or {}), json=json_body
        )
        if response.status_code in _RETRYABLE_STATUS:
            msg = f"retryable status {response.status_code}"
            raise _RetryableHTTPError(msg)
        # httpx.Client does not follow redirects by default, so a 3xx body is a
        # redirect stub, not JSON. Treat any non-2xx as an error rather than
        # caching an unparseable body.
        if response.status_code >= 300:
            msg = f"status {response.status_code}"
            raise ExternalAPIError(provider=self._provider, message=msg)
        return response.text

    def _respect_rate_limit(self) -> None:
        """Sleep just long enough to honor the per-provider minimum interval."""
        if self._last_call is not None and self._min_interval > 0:
            elapsed = self._monotonic() - self._last_call
            remaining = self._min_interval - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_call = self._monotonic()
