"""Unit tests for the IBOR -> ABOR crosswalk resolver (ADR-016, Phase E4)."""

from security_master.crosswalk import (
    resolve_brx_plus_from_gics,
    resolve_cfi_category,
    resolve_gics_from_provider,
    resolve_gics_from_sic_naics,
    resolve_gl_account,
)


def test_brx_plus_resolves_crypto_to_digital_assets() -> None:
    """A crypto BRX-Plus sleeve books to the Digital Assets - Cost Basis account."""
    assert resolve_gl_account(brx_plus_key="AC.ALTS.CRYPTO.BTC") == "14121100"


def test_brx_plus_resolves_equity_to_publicly_traded() -> None:
    """An equity sleeve books to Investment in Publicly Traded Securities."""
    assert resolve_gl_account(brx_plus_key="AC.EQUITY.US.CORE_BETA") == "14201400"


def test_brx_plus_takes_precedence_over_type() -> None:
    """When both are supplied, the BRX-Plus key wins over Type of Security."""
    gl = resolve_gl_account(
        brx_plus_key="AC.ALTS.CRYPTO.BTC",
        type_of_security="Stock",
    )
    assert gl == "14121100"


def test_type_of_security_fallback() -> None:
    """With no BRX-Plus key, resolution falls back to Type of Security."""
    assert resolve_gl_account(type_of_security="Fund") == "14201000"
    assert resolve_gl_account(type_of_security="Stock") == "14201400"


def test_unresolved_returns_none() -> None:
    """Empty input resolves to None; an unknown key resolves to None."""
    assert resolve_gl_account() is None
    assert resolve_gl_account(brx_plus_key="AC.NOT.A.KEY") is None


def test_cash_sleeves_resolve_to_provisional_leaves() -> None:
    """Cash sleeves now map to the provisional cash-equivalent GL leaves."""
    assert resolve_gl_account(brx_plus_key="AC.CASH.MONEY_MARKET") == "11141000"
    assert resolve_gl_account(brx_plus_key="AC.CASH.TBILLS") == "11141100"
    assert resolve_gl_account(brx_plus_key="AC.CASH.SHORT_TERM") == "11141200"


def test_wrapper_override_direct_real_estate() -> None:
    """A direct-property RE holding books to Investment Property, not REIT."""
    assert resolve_gl_account(brx_plus_key="AC.ALTS.RE") == "14201400"
    assert resolve_gl_account(brx_plus_key="AC.ALTS.RE", wrapper="direct") == "15111200"
    # An unmatched wrapper falls back to the default.
    assert resolve_gl_account(brx_plus_key="AC.ALTS.RE", wrapper="public") == "14201400"


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
