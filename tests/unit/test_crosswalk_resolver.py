"""Unit tests for the IBOR -> ABOR crosswalk resolver (ADR-016, Phase E4)."""

import textwrap
from pathlib import Path

from security_master.crosswalk import (
    resolve_brx_plus_from_gics,
    resolve_cfi_category,
    resolve_gics_from_provider,
    resolve_gics_from_sic_naics,
    resolve_gl_account,
)


def _write_ibor_crosswalk(tmp_path: Path, body: str) -> str:
    """Write an ibor_to_xero_gl fixture and return its directory for ``base=``.

    ``_load`` caches on ``(name, base)``; pytest gives each test a unique
    ``tmp_path``, so distinct fixtures never collide in the cache.

    Args:
        tmp_path: The pytest-provided temporary directory.
        body: YAML body for the fixture crosswalk.

    Returns:
        The directory path (as a string) to pass as ``base``.
    """
    (tmp_path / "ibor_to_xero_gl.yaml").write_text(
        textwrap.dedent(body), encoding="utf-8"
    )
    return str(tmp_path)


def test_brx_plus_resolves_crypto_to_digital_assets() -> None:
    """A crypto BRX-Plus sleeve books to the Digital Assets - Cost Basis account."""
    assert (
        resolve_gl_account(brx_plus_key="AC.ALTS.CRYPTO.BTC", allow_provisional=True)
        == "14121100"
    )


def test_brx_plus_resolves_equity_to_publicly_traded() -> None:
    """An equity sleeve books to Investment in Publicly Traded Securities."""
    assert (
        resolve_gl_account(
            brx_plus_key="AC.EQUITY.US.CORE_BETA", allow_provisional=True
        )
        == "14201400"
    )


def test_brx_plus_takes_precedence_over_type() -> None:
    """When both are supplied, the BRX-Plus key wins over Type of Security."""
    gl = resolve_gl_account(
        brx_plus_key="AC.ALTS.CRYPTO.BTC",
        type_of_security="Stock",
        allow_provisional=True,
    )
    assert gl == "14121100"


def test_type_of_security_fallback() -> None:
    """With no BRX-Plus key, resolution falls back to Type of Security."""
    assert (
        resolve_gl_account(type_of_security="Fund", allow_provisional=True)
        == "14201000"
    )
    assert (
        resolve_gl_account(type_of_security="Stock", allow_provisional=True)
        == "14201400"
    )


def test_unresolved_returns_none() -> None:
    """Empty input resolves to None; an unknown key resolves to None."""
    assert resolve_gl_account(allow_provisional=True) is None
    assert (
        resolve_gl_account(brx_plus_key="AC.NOT.A.KEY", allow_provisional=True) is None
    )


def test_provisional_gate_withholds_codes_without_optin() -> None:
    """The draft ibor crosswalk (no `complete: true`) withholds codes by default.

    This is the financial safety gate: a naive caller cannot post a provisional
    GL code; receiving one requires an explicit allow_provisional opt-in.
    """
    assert resolve_gl_account(brx_plus_key="AC.CASH.MONEY_MARKET") is None
    assert resolve_gl_account(brx_plus_key="AC.EQUITY.US.CORE_BETA") is None


def test_cash_sleeves_resolve_to_provisional_leaves() -> None:
    """With opt-in, cash sleeves map to the provisional cash-equivalent GL leaves."""
    assert (
        resolve_gl_account(brx_plus_key="AC.CASH.MONEY_MARKET", allow_provisional=True)
        == "11141000"
    )
    assert (
        resolve_gl_account(brx_plus_key="AC.CASH.TBILLS", allow_provisional=True)
        == "11141100"
    )
    assert (
        resolve_gl_account(brx_plus_key="AC.CASH.SHORT_TERM", allow_provisional=True)
        == "11141200"
    )


def test_authoritative_crosswalk_returns_codes_without_optin(tmp_path: Path) -> None:
    """A crosswalk with `complete: true` resolves codes without allow_provisional."""
    base = _write_ibor_crosswalk(
        tmp_path,
        """
        version: 1
        complete: true
        by_brx_plus:
          AC.X: "11110000"
        """,
    )
    assert resolve_gl_account(brx_plus_key="AC.X", base=base) == "11110000"


def test_wrapper_override_direct_real_estate() -> None:
    """A direct-property RE holding books to Investment Property, not REIT."""
    assert (
        resolve_gl_account(brx_plus_key="AC.ALTS.RE", allow_provisional=True)
        == "14201400"
    )
    assert (
        resolve_gl_account(
            brx_plus_key="AC.ALTS.RE", wrapper="direct", allow_provisional=True
        )
        == "15111200"
    )
    # An unmatched wrapper falls back to the default.
    assert (
        resolve_gl_account(
            brx_plus_key="AC.ALTS.RE", wrapper="public", allow_provisional=True
        )
        == "14201400"
    )


def test_wrapper_with_no_overrides_block_falls_back() -> None:
    """A wrapper on a key with no `overrides` entry returns the default code."""
    assert (
        resolve_gl_account(
            brx_plus_key="AC.EQUITY.US.CORE_BETA",
            wrapper="direct",
            allow_provisional=True,
        )
        == "14201400"
    )


