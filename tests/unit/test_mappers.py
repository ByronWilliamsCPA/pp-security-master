"""Unit tests for :mod:`security_master.storage.mappers`.

Covers the pure :class:`SecurityMatcher` matching/variance helpers and the
:class:`PortfolioMappingManager`, which is exercised against an in-memory
SQLite database via the shared ``sqlite_session`` fixture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from security_master.storage.mappers import (
    PortfolioMappingManager,
    SecurityMatcher,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.storage


# ---------------------------------------------------------------------------
# SecurityMatcher: pure matching helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("US0378331005", "us0378331005 ", True),  # case/space insensitive
        ("US0378331005", "US5949181045", False),
        ("", "US0378331005", False),  # empty operand
        ("US0378331005", "", False),
    ],
)
def test_match_by_isin(a: str, b: str, expected: bool) -> None:
    """ISIN matching is case- and whitespace-insensitive and rejects empties."""
    assert SecurityMatcher.match_by_isin(a, b) is expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [("AAPL", " aapl", True), ("AAPL", "MSFT", False), ("", "AAPL", False)],
)
def test_match_by_ticker(a: str, b: str, expected: bool) -> None:
    """Ticker matching is case- and whitespace-insensitive and rejects empties."""
    assert SecurityMatcher.match_by_ticker(a, b) is expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("Apple Inc", "APPLE INC", True),  # exact (normalized)
        ("Apple", "Apple Inc", True),  # containment
        ("Apple Inc Common Stock", "Apple Inc Holdings", False),  # overlap 0.5 < 0.8
        ("Apple", "Microsoft", False),
        ("", "Apple", False),
    ],
)
def test_match_by_name(a: str, b: str, expected: bool) -> None:
    """Name matching handles exact, containment, and word-overlap cases."""
    assert SecurityMatcher.match_by_name(a, b) is expected


def test_match_by_name_word_overlap_threshold() -> None:
    """Word-overlap matching honors the configurable threshold."""
    pp_name = "ALPHA BETA GAMMA DELTA"
    kubera = "ALPHA BETA GAMMA EPSILON"  # 3/4 words shared = 0.75
    assert SecurityMatcher.match_by_name(pp_name, kubera, threshold=0.7) is True
    assert SecurityMatcher.match_by_name(pp_name, kubera, threshold=0.8) is False


def test_find_best_match_prefers_isin() -> None:
    """ISIN match wins over later ticker/name candidates."""
    holdings = [
        {"name": "Other", "ticker": "AAPL"},
        {"isin": "US0378331005", "name": "Apple"},
    ]
    match = SecurityMatcher.find_best_match(
        {"isin": "US0378331005", "symbol": "AAPL", "name": "Apple"},
        holdings,
    )
    assert match is not None
    assert match["isin"] == "US0378331005"


def test_find_best_match_falls_back_to_ticker_then_name() -> None:
    """With no ISIN, ticker matches; with neither, name matches."""
    by_ticker = SecurityMatcher.find_best_match(
        {"symbol": "AAPL"},
        [{"ticker": "AAPL", "name": "Apple"}],
    )
    assert by_ticker is not None
    assert by_ticker["ticker"] == "AAPL"

    by_name = SecurityMatcher.find_best_match(
        {"name": "Apple Inc"},
        [{"name": "APPLE INC"}],
    )
    assert by_name is not None
    assert by_name["name"] == "APPLE INC"


def test_find_best_match_skips_holdings_missing_the_key() -> None:
    """Holdings lacking the candidate key are skipped without matching."""
    # The first holding has no isin, so the isin branch skips it; the ISIN match
    # then falls through to a ticker match on a holding with no isin key.
    match = SecurityMatcher.find_best_match(
        {"isin": "US0378331005", "symbol": "AAPL"},
        [{"name": "no-isin", "ticker": "AAPL"}],
    )
    assert match is not None
    assert match["ticker"] == "AAPL"


def test_find_best_match_returns_none_when_no_candidate() -> None:
    """No ISIN/ticker/name candidate yields None."""
    assert SecurityMatcher.find_best_match({"isin": "US0378331005"}, []) is None
    assert SecurityMatcher.find_best_match({}, [{"isin": "X"}]) is None


def test_find_best_match_exhausts_name_candidates_without_match() -> None:
    """A name search whose holdings all fail to match falls through to None."""
    result = SecurityMatcher.find_best_match(
        {"name": "Apple Inc"},
        [{"name": "Microsoft Corp"}, {"ticker": "no-name"}],
    )
    assert result is None


@pytest.mark.parametrize(
    ("pp_value", "kubera_value", "abs_var", "pct_var"),
    [
        (100.0, 110.0, 10.0, 10.0),
        (100.0, 90.0, -10.0, -10.0),
        (0.0, 50.0, 50.0, 100.0),  # zero reference, non-zero comparison
        (0.0, 0.0, 0.0, 0.0),  # both zero
    ],
)
def test_calculate_variance(
    pp_value: float,
    kubera_value: float,
    abs_var: float,
    pct_var: float,
) -> None:
    """Variance returns absolute and percentage deltas, guarding divide-by-zero."""
    variance, percentage = SecurityMatcher.calculate_variance(pp_value, kubera_value)
    assert variance == pytest.approx(abs_var)
    assert percentage == pytest.approx(pct_var)


# ---------------------------------------------------------------------------
# PortfolioMappingManager backed by in-memory SQLite
# ---------------------------------------------------------------------------


def test_get_or_create_sheet_mapping_creates_then_reuses(
    sqlite_session: Session,
) -> None:
    """First call creates a sheet with a default PP group; second reuses it."""
    manager = PortfolioMappingManager(sqlite_session)
    created = manager.get_or_create_sheet_mapping("sheet-1", "IRA")
    assert created.pp_group_name == "IRA"  # from default_sheet_mappings

    again = manager.get_or_create_sheet_mapping("sheet-1", "IRA")
    assert again.id == created.id  # reused, not duplicated


def test_get_or_create_sheet_mapping_uses_name_when_no_default(
    sqlite_session: Session,
) -> None:
    """An unknown sheet name maps its PP group to itself."""
    manager = PortfolioMappingManager(sqlite_session)
    sheet = manager.get_or_create_sheet_mapping("sheet-x", "Brokerage")
    assert sheet.pp_group_name == "Brokerage"


def test_get_or_create_section_mapping_creates_then_reuses(
    sqlite_session: Session,
) -> None:
    """Sections are created under a parent sheet, then reused by id."""
    manager = PortfolioMappingManager(sqlite_session)
    sheet = manager.get_or_create_sheet_mapping("sheet-1", "IRA")
    section = manager.get_or_create_section_mapping("sec-1", "Wells fargo", sheet)
    assert section.pp_account_name == "Wells Fargo"  # mapped default
    again = manager.get_or_create_section_mapping("sec-1", "Wells fargo", sheet)
    assert again.id == section.id


def test_update_sheet_and_section_mappings(sqlite_session: Session) -> None:
    """Updates succeed for known ids and report False for unknown ids."""
    manager = PortfolioMappingManager(sqlite_session)
    sheet = manager.get_or_create_sheet_mapping("sheet-1", "IRA")
    manager.get_or_create_section_mapping("sec-1", "Wells fargo", sheet)

    assert manager.update_sheet_mapping("sheet-1", "Retirement") is True
    assert manager.update_sheet_mapping("missing", "X") is False
    assert manager.update_section_mapping("sec-1", "WF Brokerage") is True
    assert manager.update_section_mapping("missing", "X") is False


def test_get_pp_mapping_resolves_group_and_account(sqlite_session: Session) -> None:
    """A persisted sheet/section pair resolves to its PP group and account."""
    manager = PortfolioMappingManager(sqlite_session)
    sheet = manager.get_or_create_sheet_mapping("sheet-1", "IRA")
    manager.get_or_create_section_mapping("sec-1", "Wells fargo", sheet)
    sqlite_session.flush()

    group, account = manager.get_pp_mapping("sheet-1", "sec-1")
    assert group == "IRA"
    assert account == "Wells Fargo"

    assert manager.get_pp_mapping("sheet-1", "missing") == (None, None)


def test_list_unmapped_and_summary(sqlite_session: Session) -> None:
    """Unmapped listings and the nested summary reflect persisted state."""
    manager = PortfolioMappingManager(sqlite_session)
    sheet = manager.get_or_create_sheet_mapping("sheet-1", "IRA")
    manager.get_or_create_section_mapping("sec-1", "Wells fargo", sheet)
    sqlite_session.flush()

    # All created rows have mappings, so unmapped lists are empty.
    assert manager.list_unmapped_sheets() == []
    assert manager.list_unmapped_sections() == []

    summary = manager.get_mapping_summary()
    assert summary["IRA"]["pp_group"] == "IRA"
    assert "Wells fargo" in summary["IRA"]["sections"]
    assert summary["IRA"]["sections"]["Wells fargo"]["pp_account"] == "Wells Fargo"
