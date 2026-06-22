#!/usr/bin/env python3
"""Licensing guard: block committing identifier-to-GICS assignment data.

ADR-015 #CRITICAL: GICS sector ASSIGNMENTS for listed securities are licensed and
must stay user-local; a committed identifier-to-GICS file is a redistribution-
license violation (ADR-015 section 3 and the #VERIFY at its end). This guard
parses every committed YAML/JSON file in the repository (not just a few data
directories, so the data cannot evade by living elsewhere) and fails when a
security identifier is mapped to a GICS sector value, covering:

* an ISIN-shaped mapping key -> GICS value;
* a key under any ``by_<identifier>`` mapping (``by_isin``/``by_ticker``/
  ``by_symbol``/``by_cusip``/``by_figi``/``by_wkn``/``by_sedol``/``by_ric``/...)
  -> GICS value, where the value is a scalar OR a container that holds a GICS
  value at any depth (e.g. ``{US0378331005: {sector: Energy}}``);
* a Portfolio Performance ``instruments`` block (the canonical assignment
  mechanism, ADR-015 section 1): an ``identifiers`` object paired with a
  ``categories`` (list of dicts OR list of plain strings) or singular
  ``category`` entry that names a GICS sector.

A GICS value is one of the 11 L1 sector names (case-insensitive) or a GICS code:
an L1 code (10..60) or a 4/6/8-digit sub-code whose 2-digit prefix is an L1 code.

Allowed (NOT flagged): SIC/NAICS/provider-sector -> GICS crosswalks (the ``by_*``
suffix names a classification SCHEME, not a security identifier, so it is not in
the identifier-namespace set) and the crypto seed (values are BRX-Plus AC.* keys).

#VERIFY (security/licensing): two narrow vectors remain deferred and should be
revisited if a leak is suspected: GICS sub-industry NAMES (the ~158-entry name
list, vs the 11 L1 names covered here) and bare non-ISIN identifier keys
(CUSIP/SEDOL) OUTSIDE a ``by_*`` or ``instruments`` block, because a bare numeric
key is ambiguous against legitimate GICS-code category keys. Identifiers inside an
``identifiers`` object are checked regardless of type.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import cast

import yaml

# Parsed-JSON/YAML node aliases (real types so cast() narrows for the type checker
# and the literal is not duplicated across cast calls).
_ObjDict = dict[object, object]
_ObjList = list[object]

_ROOT = Path(__file__).resolve().parent.parent

# Directories never worth scanning (VCS internals, virtualenvs, caches, build
# output). The guard scans every other committed YAML/JSON so licensed data
# cannot evade by living outside a data directory.
_EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".nox",
        ".tox",
        "build",
        "dist",
        ".worktrees",
        "htmlcov",
    }
)

_ISIN = re.compile(r"^[A-Za-z]{2}[A-Za-z0-9]{9}\d$")

# Security-identifier namespaces. A ``by_<name>`` mapping keyed on one of these is
# an identifier block (its keys are securities); the same names appear inside a PP
# ``identifiers`` object. Classification schemes (sic/naics/sector/region) are
# deliberately absent so SIC/NAICS -> GICS crosswalks stay allowed.
_SECURITY_ID_NAMES = frozenset(
    {
        "isin",
        "ticker",
        "symbol",
        "cusip",
        "figi",
        "openfigi",
        "wkn",
        "sedol",
        "ric",
        "bbg",
        "bloomberg",
        "cik",
        "lei",
        "valor",
        "valoren",
        "permid",
    }
)
_ID_BLOCK_KEYS = frozenset(f"by_{name}" for name in _SECURITY_ID_NAMES)
_ID_FIELDS = _SECURITY_ID_NAMES | {"name"}

_GICS_NAMES = {
    "energy",
    "materials",
    "industrials",
    "consumer discretionary",
    "consumer staples",
    "health care",
    "financials",
    "information technology",
    "communication services",
    "utilities",
    "real estate",
}
_GICS_L1_CODES = {"10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "60"}


def _is_gics_value(value: object) -> bool:
    """Return whether a value names a GICS sector (L1 name, or L1/sub code).

    Args:
        value: A candidate mapping value.

    Returns:
        True if the value is a GICS L1 name, an L1 code, or a 4/6/8-digit sub-code.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return False
    if text.lower() in _GICS_NAMES:
        return True
    if not text.isdigit():
        return False
    if text in _GICS_L1_CODES:
        return True
    return len(text) in (4, 6, 8) and text[:2] in _GICS_L1_CODES


