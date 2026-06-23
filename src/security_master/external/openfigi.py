"""OpenFIGI v3 mapping client: identity + instrument-type only.

OpenFIGI returns no GICS/SIC/NAICS; it confirms an instrument exists, its market
sector, and its security type. Responses are untrusted data (OWASP LLM01): every
field is read defensively and validated before use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from security_master.external.http import ExternalHTTPClient

_EQUITY_MARKET_SECTOR = "Equity"


class OpenFIGIRecord(BaseModel):
    """A validated subset of one OpenFIGI mapping match.

    Attributes:
        model_config: Pydantic model configuration (extra fields ignored).
        figi: The Financial Instrument Global Identifier.
        name: Security name.
        security_type: OpenFIGI ``securityType``.
        market_sector: OpenFIGI ``marketSector`` (coarse Bloomberg bucket).
    """

    model_config = ConfigDict(extra="ignore")

    figi: str
    name: str = ""
    security_type: str = ""
    market_sector: str = ""

    def is_equity(self) -> bool:
        """Return whether OpenFIGI classifies this as an equity instrument.

        Returns:
            ``True`` when ``marketSector`` is ``"Equity"``.
        """
        return self.market_sector == _EQUITY_MARKET_SECTOR


class OpenFIGIClient:
    """Maps an ISIN or ticker to a validated :class:`OpenFIGIRecord`."""

    def __init__(
        self, http: ExternalHTTPClient, *, base_url: str, api_key: str | None
    ) -> None:
        """Build the client.

        Args:
            http: Shared HTTP base (cache + retry + rate limit).
            base_url: OpenFIGI v3 mapping endpoint.
            api_key: Optional OpenFIGI API key (anonymous tier when ``None``).
        """
        self._http = http
        self._base_url = base_url
        self._api_key = api_key

    def map_identifier(
        self, *, isin: str | None = None, symbol: str | None = None
    ) -> OpenFIGIRecord | None:
        """Map an ISIN (preferred) or symbol to the first matching record.

        Args:
            isin: The security ISIN, if known.
            symbol: The security ticker, used when no ISIN is available.

        Returns:
            The first :class:`OpenFIGIRecord`, or ``None`` when nothing matches.

        Raises:
            ValueError: If neither ``isin`` nor ``symbol`` is provided.
        """
        if isin:
            id_type, id_value = "ID_ISIN", isin
        elif symbol:
            id_type, id_value = "TICKER", symbol
        else:
            msg = "map_identifier requires an isin or symbol"
            raise ValueError(msg)

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-OPENFIGI-APIKEY"] = self._api_key
        payload = self._http.get_json(
            self._base_url,
            cache_key=f"{id_type}:{id_value}",
            method="POST",
            headers=headers,
            json_body=[{"idType": id_type, "idValue": id_value}],
        )
        return self._first_record(payload)

    @staticmethod
    def _first_record(payload: object) -> OpenFIGIRecord | None:
        """Extract the first match from an OpenFIGI mapping response.

        Args:
            payload: The decoded mapping response (untrusted).

        Returns:
            The first validated record, or ``None`` if absent or malformed.
        """
        if not isinstance(payload, list) or not payload:
            return None
        items = cast("list[object]", payload)
        first: object = items[0]
        if not isinstance(first, dict):
            return None
        first_dict = cast("dict[str, object]", first)
        data: object = first_dict.get("data")
        if not isinstance(data, list) or not data:
            return None
        data_items = cast("list[object]", data)
        match: object = data_items[0]
        if not isinstance(match, dict):
            return None
        m = cast("dict[str, object]", match)
        figi = m.get("figi")
        if not isinstance(figi, str):
            return None
        return OpenFIGIRecord(
            figi=figi,
            name=_str_or_empty(m.get("name")),
            security_type=_str_or_empty(m.get("securityType")),
            market_sector=_str_or_empty(m.get("marketSector")),
        )


def _str_or_empty(value: object) -> str:
    """Return ``value`` if it is a string, else an empty string.

    Args:
        value: A candidate field value.

    Returns:
        The string, or ``""``.
    """
    return value if isinstance(value, str) else ""
