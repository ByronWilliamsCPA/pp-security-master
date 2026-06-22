"""The ADR-003 classification chain: fund -> equity -> bond -> manual.

Phase D3 implements ONLY the Tier-4 manual path (see ``manual.py``). The three
automated tiers below are explicit future-stubs, not silent gaps: each raises
``NotImplementedError`` referencing ADR-005 (external-API sourcing, future). The
orchestrator documents the intended order; until the automated tiers land, the
working entry point is ``manual.apply_manual_classification``.
"""

from __future__ import annotations

_FUTURE = "automated classification is future work; see ADR-005"


def classify_fund(identifier: str) -> None:
    """Tier-2 fund/ETF classification (future).

    Args:
        identifier: Security identifier (ISIN or ticker).

    Raises:
        NotImplementedError: Always; see ADR-005.
    """
    # TODO(ADR-005): pp-portfolio-classifier look-through. Honor classification_locked.
    msg = f"fund {_FUTURE}"
    raise NotImplementedError(msg)


def classify_equity(identifier: str) -> None:
    """Tier-3 listed-equity classification (future).

    Args:
        identifier: Security identifier (ISIN or ticker).

    Raises:
        NotImplementedError: Always; see ADR-005.
    """
    # TODO(ADR-005): OpenFIGI + SIC/NAICS -> GICS crosswalk. Honor classification_locked.
    msg = f"equity {_FUTURE}"
    raise NotImplementedError(msg)


def classify_bond(identifier: str) -> None:
    """Tier-3 bond classification (future).

    Args:
        identifier: Security identifier (ISIN).

    Raises:
        NotImplementedError: Always; see ADR-005.
    """
    # TODO(ADR-005): CFI category D + free bond sector. Honor classification_locked.
    msg = f"bond {_FUTURE}"
    raise NotImplementedError(msg)


def classify_security(identifier: str) -> None:
    """Run the full automated chain fund -> equity -> bond (future).

    Args:
        identifier: Security identifier.

    Raises:
        NotImplementedError: Always; the automated chain is future work (ADR-005).
            The manual fallback is invoked directly via
            ``manual.apply_manual_classification``.
    """
    # TODO(ADR-005): try fund -> equity -> bond, each skipping locked rows, then
    # queue unresolved securities for the Tier-4 manual path.
    msg = f"automated chain {_FUTURE}"
    raise NotImplementedError(msg)
