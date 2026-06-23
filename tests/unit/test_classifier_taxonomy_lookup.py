"""GICS-L1 and BRX-Plus value validation against committed taxonomies."""

import pytest

from security_master.classifier.taxonomy_lookup import (
    UnknownClassificationValueError,
    resolve_brx_plus_sleeve,
    resolve_gics_sector,
    resolve_gics_sector_by_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.classifier]


def test_resolve_gics_sector_accepts_canonical_name() -> None:
    assert resolve_gics_sector("Information Technology") == "Information Technology"


def test_resolve_gics_sector_is_case_insensitive() -> None:
    assert resolve_gics_sector("information technology") == "Information Technology"


def test_resolve_gics_sector_rejects_unknown() -> None:
    with pytest.raises(UnknownClassificationValueError):
        resolve_gics_sector("Widgets")


def test_resolve_brx_plus_sleeve_returns_level_names() -> None:
    level1, leaf = resolve_brx_plus_sleeve("AC.ALTS.CRYPTO.BTC")
    assert level1 == "Alternatives"
    assert leaf == "Crypto (BTC)"


def test_resolve_brx_plus_sleeve_rejects_unknown_key() -> None:
    with pytest.raises(UnknownClassificationValueError):
        resolve_brx_plus_sleeve("AC.NOPE")


def test_resolve_gics_sector_by_code_returns_canonical_name() -> None:
    assert resolve_gics_sector_by_code("45") == "Information Technology"
    assert resolve_gics_sector_by_code(" 10 ") == "Energy"


def test_resolve_gics_sector_by_code_rejects_unknown_code() -> None:
    with pytest.raises(UnknownClassificationValueError):
        resolve_gics_sector_by_code("99")