def _find_gics_value(node: object) -> object | None:
    """Return the first GICS value reachable in ``node`` (scalar or nested).

    Catches an identifier mapped to a GICS value directly OR wrapped in a dict or
    list (e.g. ``{US0378331005: {sector: Energy}}`` or ``{US0378331005: [Energy]}``),
    which a scalar-only check would miss.

    Args:
        node: The value mapped from an identifier key.

    Returns:
        The first GICS value found, or ``None``.
    """
    if _is_gics_value(node):
        return node
    if isinstance(node, dict):
        for val in cast("_ObjDict", node).values():
            hit = _find_gics_value(val)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for item in cast("_ObjList", node):
            hit = _find_gics_value(item)
            if hit is not None:
                return hit
    return None


def _is_identifier_key(key: object) -> bool:
    """Return whether a mapping key looks like a security identifier (ISIN).

    Args:
        key: A mapping key.

    Returns:
        True if the key matches the ISIN shape.
    """
    return isinstance(key, str) and bool(_ISIN.match(key))


def _collect_identifier_fields(identifiers: object) -> list[str]:
    """Collect ``field=value`` pairs from a PP ``identifiers`` object.

    Args:
        identifiers: The value of an ``identifiers`` key (expected to be a dict).

    Returns:
        A list of ``field=value`` strings for recognised identifier fields.
    """
    if not isinstance(identifiers, dict):
        return []
    ids: list[str] = []
    for field, val in cast("_ObjDict", identifiers).items():
        if (
            isinstance(field, str)
            and field.lower() in _ID_FIELDS
            and isinstance(val, str)
        ):
            ids.append(f"{field}={val}")
    return ids


def _entry_categories(entry: dict[object, object]) -> list[object]:
    """Collect category entries from a PP instrument, both block variants.

    Args:
        entry: One ``instruments`` list entry.

    Returns:
        The plural ``categories`` list items plus any singular ``category``.
    """
    cats: list[object] = []
    categories = entry.get("categories")
    if isinstance(categories, list):
        cats.extend(cast("_ObjList", categories))
    single = entry.get("category")
    if single is not None:
        cats.append(single)
    return cats


def _category_gics_value(cat: object) -> object | None:
    """Return the GICS value named by a category entry, if any.

    A category is either a dict with a ``key``/``name`` slot or a plain string.

    Args:
        cat: One category entry.

    Returns:
        The GICS value if the category names a GICS sector, else ``None``.
    """
    if isinstance(cat, dict):
        cat_d = cast("_ObjDict", cat)
        for slot in ("key", "name"):
            if _is_gics_value(cat_d.get(slot)):
                return cat_d.get(slot)
        return None
    return cat if _is_gics_value(cat) else None


def _check_instruments(instruments: object, path: str, out: list[str]) -> None:
    """Flag PP instruments entries that assign an identifier to a GICS category.

    Args:
        instruments: The value of an ``instruments`` key (expected to be a list).
        path: File path for messages.
        out: Accumulator for violation messages.
    """
    if not isinstance(instruments, list):
        return
    for entry in cast("_ObjList", instruments):
        if not isinstance(entry, dict):
            continue
        entry_d = cast("_ObjDict", entry)
        ids = _collect_identifier_fields(entry_d.get("identifiers"))
        if not ids:
            continue
        for cat in _entry_categories(entry_d):
            hit = _category_gics_value(cat)
            if hit is not None:
                out.append(f"{path}: instruments {ids} -> GICS {hit!r}")


