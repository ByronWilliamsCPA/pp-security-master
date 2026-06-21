"""IBOR -> ABOR crosswalk resolver (ADR-016, Phase E4).

Turns the declarative crosswalk files in ``crosswalks/`` into lookups that join
an IBOR holding's classification to the ABOR (Xero GL account, CFI category) and
to GICS. This is the executable half of the ADR-016 identifier contract; the
human contract lives in ``docs/project/IBOR_ABOR_IDENTIFIER_CONTRACT.md``.

#ASSUME the ``crosswalks/`` reference data sits at the repository root next to
the package (true in-repo and in editable installs).
#VERIFY pass an explicit ``base`` directory if the data is relocated or the
package is installed without the repo tree.
"""

from functools import cache
from pathlib import Path
from typing import cast

import yaml

_CROSSWALK_DIR = Path(__file__).resolve().parents[2] / "crosswalks"


@cache
def _load(name: str, base: str | None = None) -> dict[str, object]:
    """Load and cache a crosswalk YAML document.

    Args:
        name: File name within the crosswalks directory.
        base: Optional override for the crosswalks directory.

    Returns:
        The parsed YAML mapping.
    """
    directory = Path(base) if base is not None else _CROSSWALK_DIR
    parsed = yaml.safe_load((directory / name).read_text(encoding="utf-8"))
    return cast("dict[str, object]", parsed)


def _section(doc: dict[str, object], key: str) -> dict[str, str]:
    """Return a string-to-string mapping section from a crosswalk document.

    Args:
        doc: A parsed crosswalk document.
        key: The section name to extract.

    Returns:
        The section as a ``dict[str, str]`` (empty if absent).
    """
    return cast("dict[str, str]", doc.get(key, {}))


def resolve_gl_account(
    *,
    brx_plus_key: str | None = None,
    type_of_security: str | None = None,
    base: str | None = None,
) -> str | None:
    """Resolve the Xero GL account code for an IBOR holding.

    Resolution order matches ADR-016: a BRX-Plus key is most specific and wins;
    otherwise fall back to the Type of Security. Returns ``None`` when neither
    resolves (for example the cash sleeves listed as ``unresolved``).

    Args:
        brx_plus_key: The holding's BRX-Plus classification key, if known.
        type_of_security: The holding's Type of Security key, if known.
        base: Optional override for the crosswalks directory.

    Returns:
        The 8-digit Xero GL account code, or ``None`` if unresolved.
    """
    doc = _load("ibor_to_xero_gl.yaml", base)
    if brx_plus_key:
        by_brx = _section(doc, "by_brx_plus")
        if brx_plus_key in by_brx:
            return by_brx[brx_plus_key]
    if type_of_security:
        by_type = _section(doc, "by_type_of_security")
        if type_of_security in by_type:
            return by_type[type_of_security]
    return None


def resolve_cfi_category(type_of_security: str, base: str | None = None) -> str | None:
    """Resolve the CFI (ISO 10962) category letter for a Type of Security.

    Args:
        type_of_security: A Type of Security key (e.g. ``"Stock"``).
        base: Optional override for the crosswalks directory.

    Returns:
        The CFI category letter, or ``None`` if the type is not mapped.
    """
    mapping = _section(_load("security_type_to_cfi.yaml", base), "by_type_of_security")
    return mapping.get(type_of_security)


def resolve_gics_from_provider(
    provider_sector: str,
    base: str | None = None,
) -> str | None:
    """Resolve a GICS sector code from a data-provider sector name.

    Args:
        provider_sector: A provider sector label (Morningstar scheme).
        base: Optional override for the crosswalks directory.

    Returns:
        The GICS sector code, or ``None`` if the sector is not mapped.
    """
    mapping = _section(
        _load("provider_sector_to_gics.yaml", base),
        "by_provider_sector",
    )
    return mapping.get(provider_sector)
