"""SEC EDGAR client: resolve a US issuer's SIC code from its ticker symbol.

Free, keyless, US-issuer-only. #ASSUME (external resource): EDGAR fair-access
requires a descriptive User-Agent and <=10 req/s. #VERIFY against EDGAR's
published policy before bulk runs. Responses are untrusted data (OWASP LLM01).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from security_master.external.http import ExternalHTTPClient


class SECEdgarClient:
    """Maps a ticker symbol to the issuer's 4-digit SIC code via EDGAR."""

    def __init__(
        self,
        http: ExternalHTTPClient,
        *,
        tickers_url: str,
        submissions_url: str,
        user_agent: str,
    ) -> None:
        """Build the client.

        Args:
            http: Shared HTTP base (cache + retry + rate limit).
            tickers_url: URL of EDGAR ``company_tickers.json``.
            submissions_url: Base URL of EDGAR submissions (``/CIK##########.json``).
            user_agent: Descriptive User-Agent for EDGAR fair-access.
        """
        self._http = http
        self._tickers_url = tickers_url
        self._submissions_url = submissions_url.rstrip("/")
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}

    def sic_for_symbol(self, symbol: str) -> str | None:
        """Return the issuer's SIC code for ``symbol``, or ``None``.

        Args:
            symbol: Ticker symbol (case-insensitive).

        Returns:
            The 4-digit SIC string, or ``None`` when the symbol or SIC is absent.
        """
        cik = self._cik_for_symbol(symbol)
        if cik is None:
            return None
        payload = self._http.get_json(
            f"{self._submissions_url}/CIK{cik:010d}.json",
            cache_key=f"submissions:{cik:010d}",
            headers=self._headers,
        )
        if not isinstance(payload, dict):
            return None
        sic = cast("dict[str, object]", payload).get("sic")
        if isinstance(sic, str) and sic.isdigit():
            return sic
        if isinstance(sic, int):
            return str(sic)
        return None

    def _cik_for_symbol(self, symbol: str) -> int | None:
        """Resolve a ticker to its CIK via the cached company_tickers map.

        Args:
            symbol: Ticker symbol (case-insensitive).

        Returns:
            The integer CIK, or ``None`` when the symbol is unknown.
        """
        payload = self._http.get_json(
            self._tickers_url, cache_key="company_tickers", headers=self._headers
        )
        if not isinstance(payload, dict):
            return None
        wanted = symbol.upper()
        for entry in cast("dict[str, object]", payload).values():
            if not isinstance(entry, dict):
                continue
            row = cast("dict[str, object]", entry)
            ticker = row.get("ticker")
            cik = row.get("cik_str")
            if (
                isinstance(ticker, str)
                and ticker.upper() == wanted
                and isinstance(cik, int)
            ):
                return cik
        return None
