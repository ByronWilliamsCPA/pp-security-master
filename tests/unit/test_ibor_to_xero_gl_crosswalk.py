"""Consistency tests for the IBOR -> Xero GL crosswalk (ADR-016, Phase E2).

These guard against drift between the crosswalk mapping and the GL taxonomy: a
mapping that points at a GL code which no longer exists in the taxonomy is a
silent mis-booking waiting to happen.
"""

import json
from pathlib import Path
from typing import cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GL_TAXONOMY = REPO_ROOT / "taxonomies" / "accounting-xero-gl.taxonomy.json"
CROSSWALK = REPO_ROOT / "crosswalks" / "ibor_to_xero_gl.yaml"


def _gl_taxonomy_keys() -> set[str]:
    """Collect every leaf classification key in the GL taxonomy.

    Returns:
        The set of 8-digit Xero GL codes defined in the taxonomy.
    """
    data = cast(
        "dict[str, object]", json.loads(GL_TAXONOMY.read_text(encoding="utf-8"))
    )
    keys: set[str] = set()

    def walk(nodes: list[object]) -> None:
        for raw in nodes:
            node = cast("dict[str, object]", raw)
            raw_children = node.get("children")
            child_nodes = (
                cast("list[object]", raw_children)
                if isinstance(raw_children, list)
                else []
            )
            key = node.get("key")
            # Only leaf nodes carry assignable GL codes. Guarding on the absence
            # of children stops an intermediate-category key (not a real posting
            # target) from satisfying the crosswalk drift guard.
            if isinstance(key, str) and not child_nodes:
                keys.add(key)
            if child_nodes:
                walk(child_nodes)

    walk(cast("list[object]", data.get("categories", [])))
    return keys


def _crosswalk() -> dict[str, object]:
    """Load the crosswalk YAML.

    Returns:
        The parsed crosswalk document.
    """
    return cast(
        "dict[str, object]", yaml.safe_load(CROSSWALK.read_text(encoding="utf-8"))
    )


def _mapped_codes() -> set[str]:
    """Collect every GL code referenced by the crosswalk mapping sections.

    Returns:
        The set of GL codes appearing as mapping or override values.
    """
    cw = _crosswalk()
    codes: set[str] = set()
    for section in ("by_type_of_security", "by_brx_plus"):
        mapping = cast("dict[str, str]", cw.get(section, {}))
        codes.update(mapping.values())
    overrides = cast("dict[str, list[dict[str, str]]]", cw.get("overrides", {}))
    for entries in overrides.values():
        codes.update(e["gl"] for e in entries if "gl" in e)
    return codes


def test_every_mapped_code_exists_in_gl_taxonomy() -> None:
    """Every GL code the crosswalk maps to is a real leaf in the GL taxonomy."""
    unknown = _mapped_codes() - _gl_taxonomy_keys()
    assert not unknown, f"crosswalk references GL codes not in the taxonomy: {unknown}"


def test_gl_codes_are_eight_digit_numeric() -> None:
    """GL leaf keys follow the 8-digit Xero account-code shape."""
    bad = {k for k in _gl_taxonomy_keys() if not (k.isdigit() and len(k) == 8)}
    assert not bad, f"non 8-digit GL codes: {bad}"


def test_unresolved_entries_are_not_also_mapped() -> None:
    """A classification cannot be both mapped and listed as unresolved."""
    cw = _crosswalk()
    unresolved = set(cast("list[str]", cw.get("unresolved", [])))
    by_brx = cast("dict[str, str]", cw.get("by_brx_plus", {}))
    by_type = cast("dict[str, str]", cw.get("by_type_of_security", {}))
    overlap = unresolved & (set(by_brx) | set(by_type))
    assert not overlap, f"entries both mapped and unresolved: {overlap}"


def test_crosswalk_mapping_sections_present() -> None:
    """Both mapping sections exist, so a renamed key cannot silently skip
    validation. _mapped_codes() degrades a missing section to an empty mapping,
    which would let the drift guard pass while validating nothing."""
    cw = _crosswalk()
    for section in ("by_type_of_security", "by_brx_plus"):
        mapping = cw.get(section)
        assert isinstance(mapping, dict), f"crosswalk section '{section}' is missing"
        assert mapping, (
            f"crosswalk section '{section}' is empty; "
            "the drift guard would validate nothing"
        )
