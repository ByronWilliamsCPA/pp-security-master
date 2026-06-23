"""Remaining higher-tier classifiers are explicit future-stubs (ADR-005)."""

import pytest

from security_master.classifier.chain import (
    classify_bond,
    classify_fund,
    classify_security,
)

pytestmark = [pytest.mark.unit, pytest.mark.classifier]


@pytest.mark.parametrize("func", [classify_fund, classify_bond, classify_security])
def test_remaining_automated_tiers_are_explicit_stubs(func) -> None:
    with pytest.raises(NotImplementedError, match="ADR-005"):
        func("US0378331005")
