"""Load and apply the committed crypto classification seed.

The seed is the user's own crypto scheme (ADR-015 section 4), read packaged-first
then repo-root-fallback, mirroring ``crosswalk.py``. Applying it assigns the
mapped BRX-Plus sleeve via the Tier-4 manual path, so it honors the override lock
and writes provenance like any other manual assignment.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, cast

import yaml
from sqlalchemy import select

from security_master.classifier.manual import apply_manual_classification
from security_master.classifier.types import AssignmentKind, ManualAssignment
from security_master.storage.models import SecurityMaster

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import Session

_REPO_SEED_DIR = Path(__file__).resolve().parents[3] / "seeds"
_SEED_FILE = "crypto_classification.yaml"


@dataclass(frozen=True)
class CryptoSeed:
    """Parsed crypto seed.

    Attributes:
        by_symbol: Mapping of crypto symbol to BRX-Plus leaf key.
        default: Fallback BRX-Plus leaf key for unlisted crypto symbols.
    """

    by_symbol: dict[str, str]
    default: str


def _read_seed(name: str) -> str:
    """Read the seed text packaged-first, repo-root-fallback.

    Args:
        name: File name within the seeds directory.

    Returns:
        The file's UTF-8 text.
    """
    packaged = resources.files("security_master") / "seeds" / name
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")
    return (_REPO_SEED_DIR / name).read_text(encoding="utf-8")


@cache
def load_crypto_seed() -> CryptoSeed:
    """Load and cache the committed crypto seed.

    Returns:
        The parsed ``CryptoSeed``.
    """
    doc = cast("dict[str, object]", yaml.safe_load(_read_seed(_SEED_FILE)))
    by_symbol = cast("dict[str, str]", doc.get("by_symbol", {}))
    return CryptoSeed(by_symbol=dict(by_symbol), default=str(doc.get("default", "")))


def apply_crypto_seed(
    session: Session,
    *,
    classified_by: str,
    symbols: Sequence[str] | None = None,
    force: bool = False,
) -> int:
    """Assign crypto sleeves to securities whose symbol the seed covers.

    Args:
        session: Active database session. Assignments are flushed so they are
            queryable within the transaction; the caller still owns the commit.
        classified_by: Operator recorded in provenance.
        symbols: Extra symbols to treat as crypto (assigned the seed ``default``
            when not in ``by_symbol``). Defaults to the seed's own symbols.
        force: Override locked rows when ``True``.

    Returns:
        The number of securities assigned.
    """
    seed = load_crypto_seed()
    targets = set(seed.by_symbol) | set(symbols or [])
    assigned = 0
    rows = session.scalars(
        select(SecurityMaster).where(SecurityMaster.symbol.in_(targets)),
    ).all()
    for sec in rows:
        if sec.classification_locked and not force:
            continue
        key = seed.by_symbol.get(sec.symbol or "", seed.default)
        apply_manual_classification(
            session,
            sec,
            ManualAssignment(AssignmentKind.SLEEVE, key),
            classified_by=classified_by,
            force=force,
        )
        assigned += 1
    session.flush()
    return assigned
