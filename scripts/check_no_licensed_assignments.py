#!/usr/bin/env python3
"""Licensing guard: block committing identifier-to-GICS assignment data.

ADR-015 #CRITICAL: GICS sector ASSIGNMENTS for listed securities are licensed and
must stay user-local; a committed identifier-to-GICS file is a redistribution-
license violation. This guard scans taxonomies/, seeds/, and crosswalks/ and fails
when an identifier-shaped key maps to a GICS sector value.

Allowed (NOT flagged): SIC/NAICS/provider-sector -> GICS crosswalks (their keys are
not security identifiers), and the crypto seed (its values are BRX-Plus keys, not
GICS sectors).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCAN_DIRS = ("taxonomies", "seeds", "crosswalks")

# A line introducing an identifier-keyed block.
_ID_BLOCK = re.compile(r"^\s*by_(isin|ticker|symbol|cusip|figi|wkn)\s*:", re.IGNORECASE)
# An ISIN-shaped key: 2 letters, 9 alphanumerics, 1 check digit.
_ISIN_KEY = re.compile(r'^\s*["\']?([A-Z]{2}[A-Z0-9]{9}\d)["\']?\s*:')
# A GICS sector value: one of the 11 L1 names or a 2-digit code 10..60.
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
_GICS_CODES = {"10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "60"}
_VALUE = re.compile(r":\s*['\"]?([^'\"#\n]+?)['\"]?\s*$")


def _value_is_gics(raw: str) -> bool:
    """Return whether a mapping value names a GICS sector.

    Args:
        raw: The right-hand side of a ``key: value`` line.

    Returns:
        ``True`` if the value is one of the 11 GICS L1 names or codes.
    """
    v = raw.strip().strip("'\"").lower()
    return v in _GICS_NAMES or v in _GICS_CODES


def scan_text(path: str, text: str) -> list[str]:
    """Scan one file's text for identifier-to-GICS rows.

    Args:
        path: File path (for messages only).
        text: The file contents.

    Returns:
        A list of human-readable violation messages (empty when clean).
    """
    violations: list[str] = []
    in_id_block = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _ID_BLOCK.match(line):
            in_id_block = True
            continue
        if line and not line[:1].isspace() and ":" in line:
            in_id_block = False  # a new top-level key ends the block
        m_isin = _ISIN_KEY.match(line)
        m_val = _VALUE.search(line)
        is_id_key = bool(m_isin) or in_id_block
        if is_id_key and m_val and _value_is_gics(m_val.group(1)):
            key = m_isin.group(1) if m_isin else line.split(":", 1)[0].strip()
            violations.append(
                f"{path}:{lineno}: identifier {key!r} -> GICS {m_val.group(1)!r}"
            )
    return violations


def main(argv: list[str]) -> int:
    """Scan the committed taxonomy/seed/crosswalk dirs and report violations.

    Args:
        argv: Unused command-line arguments.

    Returns:
        ``1`` if any violation is found, else ``0``.
    """
    _ = argv
    failures: list[str] = []
    for directory in _SCAN_DIRS:
        base = _ROOT / directory
        if not base.is_dir():
            continue
        for path in sorted([*base.rglob("*.yaml"), *base.rglob("*.json")]):
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
