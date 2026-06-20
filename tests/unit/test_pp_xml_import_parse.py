"""Unit tests for the pure PP XML parser (no database required).

Validates :func:`security_master.patch.pp_xml_import.parse_client` against the
committed ``sample_data/BruceandSueWilliams_sample.xml`` fixture and small
inline documents. These tests exercise parsing only; persistence and round-trip
behavior are covered by the integration suite.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from security_master.patch.pp_xml_import import (
    ParsedClient,
    parse_client,
)

# Oracles derived from the committed sample backup (version 66).
_SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "sample_data"
    / ("BruceandSueWilliams_sample.xml")
)
# The sample has 4 <account> and 3 <portfolio> elements, but one of each is a
# degenerate placeholder with no uuid; the parser skips those, leaving 3 and 2.
_EXPECTED_SECURITIES = 18
_EXPECTED_PRICES = 53207
_EXPECTED_ACCOUNTS = 3
_EXPECTED_PORTFOLIOS = 2
_EXPECTED_BOOKMARKS = 18


@pytest.fixture(scope="module")
def parsed_sample() -> ParsedClient:
    """Parse the committed sample backup once for the module."""
    return parse_client(_SAMPLE.read_text(encoding="utf-8"))


@pytest.mark.unit
def test_sample_fixture_exists() -> None:
    """The round-trip sample fixture is present in the repository."""
    assert _SAMPLE.is_file(), f"missing sample fixture: {_SAMPLE}"


@pytest.mark.unit
def test_parses_client_metadata(parsed_sample: ParsedClient) -> None:
    """Client version and base currency are parsed."""
    assert parsed_sample.version == 66
    assert parsed_sample.base_currency == "USD"


@pytest.mark.unit
def test_parses_expected_entity_counts(parsed_sample: ParsedClient) -> None:
    """Top-level entity counts match the known sample."""
    assert len(parsed_sample.securities) == _EXPECTED_SECURITIES
    assert len(parsed_sample.accounts) == _EXPECTED_ACCOUNTS
    assert len(parsed_sample.portfolios) == _EXPECTED_PORTFOLIOS
    assert len(parsed_sample.bookmarks) == _EXPECTED_BOOKMARKS


@pytest.mark.unit
def test_parses_full_price_history(parsed_sample: ParsedClient) -> None:
    """Every price point across all securities is parsed."""
    assert parsed_sample.price_count == _EXPECTED_PRICES


@pytest.mark.unit
def test_first_security_fields(parsed_sample: ParsedClient) -> None:
    """A representative security maps every supported field."""
    security = parsed_sample.securities[0]
    assert security.name == "ISHARES ETHEREUM TRUST ETF"
    assert security.isin == "US46438R1059"
    assert security.symbol == "ETHA"
    assert security.wkn == "717828992"
    assert security.currency == "USD"
    assert security.prices, "expected price history"
    first_price = security.prices[0]
    assert first_price.price_date == date(2024, 7, 23)
    assert first_price.value == 2624000000


@pytest.mark.unit
def test_account_fields(parsed_sample: ParsedClient) -> None:
    """A representative account maps uuid, name, currency, and retired flag."""
    account = parsed_sample.accounts[0]
    assert account.uuid == "103416fd-1f99-4034-9dd5-24a47b930747"
    assert account.name == "Base 70/30"
    assert account.currency_code == "USD"
    assert account.is_retired is False


@pytest.mark.unit
def test_missing_version_raises() -> None:
    """A document without <version> is rejected."""
    with pytest.raises(ValueError, match="version"):
        parse_client("<client><baseCurrency>USD</baseCurrency></client>")


@pytest.mark.unit
def test_minimal_document_parses() -> None:
    """A minimal valid document parses to empty entity lists."""
    client = parse_client(
        "<client><version>1</version><baseCurrency>EUR</baseCurrency></client>",
    )
    assert client.version == 1
    assert client.base_currency == "EUR"
    assert client.securities == []
    assert client.price_count == 0
