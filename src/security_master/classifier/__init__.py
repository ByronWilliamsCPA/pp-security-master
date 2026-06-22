"""Security classification engine (ADR-003 four-tier chain).

Phase D3 implements ONLY the Tier-4 manual fallback + override path. The
fund -> equity -> bond automated tiers are explicit future-stubs (added in a
later task; see ADR-005). The override lock on ``securities_master`` is the
integration contract that keeps manual (D3) and automated (future) sector
assignment from colliding.

This package is built incrementally across the D3 tasks; exports grow as the
manual path, chain stubs, and crypto seed land.
"""

from security_master.classifier.taxonomy_lookup import (
    UnknownClassificationValueError,
    resolve_brx_plus_sleeve,
    resolve_gics_sector,
)
from security_master.classifier.types import (
    AssignmentKind,
    ClassificationLockedError,
    ClassificationResult,
    ClassificationTier,
    ManualAssignment,
)

__all__ = [
    "AssignmentKind",
    "ClassificationLockedError",
    "ClassificationResult",
    "ClassificationTier",
    "ManualAssignment",
    "UnknownClassificationValueError",
    "resolve_brx_plus_sleeve",
    "resolve_gics_sector",
]
