"""Security classification engine (ADR-003 four-tier chain).

Phase D3 implements ONLY the Tier-4 manual fallback + override path. The
fund -> equity -> bond automated tiers are explicit future-stubs (added in a
later task; see ADR-005). The override lock on ``securities_master`` is the
integration contract that keeps manual (D3) and automated (future) sector
assignment from colliding.

This package is built incrementally across the D3 tasks; exports grow as the
manual path, chain stubs, and crypto seed land.
"""

from security_master.classifier.chain import (
    classify_bond,
    classify_equity,
    classify_fund,
    classify_security,
)
from security_master.classifier.crypto_seed import (
    CryptoSeed,
    apply_crypto_seed,
    load_crypto_seed,
)
from security_master.classifier.manual import apply_manual_classification
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
    "CryptoSeed",
    "ManualAssignment",
    "UnknownClassificationValueError",
    "apply_crypto_seed",
    "apply_manual_classification",
    "classify_bond",
    "classify_equity",
    "classify_fund",
    "classify_security",
    "load_crypto_seed",
    "resolve_brx_plus_sleeve",
    "resolve_gics_sector",
]
