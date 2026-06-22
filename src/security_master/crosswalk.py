"""IBOR -> ABOR crosswalk resolver (ADR-016, Phase E4).

Turns the declarative crosswalk files in ``crosswalks/`` into lookups that join
an IBOR holding's classification to the ABOR (Xero GL account, CFI category) and
to GICS. This is the executable half of the ADR-016 identifier contract; the
human contract lives in ``docs/project/IBOR_ABOR_IDENTIFIER_CONTRACT.md``.

The reference data is read packaged-first, repo-root-fallback: installed wheels
carry a copy under ``security_master/crosswalks/`` (shipped via the pyproject
force-include) and editable / in-repo runs read it from the repo root. Both
layouts resolve without an explicit ``base``.

#ASSUME the force-include in ``pyproject.toml`` keeps the wheel's
``security_master/crosswalks/`` copy in sync with the repo-root source.
#VERIFY a wheel build includes the YAML files (``python -m build`` then inspect
the wheel) whenever a crosswalk file is added or renamed.
"""

from functools import cache
from importlib import resources
from pathlib import Path
from typing import cast

import yaml

# Editable / in-repo runs read the reference data from the repo root; installed
# wheels read a copy shipped inside the package (see the force-include in
# pyproject.toml). _read_crosswalk resolves packaged-first, repo-root-fallback so
# both layouts work without an explicit base override.
_REPO_CROSSWALK_DIR = Path(__file__).resolve().parents[2] / "crosswalks"


def _read_crosswalk(name: str) -> str:
    """Read a crosswalk file's text from the packaged copy or the repo root.

    Args:
        name: File name within the crosswalks directory.

    Returns:
        The file's UTF-8 text.
    """
    packaged = resources.files("security_master") / "crosswalks" / name
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")
    return (_REPO_CROSSWALK_DIR / name).read_text(encoding="utf-8")


@cache
def _load(name: str, base: str | None = None) -> dict[str, object]:
    """Load and cache a crosswalk YAML document.

    Args:
        name: File name within the crosswalks directory.
        base: Optional override for the crosswalks directory.

    Returns:
        The parsed YAML mapping.
    """
    text = (
        (Path(base) / name).read_text(encoding="utf-8")
        if base is not None
        else _read_crosswalk(name)
    )
    return cast("dict[str, object]", yaml.safe_load(text))


def _section(doc: dict[str, object], key: str) -> dict[str, str]:
    """Return a string-to-string mapping section from a crosswalk document.

    Args:
        doc: A parsed crosswalk document.
        key: The section name to extract.

    Returns:
        A copy of the section as a ``dict[str, str]`` (empty if absent). A copy
        is returned so a caller cannot mutate the ``@cache``-shared document.
    """
    return dict(cast("dict[str, str]", doc.get(key, {})))


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
