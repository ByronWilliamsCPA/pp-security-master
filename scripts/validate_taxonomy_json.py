#!/usr/bin/env python3
"""Validate Portfolio Performance taxonomy JSON files against the importer contract.

Portfolio Performance imports a standalone taxonomy through
``File > Import > Import taxonomy``. The accepted JSON shape is defined by
``TaxonomyJSONImporter.java`` in the upstream project. This script asserts the
invariants that importer enforces so a file is known-good before it is handed
to PP:

* root object: ``name`` (str), optional ``color`` (str), optional
  ``categories`` (list), optional ``instruments`` (list);
* each category: ``name`` is required and non-empty; ``key``, ``description``
  and ``color`` are optional strings; ``children`` is an optional list of
  categories;
* ``color`` values, when present, are ``#RRGGBB`` hex;
* classification keys are unique within a taxonomy (a duplicate key would make
  ``setKey`` ambiguous on import);
* instrument assignment weights are within 0-100 and sum to at most 100 per
  instrument.

Exit code is non-zero if any file fails, so the script doubles as a CI gate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import cast

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "taxonomies"


class TaxonomyError(Exception):
    """Raised when a taxonomy JSON file violates the PP importer contract."""


def _as_dict(value: object) -> dict[str, object] | None:
    """Return ``value`` typed as a string-keyed dict, or ``None`` if it is not a dict.

    Args:
        value: A value decoded from JSON (statically untyped).

    Returns:
        The value as ``dict[str, object]`` when it is a mapping, else ``None``.
    """
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def _as_list(value: object) -> list[object] | None:
    """Return ``value`` typed as a list, or ``None`` if it is not a list.

    Args:
        value: A value decoded from JSON (statically untyped).

    Returns:
        The value as ``list[object]`` when it is a sequence, else ``None``.
    """
    return cast("list[object]", value) if isinstance(value, list) else None


def _check_color(value: object, where: str, errors: list[str]) -> None:
    """Record an error if ``value`` is present but not a ``#RRGGBB`` hex string.

    Args:
        value: The candidate color value (may be ``None`` if absent).
        where: Human-readable location used in the error message.
        errors: Mutable list that collected errors are appended to.
    """
    if value is None:
        return
    if not isinstance(value, str) or not HEX_COLOR.match(value):
        errors.append(f"{where}: color {value!r} is not a #RRGGBB hex string")


def _walk_categories(
    categories: list[object],
    path: str,
    keys: list[str],
    errors: list[str],
) -> int:
    """Validate a list of category nodes recursively and count the nodes.

    Args:
        categories: The ``categories``/``children`` list to validate.
        path: Slash-delimited path to ``categories`` for error messages.
        keys: Accumulator of every ``key`` seen, used for the uniqueness check.
        errors: Mutable list that collected errors are appended to.

    Returns:
        The number of category nodes found in this subtree.
    """
    count = 0
    for index, raw_node in enumerate(categories):
        where = f"{path}[{index}]"
        node = _as_dict(raw_node)
        if node is None:
            errors.append(f"{where}: category must be an object")
            continue
        count += 1
        name = node.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{where}: 'name' is required and must be non-empty")
        key = node.get("key")
        if key is not None:
            if not isinstance(key, str) or not key.strip():
                errors.append(f"{where}: 'key' must be a non-empty string when present")
            else:
                keys.append(key)
        _check_color(node.get("color"), where, errors)
        raw_children = node.get("children")
        if raw_children is not None:
            children = _as_list(raw_children)
            if children is None:
                errors.append(f"{where}: 'children' must be a list")
            else:
                count += _walk_categories(children, f"{where}/children", keys, errors)
    return count


def _check_instruments(instruments: list[object], errors: list[str]) -> None:
    """Validate the optional ``instruments`` assignment block.

    Args:
        instruments: The ``instruments`` list from the taxonomy root.
        errors: Mutable list that collected errors are appended to.
    """
    for index, raw_entry in enumerate(instruments):
        where = f"instruments[{index}]"
        entry = _as_dict(raw_entry)
        if entry is None:
            errors.append(f"{where}: instrument must be an object")
            continue
        if _as_dict(entry.get("identifiers")) is None:
            errors.append(f"{where}: 'identifiers' object is required")
        assignments = _as_list(entry.get("categories", []))
        if assignments is None:
            errors.append(f"{where}: 'categories' must be a list")
            continue
        total = 0.0
        for a_index, raw_assignment in enumerate(assignments):
            a_where = f"{where}/categories[{a_index}]"
            assignment = _as_dict(raw_assignment)
            if assignment is None:
                errors.append(f"{a_where}: assignment must be an object")
                continue
            weight = assignment.get("weight", 100)
            if not isinstance(weight, (int, float)) or not 0 <= weight <= 100:
                errors.append(f"{a_where}: weight {weight!r} must be within 0-100")
            else:
                total += float(weight)
        if total > 100.0001:
            errors.append(f"{where}: assignment weights sum to {total} (> 100)")


def validate_file(path: Path) -> int:
    """Validate a single taxonomy JSON file.

    Args:
        path: Path to the ``*.taxonomy.json`` file.

    Returns:
        The total number of category nodes in the file.

    Raises:
        TaxonomyError: If the file violates the PP importer contract.
    """
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"{path.name}: invalid JSON: {exc}"
        raise TaxonomyError(msg) from exc

    data = _as_dict(parsed)
    if data is None:
        msg = f"{path.name}: root must be a JSON object"
        raise TaxonomyError(msg)

    errors: list[str] = []
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("root: 'name' is required and must be non-empty")
    _check_color(data.get("color"), "root", errors)

    categories = _as_list(data.get("categories", []))
    if categories is None:
        errors.append("root: 'categories' must be a list")
        categories = []

    keys: list[str] = []
    node_count = _walk_categories(categories, "categories", keys, errors)

    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        errors.append(f"root: duplicate classification keys: {', '.join(duplicates)}")

    raw_instruments = data.get("instruments")
    if raw_instruments is not None:
        instruments = _as_list(raw_instruments)
        if instruments is None:
            errors.append("root: 'instruments' must be a list")
        else:
            _check_instruments(instruments, errors)

    if errors:
        joined = "\n  - ".join(errors)
        msg = f"{path.name}: {len(errors)} error(s):\n  - {joined}"
        raise TaxonomyError(msg)
    return node_count


def main(argv: list[str]) -> int:
    """Validate every taxonomy file in the target directory.

    Args:
        argv: Command-line arguments; an optional directory path overrides the
            default ``taxonomies/`` directory.

    Returns:
        Process exit code: ``0`` if all files pass, ``1`` otherwise.
    """
    target = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    files = sorted(target.glob("*.taxonomy.json"))
    if not files:
        print(f"No *.taxonomy.json files found in {target}", file=sys.stderr)
        return 1

    failures = 0
    for path in files:
        try:
            count = validate_file(path)
        except TaxonomyError as exc:
            failures += 1
            print(f"FAIL {exc}", file=sys.stderr)
        else:
            print(f"OK   {path.name}: {count} classification nodes")

    print(f"\n{len(files) - failures}/{len(files)} taxonomy files valid")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
