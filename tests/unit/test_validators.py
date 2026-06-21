"""Unit tests for :mod:`security_master.storage.validators`.

Exercises :class:`SecurityDataValidator` format checks, the weighted
data-quality scoring helpers, and the aggregate ``validate_security`` rules.
All tests are pure: a transient :class:`SecurityMaster` instance is built in
memory and never persisted, so no database is required.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from security_master.storage.models import SecurityMaster
from security_master.storage.validators import SecurityDataValidator

# NOTE (characterization): SecurityDataValidator.validate_isin implements a
# NON-standard check digit (it omits the Luhn digit-sum of doubled products),
# so it rejects real, spec-valid ISINs such as "US0378331005" and accepts some
# spec-invalid ones. These tests pin the routine's CURRENT behavior, not the
# ISO 6166 spec. "DE0005140008" is an ISIN that the current routine accepts and
# is used to drive the valid-ISIN branches. See skill-observation #548.
_VALID_ISIN = "DE0005140008"


@pytest.mark.storage
@pytest.mark.parametrize(
    ("isin", "expected"),
    [
        (None, True),  # optional field
        ("", True),  # optional field
        (_VALID_ISIN, True),  # accepted by the current check-digit routine
        ("DE0005140009", False),  # wrong check digit
        ("de0005140008", False),  # lowercase fails the format pattern
        ("DE000514000", False),  # too short
        ("US0378331005", False),  # real, spec-valid ISIN the routine rejects (bug)
    ],
)
def test_validate_isin(isin: str | None, expected: bool) -> None:
    """ISIN validation: format gate plus the current (non-standard) check digit.

    Characterization test. See module note and skill-observation #548: the
    routine deviates from ISO 6166, so a genuinely valid ISIN appears as a
    rejected case here on purpose.
    """
    assert SecurityDataValidator.validate_isin(isin) is expected


@pytest.mark.storage
@pytest.mark.parametrize(
    ("wkn", "expected"),
    [(None, True), ("", True), ("865985", True), ("12345", False), ("ABCDEFG", False)],
)
def test_validate_wkn(wkn: str | None, expected: bool) -> None:
    """WKN validation accepts optional values and a 6-char alphanumeric code."""
    assert SecurityDataValidator.validate_wkn(wkn) is expected


@pytest.mark.storage
@pytest.mark.parametrize(
    ("symbol", "expected"),
    [(None, True), ("", True), ("AAPL", True), ("BRK.B", True), ("bad sym", False)],
)
def test_validate_symbol(symbol: str | None, expected: bool) -> None:
    """Symbol validation accepts optional values and the allowed character set."""
    assert SecurityDataValidator.validate_symbol(symbol) is expected


@pytest.mark.storage
@pytest.mark.parametrize(
    ("currency", "expected"),
    [
        ("USD", True),
        ("EUR", True),
        ("US", False),
        ("usd", False),
        ("US1", False),
        ("", False),
    ],
)
def test_validate_currency(currency: str, expected: bool) -> None:
    """Currency validation requires a 3-letter uppercase alphabetic code."""
    assert SecurityDataValidator.validate_currency(currency) is expected


@pytest.mark.storage
def test_quality_score_is_perfect_for_complete_record() -> None:
    """A fully populated, valid security scores at the 1.00 ceiling."""
    security = SecurityMaster(
        name="APPLE INC",
        isin=_VALID_ISIN,
        symbol="AAPL",
        wkn="865985",
        currency="USD",
        latest_price=Decimal("190.00"),
        latest_date="2026-06-19",
        sector="Technology",
        type_of_security_level1="Equity",
        asset_classes_level1="Stocks",
        region="North America",
        market="NASDAQ",
        quote_feed_latest="YAHOO",
        data_source="OPENFIGI",
    )
    assert SecurityDataValidator.calculate_data_quality_score(security) == Decimal(
        "1.00"
    )


@pytest.mark.storage
def test_quality_score_is_zero_for_empty_record() -> None:
    """A record with no populated fields scores 0.00."""
    security = SecurityMaster()
    assert SecurityDataValidator.calculate_data_quality_score(security) == Decimal(
        "0.0"
    )


@pytest.mark.storage
def test_quality_score_is_partial_for_identification_only() -> None:
    """Identification fields alone contribute their 40% weight, no more."""
    security = SecurityMaster(
        name="APPLE INC",
        isin=_VALID_ISIN,
        symbol="AAPL",
        wkn="865985",
    )
    score = SecurityDataValidator.calculate_data_quality_score(security)
    assert score == pytest.approx(Decimal("0.4"))


@pytest.mark.storage
def test_validate_security_accepts_minimal_valid_record() -> None:
    """A record with required name and currency and no bad formats is valid."""
    security = SecurityMaster(name="APPLE INC", currency="USD")
    is_valid, errors = SecurityDataValidator.validate_security(security)
    assert is_valid is True
    assert errors == []


@pytest.mark.storage
def test_validate_security_reports_all_violations() -> None:
    """Every failing rule contributes a distinct, human-readable error."""
    security = SecurityMaster(
        name="",
        currency="us",
        isin="BADISIN",
        wkn="x",
        symbol="bad sym",
        latest_price=Decimal(-1),
        ter=Decimal(99),
    )
    is_valid, errors = SecurityDataValidator.validate_security(security)
    assert is_valid is False
    joined = " | ".join(errors)
    assert "Name is required" in joined
    assert "Invalid currency code" in joined
    assert "Invalid ISIN" in joined
    assert "Invalid WKN" in joined
    assert "Invalid symbol" in joined
    assert "Latest price cannot be negative" in joined
    assert "TER must be between" in joined


@pytest.mark.storage
def test_validate_security_flags_missing_currency() -> None:
    """A missing currency is reported separately from an invalid one."""
    security = SecurityMaster(name="APPLE INC", currency="")
    is_valid, errors = SecurityDataValidator.validate_security(security)
    assert is_valid is False
    assert "Currency is required" in errors
