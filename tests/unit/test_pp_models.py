"""Unit tests for derived helpers on :mod:`security_master.storage.pp_models`.

Covers the ``PPSecurityPrice.price_decimal`` property pair, which converts
between Portfolio Performance's integer price representation (value scaled by
1e8) and a :class:`~decimal.Decimal`. The instance is transient, so no database
is required.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from security_master.storage.pp_models import PPSecurityPrice

pytestmark = pytest.mark.storage


def test_price_decimal_setter_scales_to_pp_integer() -> None:
    """Assigning a Decimal stores the PP integer scaled by 1e8."""
    price = PPSecurityPrice()
    price.price_decimal = Decimal("26.24")
    assert price.price_value == 2_624_000_000


def test_price_decimal_getter_unscales_pp_integer() -> None:
    """Reading the property unscales the stored PP integer back to a Decimal."""
    price = PPSecurityPrice(price_value=2_624_000_000)
    assert price.price_decimal == Decimal("26.24")


def test_price_decimal_round_trips() -> None:
    """Set then get returns the original Decimal value."""
    price = PPSecurityPrice()
    price.price_decimal = Decimal("1234.56789012")
    assert price.price_decimal == Decimal("1234.56789012")
