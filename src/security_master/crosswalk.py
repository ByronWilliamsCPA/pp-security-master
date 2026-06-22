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


def _resolve_override(
    doc: dict[str, object],
    key: str,
    wrapper: str | None,
    holding_intent: str | None,
) -> str | None:
    """Return a wrapper/intent-specific GL code for ``key``, if one matches.

    Args:
        doc: The parsed ibor_to_xero_gl crosswalk document.
        key: The already-resolved classification key (BRX-Plus or Type).
        wrapper: The holding's wrapper, if supplied by the caller.
        holding_intent: The holding's current/non-current intent, if supplied.

    Returns:
        The override GL code when an entry's declared conditions all match the
        supplied values, else ``None``.
    """
    overrides = cast("dict[str, list[dict[str, str]]]", doc.get("overrides", {}))
    for entry in overrides.get(key, []):
        want_wrapper = entry.get("wrapper")
        want_intent = entry.get("holding_intent")
        if want_wrapper is not None and want_wrapper != wrapper:
            continue
        if want_intent is not None and want_intent != holding_intent:
            continue
        gl = entry.get("gl")
        if gl is not None:
            return gl
    return None


def resolve_gl_account(
    *,
    brx_plus_key: str | None = None,
    type_of_security: str | None = None,
    wrapper: str | None = None,
    holding_intent: str | None = None,
    base: str | None = None,
) -> str | None:
    """Resolve the Xero GL account code for an IBOR holding.

    Resolution order matches ADR-016: a BRX-Plus key is most specific and wins;
    otherwise fall back to the Type of Security. When ``wrapper`` or
    ``holding_intent`` is supplied and the resolved key has an ``overrides``
    entry whose conditions match, the override replaces the default. Returns
    ``None`` when nothing resolves.

    Args:
        brx_plus_key: The holding's BRX-Plus classification key, if known.
        type_of_security: The holding's Type of Security key, if known.
        wrapper: Holding wrapper (``"direct"``, ``"fund"``, ``"etf"``,
            ``"public"``); selects a wrapper-specific override when present.
        holding_intent: ``"current"`` or ``"non_current"``; selects an
            intent-specific override when present. Not derivable from PP data,
            so it is a per-holding input.
        base: Optional override for the crosswalks directory.

    Returns:
        The Xero GL account code, or ``None`` if unresolved.
    """
    doc = _load("ibor_to_xero_gl.yaml", base)
    resolved_key: str | None = None
    default_gl: str | None = None
    if brx_plus_key:
        by_brx = _section(doc, "by_brx_plus")
        if brx_plus_key in by_brx:
            resolved_key, default_gl = brx_plus_key, by_brx[brx_plus_key]
    if default_gl is None and type_of_security:
        by_type = _section(doc, "by_type_of_security")
        if type_of_security in by_type:
            resolved_key, default_gl = type_of_security, by_type[type_of_security]
    if resolved_key is None or default_gl is None:
        return None
    if wrapper is not None or holding_intent is not None:
        override = _resolve_override(doc, resolved_key, wrapper, holding_intent)
        if override is not None:
            return override
    return default_gl


def _longest_prefix_match(code: str, mapping: dict[str, str]) -> str | None:
    """Return the value for the longest key in ``mapping`` that prefixes ``code``.

    Args:
        code: The full numeric industry code to classify.
        mapping: A prefix-keyed mapping (e.g. ``by_sic_prefix``).

    Returns:
        The mapped value for the longest matching prefix, or ``None`` if no key
        is a prefix of ``code``.
    """
    for length in range(len(code), 0, -1):
        candidate = code[:length]
        if candidate in mapping:
            return mapping[candidate]
    return None


def resolve_gics_from_sic_naics(
    *,
    sic: str | None = None,
    naics: str | None = None,
    base: str | None = None,
) -> str | None:
    """Resolve a GICS sector code from an issuer's SIC or NAICS code.

    Uses longest-prefix match so a deeper carve-out (e.g. SIC ``283`` drugs)
    overrides its 2-digit group (SIC ``28`` chemicals). SIC is tried first when
    both are supplied (it is the older, coarser scheme); #VERIFY this precedence
    against issuer data if SIC and NAICS disagree.

    Args:
        sic: The issuer's SIC code (any length), if known.
        naics: The issuer's NAICS code (any length), if known.
        base: Optional override for the crosswalks directory.

    Returns:
        The GICS sector code, or ``None`` if no prefix matches either input.
    """
    doc = _load("sic_naics_to_gics.yaml", base)
    if sic:
        match = _longest_prefix_match(sic, _section(doc, "by_sic_prefix"))
        if match is not None:
            return match
    if naics:
        match = _longest_prefix_match(naics, _section(doc, "by_naics_prefix"))
        if match is not None:
            return match
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