def _flag_identifier_assignment(
    key: object, value: object, path: str, out: list[str], *, in_id_block: bool
) -> None:
    """Append a violation if ``key`` is an identifier mapped to a GICS value.

    Args:
        key: The mapping key.
        value: The value mapped from ``key`` (scalar or container).
        path: File path for messages.
        out: Accumulator for violation messages.
        in_id_block: True when the parent mapping was a ``by_*`` identifier block.
    """
    if not (in_id_block or _is_identifier_key(key)):
        return
    hit = _find_gics_value(value)
    if hit is not None:
        out.append(f"{path}: identifier {key!r} -> GICS {hit!r}")


def _walk(node: object, path: str, out: list[str], *, in_id_block: bool) -> None:
    """Recursively flag identifier-key -> GICS-value mappings and instruments blocks.

    Args:
        node: The current parsed node.
        path: File path for messages.
        out: Accumulator for violation messages.
        in_id_block: True when the parent mapping was a ``by_*`` identifier block.
    """
    if isinstance(node, dict):
        node_d = cast("_ObjDict", node)
        if "instruments" in node_d:
            _check_instruments(node_d.get("instruments"), path, out)
        for key, value in node_d.items():
            _flag_identifier_assignment(key, value, path, out, in_id_block=in_id_block)
            child_in_id_block = isinstance(key, str) and key.lower() in _ID_BLOCK_KEYS
            _walk(value, path, out, in_id_block=child_in_id_block)
    elif isinstance(node, list):
        for item in cast("_ObjList", node):
            _walk(item, path, out, in_id_block=in_id_block)


def scan_text(path: str, text: str) -> list[str]:
    """Scan one file's text for identifier-to-GICS assignment rows.

    Args:
        path: File path (selects the parser by suffix; used in messages).
        text: The file contents.

    Returns:
        A list of violation messages (empty when clean). A parse failure returns no
        violations; file syntax is validated by other hooks.
    """
    try:
        data: object = (
            json.loads(text) if path.endswith(".json") else yaml.safe_load(text)
        )
    except (json.JSONDecodeError, yaml.YAMLError):
        return []
    out: list[str] = []
    _walk(data, path, out, in_id_block=False)
    # The nested and id-block passes can reach the same scalar twice; dedupe so a
    # single assignment is reported once. dict.fromkeys preserves first-seen order.
    return list(dict.fromkeys(out))


def _iter_data_files() -> list[Path]:
    """Enumerate every YAML/JSON file in the repo outside excluded directories.

    Returns:
        Sorted list of YAML/JSON paths to scan (whole-tree, so licensed data
        cannot evade by living outside a known data directory).
    """
    paths: list[Path] = []
    for path in _ROOT.rglob("*"):
        if path.suffix.lower() not in (".yaml", ".yml", ".json"):
            continue
        if any(part in _EXCLUDE_DIRS for part in path.relative_to(_ROOT).parts):
            continue
        paths.append(path)
    return sorted(paths)


def main(argv: list[str]) -> int:
    """Scan every committed YAML/JSON file and report identifier-to-GICS rows.

    Args:
        argv: Unused command-line arguments.

    Returns:
        1 if any violation is found, else 0.
    """
    _ = argv
    failures: list[str] = []
    for path in _iter_data_files():
        rel = str(path.relative_to(_ROOT))
        try:
            # errors="replace" keeps a non-UTF-8 file from crashing the guard;
            # GICS names/codes are ASCII, so replacement chars never hide a match.
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"LICENSING GUARD: could not read {rel}: {exc}", file=sys.stderr)
            failures.append(f"{rel}: unreadable, cannot verify ({exc})")
            continue
        failures.extend(scan_text(rel, text))
    for msg in failures:
        print(f"LICENSING VIOLATION {msg}", file=sys.stderr)
    if failures:
        print(
            f"\n{len(failures)} identifier-to-GICS row(s) found (ADR-015 #CRITICAL).",
            file=sys.stderr,
        )
        return 1
    print("Licensing guard: no identifier-to-GICS assignment rows found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
