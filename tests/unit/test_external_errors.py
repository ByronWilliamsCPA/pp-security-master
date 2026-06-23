"""Unit tests for external-API error types."""

from __future__ import annotations

import pytest

from security_master.external.errors import ExternalAPIError

pytestmark = [pytest.mark.unit]


def test_external_api_error_carries_provider_and_message() -> None:
    err = ExternalAPIError(provider="openfigi", message="rate limited")
    assert err.provider == "openfigi"
    assert "openfigi" in str(err)
    assert "rate limited" in str(err)
