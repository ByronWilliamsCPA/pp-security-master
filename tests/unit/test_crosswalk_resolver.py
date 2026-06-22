"""Unit tests for the IBOR -> ABOR crosswalk resolver (ADR-016, Phase E4)."""

from security_master.crosswalk import (
    resolve_cfi_category,
    resolve_gics_from_provider,
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
