"""Unit tests for ExternalAPISettings."""

from __future__ import annotations

from pathlib import Path

import pytest

from security_master.external.settings import ExternalAPISettings

pytestmark = [pytest.mark.unit]


def test_defaults_allow_keyless_openfigi(monkeypatch: pytest.MonkeyPatch) -> None:
    # conftest.py injects OPENFIGI_API_KEY into os.environ for the test suite;
    # remove it so we can verify the unauthenticated-default path.
    monkeypatch.delenv("OPENFIGI_API_KEY", raising=False)
    monkeypatch.delenv("OPENFIGI_BASE_URL", raising=False)
    settings = ExternalAPISettings(_env_file=None)
    assert settings.openfigi_api_key is None
    assert settings.openfigi_base_url.startswith("https://")
    assert settings.cache_ttl_days > 0


def test_explicit_values_round_trip() -> None:
    settings = ExternalAPISettings(
        _env_file=None,
        openfigi_api_key="k",
        sec_user_agent="pp-security-master byron@example.com",
    )
    assert settings.openfigi_api_key == "k"
    assert "byron@example.com" in settings.sec_user_agent


def test_rejects_non_https_url() -> None:
    with pytest.raises(ValueError, match="https"):
        ExternalAPISettings(_env_file=None, openfigi_base_url="http://insecure.example")


def test_rejects_non_gitignored_cache_path() -> None:
    with pytest.raises(ValueError, match="not gitignored"):
        ExternalAPISettings(_env_file=None, cache_path=Path("schema_exports/cache.db"))


def test_accepts_gitignored_cache_paths() -> None:
    # Covered by the *.sqlite3 rule, and by a path under data/.
    assert ExternalAPISettings(
        _env_file=None, cache_path=Path("elsewhere/cache.sqlite3")
    )
    assert ExternalAPISettings(_env_file=None, cache_path=Path("data/cache/x.db"))


def test_rejects_out_of_range_bounds() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        ExternalAPISettings(_env_file=None, max_retries=99)
