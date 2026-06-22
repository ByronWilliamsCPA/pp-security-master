"""Unit tests for shared IBKR Flex parse helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from security_master.extractor._flex_common import (
    dash_to_none,
    none_if_empty,
    parse_decimal,
    parse_flex_date,
)


@pytest.mark.unit
@pytest.mark.extractor
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10/31/2023", date(2023, 10, 31)),
        ("10/31/2023;202000", date(2023, 10, 31)),
        ("20231031", date(2023, 10, 31)),
        ("2023-10-31", date(2023, 10, 31)),
        ("", None),
        (None, None),
    ],
)
def test_parse_flex_date(raw: str | None, expected: date | None) -> None:
    assert parse_flex_date(raw) == expected


@pytest.mark.unit
@pytest.mark.extractor
def test_parse_flex_date_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unrecognized IBKR Flex date"):
        parse_flex_date("31.10.2023")


@pytest.mark.unit
@pytest.mark.extractor
def test_dash_to_none() -> None:
    assert dash_to_none("--") is None
    assert dash_to_none("") is None
    assert dash_to_none("AAPL") == "AAPL"


@pytest.mark.unit
@pytest.mark.extractor
def test_reexports_match() -> None:
    """Back-compat aliases in ibkr_flex still resolve correctly."""
    from security_master.extractor.ibkr_flex import _none_if_empty as flex_nif

    assert flex_nif("  ") is None
    assert none_if_empty("  ") is None
    assert parse_decimal("1.50") == Decimal("1.50")
