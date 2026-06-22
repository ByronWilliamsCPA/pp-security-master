"""Validate manual classification values against committed taxonomy files.

GICS-L1 sector names come from ``industries-gics-sectors.taxonomy.json`` (the 11
framework labels, safe to ship per ADR-015). BRX-Plus sleeve keys come from
``brx-plus-byron.taxonomy.json`` (the user's own scheme).
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from pathlib import Path
from typing import TypeAlias, cast

JSONValue: TypeAlias = (
    "str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]"
)

_REPO_TAXONOMY_DIR = Path(__file__).resolve().parents[3] / "taxonomies"
_GICS_SECTORS_FILE = "industries-gics-sectors.taxonomy.json"
_BRX_PLUS_FILE = "brx-plus-byron.taxonomy.json"

CASH_LEVEL1 = "Cash & Cash Equivalents"


class UnknownClassificationValueError(ValueError):
    """Raised when a value is not present in the relevant taxonomy."""


def _read_taxonomy(name: str) -> JSONValue:
    """Read a taxonomy JSON file packaged-first, repo-root-fallback.

    Args:
        name: File name within the taxonomies directory.

    Returns:
        The parsed taxonomy document.
    """
    packaged = resources.files("security_master") / "taxonomies" / name
    text = (
        packaged.read_text(encoding="utf-8")
        if packaged.is_file()
        else (_REPO_TAXONOMY_DIR / name).read_text(encoding="utf-8")
    )
    return cast("JSONValue", json.loads(text))


def _dict_list(value: JSONValue) -> list[dict[str, JSONValue]]:
    """Narrow a parsed JSON value to a list of object nodes.

    Args:
        value: A parsed JSON value.

    Returns:
        The elements that are JSON objects; an empty list otherwise.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _categories(doc: JSONValue) -> list[dict[str, JSONValue]]:
    """Extract the ``categories`` list of mapping nodes from a taxonomy doc.

    Args:
        doc: A parsed taxonomy document.

    Returns:
        The category nodes that are JSON objects; an empty list otherwise.
    """
    if not isinstance(doc, dict):
        return []
    return _dict_list(doc.get("categories"))


def _str_field(node: dict[str, JSONValue], field: str) -> str | None:
    """Return ``node[field]`` if it is a string, else ``None``.

    Args:
        node: A taxonomy node mapping.
        field: The field name to read.

    Returns:
        The string value, or ``None`` if absent or non-string.
    """
    value = node.get(field)
    return value if isinstance(value, str) else None


@cache
def _gics_sector_names() -> dict[str, str]:
    """Map lower-cased GICS-L1 sector names to their canonical form.

    Returns:
        Mapping of ``name.lower()`` to the canonical sector name.
    """
    names: dict[str, str] = {}
    for node in _categories(_read_taxonomy(_GICS_SECTORS_FILE)):
        name = _str_field(node, "name")
        if name is not None:
            names[name.lower()] = name
    return names


@cache
def _brx_plus_index() -> dict[str, tuple[str, str]]:
    """Map every BRX-Plus leaf key to ``(level1_name, leaf_name)``.

    Returns:
        Mapping of leaf key to a (top-level category name, leaf name) tuple.
    """
    index: dict[str, tuple[str, str]] = {}
    for parent in _categories(_read_taxonomy(_BRX_PLUS_FILE)):
        level1 = _str_field(parent, "name") or ""
        for child in _dict_list(parent.get("children")):
            key = _str_field(child, "key")
            if key is not None:
                index[key] = (level1, _str_field(child, "name") or "")
    return index


def resolve_gics_sector(value: str) -> str:
    """Return the canonical GICS-L1 sector name for ``value``.

    Args:
        value: A candidate sector name (case-insensitive).

    Returns:
        The canonical sector name.

    Raises:
        UnknownClassificationValueError: If the value is not one of the 11 sectors.
    """
    canonical = _gics_sector_names().get(value.strip().lower())
    if canonical is None:
        valid = ", ".join(sorted(_gics_sector_names().values()))
        msg = f"unknown GICS-L1 sector {value!r}; valid: {valid}"
        raise UnknownClassificationValueError(msg)
    return canonical


def resolve_brx_plus_sleeve(key: str) -> tuple[str, str]:
    """Return ``(level1_name, leaf_name)`` for a BRX-Plus leaf key.

    Args:
        key: A BRX-Plus leaf key (e.g. ``"AC.ALTS.CRYPTO.BTC"``).

    Returns:
        The top-level category name and the leaf name.

    Raises:
        UnknownClassificationValueError: If the key is not in the BRX-Plus taxonomy.
    """
    pair = _brx_plus_index().get(key)
    if pair is None:
        msg = f"unknown BRX-Plus sleeve key {key!r}"
        raise UnknownClassificationValueError(msg)
    return pair
