"""Tier-3 listed-equity classification (ADR-003 Tier 3, ADR-005).

OpenFIGI confirms the instrument is an equity and validates identity; the GICS
sector comes from the row's provider sector (resolve_gics_from_provider) or, as a
free fallback, from a SEC EDGAR SIC code (resolve_gics_from_sic_naics). Mirrors
manual.py: honors the override lock, writes provenance, but never sets the lock
(only Tier-4 manual locks a row).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from security_master.classifier.taxonomy_lookup import (
    UnknownClassificationValueError,
    resolve_gics_sector_by_code,
)
from security_master.classifier.types import ClassificationResult, ClassificationTier
from security_master.crosswalk import (
    resolve_gics_from_provider,
    resolve_gics_from_sic_naics,
)
from security_master.external.errors import ExternalAPIError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from security_master.external.openfigi import OpenFIGIRecord
    from security_master.storage.models import SecurityMaster

_TIER3_CONFIDENCE = Decimal("0.80")  # ADR-003 Tier-3 band (below Tier-2 >= 0.90)
_AUTO = "auto"


class _OpenFIGI(Protocol):
    """Structural type for the OpenFIGI dependency (eases test stubbing)."""

    def map_identifier(
        self, *, isin: str | None = ..., symbol: str | None = ...
    ) -> OpenFIGIRecord | None: ...


class _Edgar(Protocol):
    """Structural type for the SEC EDGAR dependency."""

    def sic_for_symbol(self, symbol: str) -> str | None: ...


def classify_equity(
    session: Session,
    security: SecurityMaster,
    *,
    openfigi: _OpenFIGI,
    edgar: _Edgar,
) -> ClassificationResult | None:
    """Classify a listed equity's GICS sector, honoring the override lock.

    Args:
        session: Active database session (committed by the caller).
        security: The security to classify.
        openfigi: OpenFIGI client (identity + instrument-type confirmation).
        edgar: SEC EDGAR client (SIC fallback for US issuers).

    Returns:
        A ``ClassificationResult`` when a GICS sector was assigned, or ``None``
        when the row is locked, is not an equity, or no sector resolved (the
        caller then tries the next tier or queues for manual classification).
    """
    if security.classification_locked:
        return None  # never overwrite a human (Tier-4) classification

    record = _safe_map(openfigi, security)
    if record is None or not record.is_equity():
        return None

    resolved = _resolve_sector(security, edgar)
    if resolved is None:
        return None
    gics_code, source = resolved
    try:
        sector_name = resolve_gics_sector_by_code(gics_code)
    except UnknownClassificationValueError:
        return None  # crosswalk produced a code the taxonomy does not know

    security.industries_gics_sectors_level1 = sector_name
    security.classification_tier = ClassificationTier.EXTERNAL_API
    security.classification_source = source
    security.classification_confidence = _TIER3_CONFIDENCE
    security.classified_by = _AUTO
    # #ASSUME (data integrity): naive-UTC, matching the other timestamp columns.
    security.classified_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(security)
    return ClassificationResult(
        tier=ClassificationTier.EXTERNAL_API, source=source, locked=False
    )


def _safe_map(openfigi: _OpenFIGI, security: SecurityMaster) -> OpenFIGIRecord | None:
    """Map the security via OpenFIGI, degrading to ``None`` on API failure.

    Args:
        openfigi: OpenFIGI client.
        security: The security being classified.

    Returns:
        The mapped record, or ``None`` on no match / API outage.
    """
    if not (security.isin or security.symbol):
        return None
    try:
        return openfigi.map_identifier(isin=security.isin, symbol=security.symbol)
    except ExternalAPIError:
        return None  # graceful degradation: never crash the batch


def _resolve_sector(security: SecurityMaster, edgar: _Edgar) -> tuple[str, str] | None:
    """Resolve a GICS sector code and its provenance source label.

    Args:
        security: The security being classified.
        edgar: SEC EDGAR client (SIC fallback).

    Returns:
        A ``(gics_code, source_label)`` tuple, or ``None`` when unresolved.
    """
    if security.sector:
        gics = resolve_gics_from_provider(security.sector)
        if gics is not None:
            return gics, "provider-sector"
    if security.symbol:
        try:
            sic = edgar.sic_for_symbol(security.symbol)
        except ExternalAPIError:
            sic = None  # graceful degradation
        if sic:
            gics = resolve_gics_from_sic_naics(sic=sic)
            if gics is not None:
                return gics, "edgar-sic"
    return None
