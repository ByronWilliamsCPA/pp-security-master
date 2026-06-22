"""Value objects and errors for the classification engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class ClassificationTier(IntEnum):
    """ADR-003 sourcing tier that produced a classification."""

    PP_NATIVE = 1
    PP_CLASSIFIER = 2
    EXTERNAL_API = 3
    MANUAL = 4


class AssignmentKind(Enum):
    """What a manual assignment targets."""

    GICS_SECTOR = "gics_sector"
    SLEEVE = "sleeve"
    CASH = "cash"


@dataclass(frozen=True)
class ManualAssignment:
    """A validated manual classification ready to write.

    Attributes:
        kind: Which taxonomy axis this assignment targets.
        value: The validated, canonical value (GICS sector name or BRX-Plus key).
    """

    kind: AssignmentKind
    value: str


@dataclass(frozen=True)
class ClassificationResult:
    """Outcome of a classification attempt.

    Attributes:
        tier: The tier that produced the result.
        source: Provenance source label (e.g. ``"manual"``).
        locked: Whether the row is now locked against automated overwrite.
    """

    tier: ClassificationTier
    source: str
    locked: bool


class ClassificationLockedError(RuntimeError):
    """Raised when a manual assignment targets a locked row without ``force``."""

    def __init__(
        self,
        *,
        isin: str | None,
        tier: int | None,
        by: str | None,
        at: object,
    ) -> None:
        """Build the error with the existing provenance for the CLI to render.

        Args:
            isin: ISIN of the locked security, if any.
            tier: Existing classification tier on the locked row.
            by: Operator who set the existing classification.
            at: Timestamp of the existing classification.
        """
        self.isin = isin
        self.tier = tier
        self.by = by
        self.at = at
        super().__init__(
            f"security {isin!r} is locked (tier {tier}, by {by} at {at}); "
            f"re-run with --force to override",
        )
