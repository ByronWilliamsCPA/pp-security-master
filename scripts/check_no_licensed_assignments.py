#!/usr/bin/env python3
"""Licensing guard: block committing identifier-to-GICS assignment data.

ADR-015 #CRITICAL: GICS sector ASSIGNMENTS for listed securities are licensed and
must stay user-local; a committed identifier-to-GICS file is a redistribution-
license violation (ADR-015 section 3 and the #VERIFY at its end). This guard
parses every YAML/JSON file under taxonomies/, seeds/, and crosswalks/ and fails
when a security identifier is mapped to a GICS sector value, covering:

* an ISIN-shaped mapping key -> GICS value;
* a key under a ``by_isin``/``by_ticker``/``by_symbol``/``by_cusip``/``by_figi``/
  ``by_wkn`` mapping -> GICS value;
* a Portfolio Performance ``instruments`` block (the canonical assignment
  mechanism, ADR-015 section 1): an ``identifiers`` object paired with a
  ``categories`` entry whose ``key`` or ``name`` is a GICS sector.

A GICS value is one of the 11 L1 sector names (case-insensitive) or a GICS code:
an L1 code (10..60) or a 4/6/8-digit sub-code whose 2-digit prefix is an L1 code.

Allowed (NOT flagged): SIC/NAICS/provider-sector -> GICS crosswalks (keys are not
security identifiers) and the crypto seed (values are BRX-Plus AC.* keys).

#VERIFY (security/licensing): two narrow vectors are deliberately deferred and
should be revisited if a leak is suspected: GICS sub-industry NAMES (the ~158-entry
name list, vs the 11 L1 names covered here) and bare non-ISIN identifier keys
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

_ROOT = Path(__file__).resolve().parent.parent
_SCAN_DIRS = ("taxonomies", "seeds", "crosswalks")

_ISIN = re.compile(r"^[A-Za-z]{2}[A-Za-z0-9]{9}\d$")
_ID_BLOCK_KEYS = {"by_isin", "by_ticker", "by_symbol", "by_cusip", "by_figi", "by_wkn"}
_ID_FIELDS = {"isin", "ticker", "symbol", "cusip", "figi", "wkn", "sedol", "name"}

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
    for field, val in cast("dict[object, object]", identifiers).items():
        if (
            isinstance(field, str)
            and field.lower() in _ID_FIELDS
            and isinstance(val, str)
        ):
            ids.append(f"{field}={val}")
    return ids


def _check_instruments(instruments: object, path: str, out: list[str]) -> None:
    """Flag PP instruments entries that assign an identifier to a GICS category.

    Args:
        instruments: The value of an ``instruments`` key (expected to be a list).
        path: File path for messages.
        out: Accumulator for violation messages.
    """
    if not isinstance(instruments, list):
        return
    for entry in cast("list[object]", instruments):
        if not isinstance(entry, dict):
            continue
        entry_d = cast("dict[object, object]", entry)
        ids = _collect_identifier_fields(entry_d.get("identifiers"))
        categories = entry_d.get("categories")
        if not ids or not isinstance(categories, list):
            continue
        for cat in cast("list[object]", categories):
            if not isinstance(cat, dict):
                continue
            cat_d = cast("dict[object, object]", cat)
            for slot in ("key", "name"):
                if _is_gics_value(cat_d.get(slot)):
                    out.append(f"{path}: instruments {ids} -> GICS {cat_d.get(slot)!r}")


def _walk(node: object, path: str, out: list[str], *, in_id_block: bool) -> None:
    """Recursively flag identifier-key -> GICS-value mappings and instruments blocks.

    Args:
        node: The current parsed node.
        path: File path for messages.
        out: Accumulator for violation messages.
        in_id_block: True when the parent mapping was a ``by_*`` identifier block.
    """
    if isinstance(node, dict):
        node_d = cast("dict[object, object]", node)
        if "instruments" in node_d:
            _check_instruments(node_d.get("instruments"), path, out)
        for key, value in node_d.items():
            if (in_id_block or _is_identifier_key(key)) and _is_gics_value(value):
                out.append(f"{path}: identifier {key!r} -> GICS {value!r}")
            child_in_id_block = isinstance(key, str) and key.lower() in _ID_BLOCK_KEYS
            _walk(value, path, out, in_id_block=child_in_id_block)
    elif isinstance(node, list):
        for item in cast("list[object]", node):
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
    return out


def main(argv: list[str]) -> int:
    """Scan the committed taxonomy/seed/crosswalk dirs and report violations.

    Args:
        argv: Unused command-line arguments.

    Returns:
        1 if any violation is found, else 0.
    """
    _ = argv
    failures: list[str] = []
    for directory in _SCAN_DIRS:
        base = _ROOT / directory
        if not base.is_dir():
            continue
        for path in sorted(
            [*base.rglob("*.yaml"), *base.rglob("*.yml"), *base.rglob("*.json")]
        ):
            failures.extend(
                scan_text(
                    str(path.relative_to(_ROOT)),
                    path.read_text(encoding="utf-8"),
                )
            )
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
