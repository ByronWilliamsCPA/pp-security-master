"""Licensing guard: identifier-key -> GICS-value is forbidden; crypto seed is allowed."""

import pytest
from scripts.check_no_licensed_assignments import scan_text

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_isin_to_gics_name_is_flagged() -> None:
    violations = scan_text(
        "evil.yaml", 'by_isin:\n  US0378331005: "Information Technology"\n'
    )
    assert violations


def test_isin_to_gics_code_is_flagged() -> None:
    violations = scan_text("evil.yaml", "by_isin:\n  US0378331005: '45'\n")
    assert violations


def test_crypto_seed_symbol_to_brx_is_allowed() -> None:
    ok = "by_symbol:\n  BTC: AC.ALTS.CRYPTO.BTC\n  ETH: AC.ALTS.CRYPTO.ETH\n"
    assert scan_text("seeds/crypto_classification.yaml", ok) == []


def test_provider_sector_to_gics_is_allowed() -> None:
    # SIC/NAICS/provider keys are NOT security identifiers, so mapping them to GICS is legal.
    text = "by_provider_sector:\n  Technology: '45'\n"
    assert scan_text("crosswalks/provider_sector_to_gics.yaml", text) == []
