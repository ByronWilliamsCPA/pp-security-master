"""Tier-4 manual classification: the one tier D3 implements.

Honors the override lock (refuses a locked row unless ``force``), writes the
target taxonomy column for the assignment kind, and records full provenance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from security_master.classifier.taxonomy_lookup import (
    CASH_LEVEL1,
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from security_master.storage.models import SecurityMaster

_MANUAL_SOURCE = "manual"
_MANUAL_CONFIDENCE = Decimal("1.00")


def _write_target(security: SecurityMaster, assignment: ManualAssignment) -> None:
    """Write the taxonomy column(s) for the assignment kind.

    Args:
        security: The row to mutate.
        assignment: The validated assignment.
    """
    if assignment.kind is AssignmentKind.GICS_SECTOR:
        security.industries_gics_sectors_level1 = resolve_gics_sector(assignment.value)
    elif assignment.kind is AssignmentKind.SLEEVE:
        level1, leaf = resolve_brx_plus_sleeve(assignment.value)
        security.brx_plus_level1 = level1
        security.brx_plus_level2 = leaf
        security.brx_plus = assignment.value
    else:  # AssignmentKind.CASH
        security.brx_plus_level1 = CASH_LEVEL1


def apply_manual_classification(
    session: Session,
    security: SecurityMaster,
    assignment: ManualAssignment,
    *,
    classified_by: str,
    force: bool = False,
) -> ClassificationResult:
    """Apply a Tier-4 manual classification, honoring the override lock.

    Args:
        session: Active database session (committed by the caller).
        security: The security to classify.
        assignment: The validated manual assignment.
        classified_by: Operator recorded in provenance.
        force: Override an already-locked row when ``True``.

    Returns:
        A ``ClassificationResult`` describing what was written.

    Raises:
        ClassificationLockedError: If the row is locked and ``force`` is ``False``.
    """
    if security.classification_locked and not force:
        raise ClassificationLockedError(
            isin=security.isin,
            tier=security.classification_tier,
            by=security.classified_by,
            at=security.classified_at,
        )

    _write_target(security, assignment)
    security.classification_tier = ClassificationTier.MANUAL
    security.classification_source = _MANUAL_SOURCE
    security.classification_confidence = _MANUAL_CONFIDENCE
    security.classification_locked = True
    security.classified_by = classified_by
    security.classified_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(security)
    return ClassificationResult(
        tier=ClassificationTier.MANUAL,
        source=_MANUAL_SOURCE,
        locked=True,
    )