def test_brx_plus_precedence_and_type_fallthrough() -> None:
    """BRX-Plus wins when both supplied; an unknown BRX-Plus falls through to type."""
    assert (
        resolve_gl_account(
            brx_plus_key="AC.CASH.TBILLS",
            type_of_security="Stock",
            allow_provisional=True,
        )
        == "11141100"
    )
    assert (
        resolve_gl_account(
            brx_plus_key="AC.NOT.A.KEY",
            type_of_security="Stock",
            allow_provisional=True,
        )
        == "14201400"
    )


def test_holding_intent_override_selects_intent_specific_gl(tmp_path: Path) -> None:
    """An intent-keyed override fires only when holding_intent matches."""
    base = _write_ibor_crosswalk(
        tmp_path,
        """
        version: 1
        complete: true
        by_brx_plus:
          AC.X: "11110000"
        overrides:
          AC.X:
            - { holding_intent: non_current, gl: "22220000" }
        """,
    )
    assert resolve_gl_account(brx_plus_key="AC.X", base=base) == "11110000"
    assert (
        resolve_gl_account(brx_plus_key="AC.X", holding_intent="non_current", base=base)
        == "22220000"
    )
    assert (
        resolve_gl_account(brx_plus_key="AC.X", holding_intent="current", base=base)
        == "11110000"
    )


def test_override_first_match_and_combined_conditions(tmp_path: Path) -> None:
    """First matching entry wins; a two-condition entry needs both to match."""
    base = _write_ibor_crosswalk(
        tmp_path,
        """
        version: 1
        complete: true
        by_brx_plus:
          AC.X: "11110000"
        overrides:
          AC.X:
            - { wrapper: direct, holding_intent: non_current, gl: "33330000" }
            - { wrapper: direct, gl: "22220000" }
        """,
    )
    # Only wrapper matches: the two-condition entry is skipped; the second wins.
    assert (
        resolve_gl_account(brx_plus_key="AC.X", wrapper="direct", base=base)
        == "22220000"
    )
    # Both conditions match: the first entry wins by position.
    assert (
        resolve_gl_account(
            brx_plus_key="AC.X",
            wrapper="direct",
            holding_intent="non_current",
            base=base,
        )
        == "33330000"
    )


def test_resolve_cfi_category() -> None:
    """Type of Security maps to the expected CFI category letter."""
    assert resolve_cfi_category("Stock") == "E"
    assert resolve_cfi_category("Bond") == "D"
    assert resolve_cfi_category("ETF") == "C"
    assert resolve_cfi_category("nonexistent") is None


def test_resolve_gics_from_provider() -> None:
    """Morningstar provider sectors map to GICS sector codes."""
    assert resolve_gics_from_provider("Energy") == "10"
    assert resolve_gics_from_provider("Healthcare") == "35"
    assert resolve_gics_from_provider("Not A Sector") is None


def test_resolve_gics_from_sic_exact_and_prefix() -> None:
    """SIC lookup uses longest-prefix match; a 3-digit carve-out beats its group."""
    assert resolve_gics_from_sic_naics(sic="13") == "10"  # Oil & Gas -> Energy
    assert resolve_gics_from_sic_naics(sic="2834") == "35"  # 283 drugs -> Health Care
    assert resolve_gics_from_sic_naics(sic="2890") == "15"  # 28 chemicals -> Materials
    assert resolve_gics_from_sic_naics(sic="9999") is None  # no matching prefix


def test_resolve_gics_from_naics_prefix_tie_break() -> None:
    """NAICS lookup prefers the deeper prefix (211 Energy beats 21 Materials)."""
    assert resolve_gics_from_sic_naics(naics="211110") == "10"  # Oil & Gas Extraction
    assert resolve_gics_from_sic_naics(naics="212") == "15"  # Mining (ex O&G)
    assert resolve_gics_from_sic_naics(naics="54151") == "45"  # Computer Systems Design
    assert resolve_gics_from_sic_naics(naics="00") is None


def test_resolve_gics_sic_takes_precedence_over_naics() -> None:
    """When both are supplied, SIC is tried first."""
    assert resolve_gics_from_sic_naics(sic="60", naics="00") == "40"
    assert resolve_gics_from_sic_naics(sic=None, naics="52") == "40"


def test_resolve_gics_sic_miss_falls_through_to_naics() -> None:
    """A non-matching SIC falls through to a matching NAICS rather than returning None."""
    assert resolve_gics_from_sic_naics(sic="9999", naics="52") == "40"
    assert resolve_gics_from_sic_naics(sic="", naics="52") == "40"


def test_resolve_brx_plus_single_sector() -> None:
    """A single-sector holding maps to its GICS sector sleeve."""
    assert (
        resolve_brx_plus_from_gics("10", is_single_sector=True)
        == "AC.EQUITY.SECTOR.ENERGY"
    )
    assert (
        resolve_brx_plus_from_gics("45", is_single_sector=True)
        == "AC.EQUITY.SECTOR.INFO_TECH"
    )


def test_resolve_brx_plus_guardrail_blocks_broad_holdings() -> None:
    """Broad/factor/region holdings are never auto-assigned from GICS."""
    assert resolve_brx_plus_from_gics("10", is_single_sector=False) is None


def test_resolve_brx_plus_unknown_sector_falls_back() -> None:
    """An unknown sector code on a single-sector holding falls back to the default."""
    assert (
        resolve_brx_plus_from_gics("99", is_single_sector=True)
        == "AC.EQUITY.SECTOR_THEMATIC"
    )
