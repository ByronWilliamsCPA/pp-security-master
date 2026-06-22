"""Licensing guard: identifier-key -> GICS-value is forbidden; crypto seed is allowed."""

from pathlib import Path

import pytest
import scripts.check_no_licensed_assignments as guard
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


def test_pp_instruments_isin_to_gics_code_is_flagged() -> None:
    text = '{"instruments":[{"identifiers":{"isin":"US0378331005"},"categories":[{"key":"45","weight":100}]}]}'
    assert scan_text("taxonomies/evil.taxonomy.json", text)


def test_inline_flow_isin_to_gics_is_flagged() -> None:
    assert scan_text("evil.yaml", "by_isin: {US0378331005: Energy}\n")


def test_gics_subcode_is_flagged() -> None:
    assert scan_text("evil.yaml", "by_isin:\n  US0378331005: '4510'\n")


def test_trailing_comment_value_is_flagged() -> None:
    assert scan_text("evil.yaml", "by_isin:\n  US0378331005: Energy  # sneaky\n")


def test_instruments_non_gics_category_is_allowed() -> None:
    text = '{"instruments":[{"identifiers":{"isin":"US0378331005"},"categories":[{"key":"AC.EQUITY"}]}]}'
    assert scan_text("taxonomies/ok.taxonomy.json", text) == []


# --- Hardening: evasions that previously slipped past the guard ---


def test_nested_dict_gics_value_under_isin_is_flagged() -> None:
    # GICS value wrapped in a dict, not a bare scalar.
    assert scan_text("evil.yaml", "by_isin:\n  US0378331005:\n    sector: Energy\n")


def test_nested_list_gics_value_under_isin_is_flagged() -> None:
    assert scan_text("evil.yaml", "by_isin:\n  US0378331005:\n    - Energy\n")


def test_unlisted_identifier_namespace_by_sedol_is_flagged() -> None:
    assert scan_text("evil.yaml", "by_sedol:\n  '2046251': Information Technology\n")


def test_unlisted_identifier_namespace_by_ric_is_flagged() -> None:
    assert scan_text("evil.yaml", "by_ric:\n  AAPL.O: Information Technology\n")


def test_classification_scheme_namespace_by_sic_is_allowed() -> None:
    # SIC is a classification scheme, not a security identifier; the SIC -> GICS
    # crosswalk must stay allowed even though it uses a by_* mapping.
    assert (
        scan_text("crosswalks/sic_to_gics.yaml", "by_sic:\n  '3711': Industrials\n")
        == []
    )


def test_instruments_categories_list_of_strings_is_flagged() -> None:
    text = '{"instruments":[{"identifiers":{"isin":"US0378331005"},"categories":["Energy"]}]}'
    assert scan_text("taxonomies/evil.taxonomy.json", text)


def test_instruments_singular_category_is_flagged() -> None:
    text = '{"instruments":[{"identifiers":{"isin":"US0378331005"},"category":{"key":"Energy"}}]}'
    assert scan_text("taxonomies/evil.taxonomy.json", text)


def test_main_flags_planted_file_outside_data_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A licensed assignment hidden outside taxonomies/seeds/crosswalks must still
    # be caught now that the guard scans the whole tree.
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "sneaky.yaml").write_text(
        "by_isin:\n  US0378331005: Energy\n", encoding="utf-8"
    )
    monkeypatch.setattr(guard, "_ROOT", tmp_path)
    assert guard.main([]) == 1


def test_main_clean_tree_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "seeds").mkdir()
    (tmp_path / "seeds" / "crypto.yaml").write_text(
        "by_symbol:\n  BTC: AC.ALTS.CRYPTO.BTC\n", encoding="utf-8"
    )
    monkeypatch.setattr(guard, "_ROOT", tmp_path)
    assert guard.main([]) == 0


def test_main_skips_excluded_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A violation inside an excluded dir (e.g. a vendored .venv) is not scanned.
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "vendored.yaml").write_text(
        "by_isin:\n  US0378331005: Energy\n", encoding="utf-8"
    )
    monkeypatch.setattr(guard, "_ROOT", tmp_path)
    assert guard.main([]) == 0
