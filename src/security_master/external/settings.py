"""Typed configuration for the external-API framework (read from .env only)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# #ASSUME (external resource): the OpenFIGI free tier (anonymous or keyed) is
# sufficient for current batch sizes. #VERIFY against a real import volume and
# document the paid-tier threshold if batches exceed it.
_DEFAULT_OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
_DEFAULT_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_DEFAULT_SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions"


class ExternalAPISettings(BaseSettings):
    """External-API settings loaded from environment / ``.env``.

    Attributes:
        model_config: Pydantic-settings configuration (env prefix, env file, extras).
        openfigi_api_key: Optional OpenFIGI key; absent runs the anonymous tier.
        openfigi_base_url: OpenFIGI v3 mapping endpoint.
        sec_user_agent: Descriptive User-Agent for SEC EDGAR fair-access policy.
        sec_tickers_url: SEC company_tickers.json URL (ticker -> CIK).
        sec_submissions_url: SEC submissions base URL (CIK -> SIC).
        cache_path: On-disk SQLite response-cache file.
        cache_ttl_days: Cache entry lifetime in days.
        min_request_interval_seconds: Minimum spacing between calls per provider.
        max_retries: Retry attempts on 429/5xx/transport errors.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        extra="ignore",
    )

    # #CRITICAL (security): the key is a secret. It lives in .env only and must
    # never be committed. #VERIFY detect-secrets stays clean.
    openfigi_api_key: str | None = None
    openfigi_base_url: str = _DEFAULT_OPENFIGI_URL
    # #ASSUME (external resource): SEC EDGAR fair-access requires a descriptive
    # User-Agent and <=10 req/s. #VERIFY against EDGAR's published access policy.
    sec_user_agent: str = "pp-security-master (set SEC_USER_AGENT in .env)"
    sec_tickers_url: str = _DEFAULT_SEC_TICKERS_URL
    sec_submissions_url: str = _DEFAULT_SEC_SUBMISSIONS_URL
    cache_path: Path = Path("data/cache/external_api.sqlite3")
    cache_ttl_days: int = Field(default=30, gt=0, le=3650)
    min_request_interval_seconds: float = Field(default=0.2, ge=0)
    max_retries: int = Field(default=4, ge=0, le=10)

    @field_validator("openfigi_base_url", "sec_tickers_url", "sec_submissions_url")
    @classmethod
    def _require_https(cls, value: str) -> str:
        """Require an https URL so the API key is never sent in cleartext.

        Args:
            value: A configured provider URL.

        Returns:
            The validated URL.

        Raises:
            ValueError: If the URL is empty or not https.
        """
        if not value.startswith("https://"):
            msg = f"expected an https:// URL, got {value!r}"
            raise ValueError(msg)
        return value

    @field_validator("cache_path")
    @classmethod
    def _cache_path_must_be_gitignored(cls, value: Path) -> Path:
        """Enforce the ADR-015 licensing invariant in code, not just docs.

        The cache holds raw licensed provider JSON, so its path must resolve
        somewhere git ignores it (a ``.sqlite3`` suffix, covered by the
        ``*.sqlite3`` rule, or any path under a ``data/`` directory). An
        operator override outside those would let licensed data be committed.

        Args:
            value: The configured cache path.

        Returns:
            The validated path.

        Raises:
            ValueError: If the path is not covered by a gitignore rule.
        """
        if value.suffix == ".sqlite3" or "data" in value.parts:
            return value
        msg = (
            f"cache_path {value} is not gitignored; raw licensed provider JSON "
            "could be committed (ADR-015). Use a '.sqlite3' suffix or a path "
            "under 'data/'."
        )
        raise ValueError(msg)
