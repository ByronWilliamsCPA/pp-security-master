"""Consistency tests for the classification crosswalks (ADR-016, Phase E3).

Each crosswalk maps one classification scheme onto another. These tests guard
against drift: a mapping that points at a code absent from the target taxonomy
would silently mis-classify.
"""

import json
from pathlib import Path
from typing import cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TAX = REPO_ROOT / "taxonomies"
CW = REPO_ROOT / "crosswalks"


def _taxonomy_keys(path: Path) -> set[str]:
    """Collect every classification key (leaf or group) in a taxonomy JSON.

    Args:
        path: Path to a ``*.taxonomy.json`` file.

    Returns:
        The set of all ``key`` values found anywhere in the tree.
    """
    data = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    keys: set[str] = set()

    def walk(nodes: list[object]) -> None:
        for raw in nodes:
            node = cast("dict[str, object]", raw)
            key = node.get("key")
            if isinstance(key, str):
                keys.add(key)
            children = node.get("children")
            if isinstance(children, list):
                walk(cast("list[object]", children))

    walk(cast("list[object]", data.get("categories", [])))
    return keys


def _yaml(path: Path) -> dict[str, object]:
    """Load a crosswalk YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        The parsed document.
    """
    return cast("dict[str, object]", yaml.safe_load(path.read_text(encoding="utf-8")))


def test_security_type_to_cfi_keys_and_values() -> None:
    """Type keys exist in the Type of Security taxonomy; CFI values are categories."""
    type_keys = _taxonomy_keys(TAX / "type-of-security.taxonomy.json")
    mapping = cast(
        "dict[str, str]",
        _yaml(CW / "security_type_to_cfi.yaml")["by_type_of_security"],
    )
    unknown = set(mapping) - type_keys
    assert not unknown, f"unknown Type of Security keys: {unknown}"
    allowed_cfi = {"E", "C", "D", "O", "T", "F", "S", "R", "H", "I", "J", "K", "L", "M"}
    bad = {v for v in mapping.values() if v not in allowed_cfi}
    assert not bad, f"invalid CFI category letters: {bad}"


def test_provider_sector_to_gics_targets_exist() -> None:
    """Every mapped GICS code exists in the GICS sectors taxonomy."""
    gics = _taxonomy_keys(TAX / "industries-gics-sectors.taxonomy.json")
    mapping = cast(
        "dict[str, str]",
        _yaml(CW / "provider_sector_to_gics.yaml")["by_provider_sector"],
    )
    unknown = set(mapping.values()) - gics
    assert not unknown, f"provider->GICS targets not in taxonomy: {unknown}"


def test_gics_to_brx_plus_keys_and_targets_exist() -> None:
    """GICS source keys and BRX-Plus target keys both resolve to real nodes."""
    gics = _taxonomy_keys(TAX / "industries-gics-sectors.taxonomy.json")
    brx = _taxonomy_keys(TAX / "brx-plus-byron.taxonomy.json")
    doc = _yaml(CW / "gics_to_brx_plus.yaml")
    mapping = cast("dict[str, str]", doc["by_gics_sector"])
    assert not (set(mapping) - gics), "GICS source codes not in taxonomy"
    assert not (set(mapping.values()) - brx), "BRX-Plus targets not in taxonomy"
    assert cast("str", doc["default_for_single_sector"]) in brx


def test_sic_naics_to_gics_targets_exist() -> None:
    """Every SIC/NAICS-mapped GICS code exists in the GICS sectors taxonomy."""
    gics = _taxonomy_keys(TAX / "industries-gics-sectors.taxonomy.json")
    doc = _yaml(CW / "sic_naics_to_gics.yaml")
    codes: set[str] = set()
    for section in ("by_sic_prefix", "by_naics_prefix"):
        codes.update(cast("dict[str, str]", doc[section]).values())
    unknown = codes - gics
    assert not unknown, f"SIC/NAICS->GICS targets not in taxonomy: {unknown}"
