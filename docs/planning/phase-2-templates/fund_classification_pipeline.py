"""
Complete Fund Classification Pipeline Implementation
Copy this to: src/security_master/classifier/fund.py
"""

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Add external libraries to path
EXTERNAL_PATH = Path(__file__).parent.parent.parent / "external"
sys.path.insert(0, str(EXTERNAL_PATH))

from ..adapters.pp_classifier_adapter import PPClassifierAdapter
from ..external_apis.openfigi_client import OpenFIGIClient
from ..models.security import SecurityClassification

logger = logging.getLogger(__name__)


class ClassificationSource(Enum):
    """Sources for security classification."""

    PP_PORTFOLIO_CLASSIFIER = "pp-portfolio-classifier"
    OPENFIGI = "openfigi"
    MANUAL = "manual"
    FALLBACK = "fallback"


@dataclass
class ClassificationResult:
    """Result of security classification."""

    security_id: str
    classification: SecurityClassification | None
    confidence: float
    source: ClassificationSource
    metadata: dict[str, Any]
    timestamp: datetime
    processing_time_ms: int
    fallback_applied: bool = False
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class FundClassificationConfig(BaseModel):
    """Configuration for fund classification pipeline."""

    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    enable_fallback: bool = True
    cache_results: bool = True
    batch_size: int = 100
    timeout_seconds: int = 30
    max_retries: int = 3
    enable_openfigi_fallback: bool = True
    enable_manual_review_trigger: bool = True
    manual_review_threshold: float = 0.5


class FundClassificationPipeline:
    """
    Fund classification pipeline using pp-portfolio-classifier with OpenFIGI fallback.

    Classification chain: pp-portfolio-classifier → OpenFIGI → Manual Review
    """

    def __init__(
        self,
        config: FundClassificationConfig | None = None,
        pp_adapter: PPClassifierAdapter | None = None,
        openfigi_client: OpenFIGIClient | None = None,
    ):
        self.config = config or FundClassificationConfig()
        self.pp_adapter = pp_adapter or PPClassifierAdapter()
        self.openfigi_client = openfigi_client or OpenFIGIClient()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Performance tracking
        self.classification_stats = {
            "total_classified": 0,
            "pp_classifier_success": 0,
            "openfigi_success": 0,
            "manual_review_required": 0,
            "errors": 0,
            "average_processing_time_ms": 0.0,
        }

    async def classify_fund(
        self,
        symbol: str,
        name: str | None = None,
        cusip: str | None = None,
        isin: str | None = None,
    ) -> ClassificationResult:
        """
        Classify a single fund using the classification pipeline.

        Args:
            symbol (str): Fund ticker symbol.
            name (str | None): Fund name.
            cusip (str | None): CUSIP identifier.
            isin (str | None): ISIN identifier.

        Returns:
            ClassificationResult: Classification result with confidence and metadata.
        """
        start_time = datetime.now()
        security_id = symbol or cusip or isin

        try:
            # Stage 1: pp-portfolio-classifier
            result = await self._classify_with_pp_classifier(symbol, name, cusip, isin)

            if result.confidence >= self.config.confidence_threshold:
                self._update_stats(result, start_time)
                return result

            # Stage 2: OpenFIGI fallback (if enabled and available)
            if (
                self.config.enable_openfigi_fallback
                and self.openfigi_client
                and result.confidence < self.config.confidence_threshold
            ):

                self.logger.info(
                    f"Low confidence from pp-classifier ({result.confidence:.2f}), trying OpenFIGI",
                )

                fallback_result = await self._classify_with_openfigi(
                    symbol,
                    name,
                    cusip,
                    isin,
                )

                if fallback_result.confidence > result.confidence:
                    fallback_result.fallback_applied = True
                    self._update_stats(fallback_result, start_time)
                    return fallback_result

            # Stage 3: Manual review trigger
            if (
                self.config.enable_manual_review_trigger
                and result.confidence < self.config.manual_review_threshold
            ):

                self.logger.warning(
                    f"Classification confidence too low ({result.confidence:.2f}) "
                    f"for {symbol}, triggering manual review",
                )
                result.metadata["manual_review_required"] = True
                self.classification_stats["manual_review_required"] += 1

            self._update_stats(result, start_time)
            return result

        except Exception as e:
            self.logger.error(f"Classification failed for {symbol}: {e}")
            self.classification_stats["errors"] += 1

            return ClassificationResult(
                security_id=security_id,
                classification=None,
                confidence=0.0,
                source=ClassificationSource.FALLBACK,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000,
                ),
                errors=[str(e)],
            )

    async def classify_batch(
        self,
        securities: list[dict[str, Any]],
    ) -> list[ClassificationResult]:
        """
        Classify multiple securities in batch.

        Args:
            securities (list[dict[str, Any]]): List of security dicts with symbol, name, cusip, isin keys.

        Returns:
            list[ClassificationResult]: List of classification results in input order.
        """
        self.logger.info(
            f"Starting batch classification of {len(securities)} securities",
        )

        # Process in chunks to manage memory and API limits
        results = []
        for i in range(0, len(securities), self.config.batch_size):
            batch = securities[i : i + self.config.batch_size]

            # Create classification tasks
            tasks = []
            for security in batch:
                task = self.classify_fund(
                    symbol=security.get("symbol"),
                    name=security.get("name"),
                    cusip=security.get("cusip"),
                    isin=security.get("isin"),
                )
                tasks.append(task)

            # Execute batch with timeout
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=self.config.timeout_seconds,
                )

                # Handle exceptions in results
                for result in batch_results:
                    if isinstance(result, Exception):
                        self.logger.error(f"Batch classification error: {result}")
                        # Create error result
                        error_result = ClassificationResult(
                            security_id="unknown",
                            classification=None,
                            confidence=0.0,
                            source=ClassificationSource.FALLBACK,
                            metadata={"error": str(result)},
                            timestamp=datetime.now(),
                            processing_time_ms=0,
                            errors=[str(result)],
                        )
                        results.append(error_result)
                    else:
                        results.append(result)

            except TimeoutError:
                self.logger.error(
                    f"Batch classification timeout after {self.config.timeout_seconds}s",
                )
                # Create timeout results
                for security in batch:
                    timeout_result = ClassificationResult(
                        security_id=security.get("symbol", "unknown"),
                        classification=None,
                        confidence=0.0,
                        source=ClassificationSource.FALLBACK,
                        metadata={"error": "timeout"},
                        timestamp=datetime.now(),
                        processing_time_ms=self.config.timeout_seconds * 1000,
                        errors=["Classification timeout"],
                    )
                    results.append(timeout_result)

        self.logger.info(f"Batch classification complete: {len(results)} results")
        return results

    async def _classify_with_pp_classifier(
        self,
        symbol: str | None,
        name: str | None,
        cusip: str | None,
        isin: str | None,
    ) -> ClassificationResult:
        """Classify using pp-portfolio-classifier.

        Args:
            symbol (str | None): Ticker symbol.
            name (str | None): Security name.
            cusip (str | None): CUSIP identifier.
            isin (str | None): ISIN identifier.

        Returns:
            ClassificationResult: Result from pp-portfolio-classifier or error result.
        """
        security_id = symbol or cusip or isin or "unknown"

        if not self.pp_adapter.is_available():
            return ClassificationResult(
                security_id=security_id,
                classification=None,
                confidence=0.0,
                source=ClassificationSource.PP_PORTFOLIO_CLASSIFIER,
                metadata={"error": "pp-portfolio-classifier not available"},
                timestamp=datetime.now(),
                processing_time_ms=0,
                errors=["pp-portfolio-classifier not available"],
            )

        start_time = datetime.now()

        try:
            # Use pp-portfolio-classifier
            pp_result = self.pp_adapter.classify_fund(symbol, name)

            if pp_result:
                # Convert pp-classifier result to our format
                classification = self._convert_pp_result(pp_result)
                confidence = pp_result.get("confidence", 0.8)

                self.classification_stats["pp_classifier_success"] += 1

                return ClassificationResult(
                    security_id=security_id,
                    classification=classification,
                    confidence=confidence,
                    source=ClassificationSource.PP_PORTFOLIO_CLASSIFIER,
                    metadata={"pp_result": pp_result, "symbol": symbol, "name": name},
                    timestamp=datetime.now(),
                    processing_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000,
                    ),
                )
            return ClassificationResult(
                security_id=security_id,
                classification=None,
                confidence=0.0,
                source=ClassificationSource.PP_PORTFOLIO_CLASSIFIER,
                metadata={"error": "No result from pp-portfolio-classifier"},
                timestamp=datetime.now(),
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000,
                ),
                errors=["No result from pp-portfolio-classifier"],
            )

        except Exception as e:
            self.logger.error(f"pp-portfolio-classifier error for {symbol}: {e}")
            return ClassificationResult(
                security_id=security_id,
                classification=None,
                confidence=0.0,
                source=ClassificationSource.PP_PORTFOLIO_CLASSIFIER,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000,
                ),
                errors=[str(e)],
            )

    async def _classify_with_openfigi(
        self,
        symbol: str | None,
        name: str | None,
        cusip: str | None,
        isin: str | None,
    ) -> ClassificationResult:
        """Classify using OpenFIGI API.

        Args:
            symbol (str | None): Ticker symbol.
            name (str | None): Security name.
            cusip (str | None): CUSIP identifier.
            isin (str | None): ISIN identifier.

        Returns:
            ClassificationResult: Result from OpenFIGI or error result.
        """
        security_id = symbol or cusip or isin or "unknown"
        start_time = datetime.now()

        try:
            # Build search parameters
            search_params = {}
            if symbol:
                search_params["symbols"] = [symbol]
            if cusip:
                search_params["cusips"] = [cusip]
            if name:
                search_params["names"] = [name]

            # Search OpenFIGI
            openfigi_results = await self.openfigi_client.search_securities(
                **search_params,
            )

            if openfigi_results:
                # Take the first result and convert it
                figi_result = openfigi_results[0]
                classification = self._convert_openfigi_result(figi_result)

                # Calculate confidence based on match quality
                confidence = self._calculate_openfigi_confidence(
                    figi_result,
                    symbol,
                    name,
                )

                self.classification_stats["openfigi_success"] += 1

                return ClassificationResult(
                    security_id=security_id,
                    classification=classification,
                    confidence=confidence,
                    source=ClassificationSource.OPENFIGI,
                    metadata={
                        "openfigi_result": figi_result,
                        "figi": figi_result.get("figi"),
                        "search_params": search_params,
                    },
                    timestamp=datetime.now(),
                    processing_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000,
                    ),
                )
            return ClassificationResult(
                security_id=security_id,
                classification=None,
                confidence=0.0,
                source=ClassificationSource.OPENFIGI,
                metadata={"error": "No results from OpenFIGI"},
                timestamp=datetime.now(),
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000,
                ),
                errors=["No results from OpenFIGI"],
            )

        except Exception as e:
            self.logger.error(f"OpenFIGI classification error for {symbol}: {e}")
            return ClassificationResult(
                security_id=security_id,
                classification=None,
                confidence=0.0,
                source=ClassificationSource.OPENFIGI,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000,
                ),
                errors=[str(e)],
            )

    def _convert_pp_result(
        self,
        pp_result: dict[str, Any],
    ) -> SecurityClassification | None:
        """Convert pp-portfolio-classifier result to SecurityClassification.

        Args:
            pp_result (dict[str, Any]): Raw result dict from pp-portfolio-classifier.

        Returns:
            SecurityClassification | None: Converted classification or None if data is insufficient.
        """
        # This will be implemented based on actual pp-portfolio-classifier output format
        classification_data = pp_result.get("classification", {})

        return SecurityClassification(
            asset_class=classification_data.get("asset_class", "Fund"),
            sector=classification_data.get("sector"),
            industry=classification_data.get("industry"),
            geographic_focus=classification_data.get("geographic_focus"),
            investment_style=classification_data.get("investment_style"),
            fund_type=classification_data.get("fund_type", "ETF"),
            classification_source="pp-portfolio-classifier",
        )

    def _convert_openfigi_result(
        self,
        figi_result: dict[str, Any],
    ) -> SecurityClassification | None:
        """Convert OpenFIGI result to SecurityClassification.

        Args:
            figi_result (dict[str, Any]): Raw result dict from OpenFIGI API.

        Returns:
            SecurityClassification | None: Converted classification or None if data is insufficient.
        """
        return SecurityClassification(
            asset_class=figi_result.get("securityType", "Unknown"),
            sector=figi_result.get("sector"),
            industry=figi_result.get("industry"),
            geographic_focus=figi_result.get(
                "exchCode",
            ),  # Exchange as geographic indicator
            market_cap=figi_result.get("marketCap"),
            exchange=figi_result.get("exchCode"),
            figi=figi_result.get("figi"),
            classification_source="openfigi",
        )

    def _calculate_openfigi_confidence(
        self,
        figi_result: dict[str, Any],
        symbol: str | None,
        name: str | None,
    ) -> float:
        """Calculate confidence score for OpenFIGI result.

        Args:
            figi_result (dict[str, Any]): Raw result dict from OpenFIGI API.
            symbol (str | None): Ticker symbol used in the search.
            name (str | None): Security name used in the search.

        Returns:
            float: Confidence score between 0.0 and 1.0.
        """
        confidence = 0.6  # Base confidence for OpenFIGI

        # Boost confidence if symbol matches exactly
        if symbol and figi_result.get("ticker") == symbol:
            confidence += 0.2

        # Boost confidence if name similarity is high
        if name and figi_result.get("name"):
            # Simple name similarity (could be enhanced with fuzzy matching)
            if name.lower() in figi_result.get("name", "").lower():
                confidence += 0.1

        # Boost confidence if we have complete data
        if all(
            figi_result.get(field)
            for field in ["figi", "ticker", "name", "securityType"]
        ):
            confidence += 0.1

        return min(confidence, 1.0)

    def _update_stats(self, result: ClassificationResult, start_time: datetime):
        """Update classification statistics.

        Args:
            result (ClassificationResult): Completed classification result to record.
            start_time (datetime): Timestamp when classification started.
        """
        self.classification_stats["total_classified"] += 1

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        # Update average processing time
        total_time = self.classification_stats["average_processing_time_ms"] * (
            self.classification_stats["total_classified"] - 1
        )
        total_time += processing_time
        self.classification_stats["average_processing_time_ms"] = (
            total_time / self.classification_stats["total_classified"]
        )

    def get_performance_stats(self) -> dict[str, Any]:
        """Get classification performance statistics.

        Returns:
            dict[str, Any]: Statistics dict including rates for pp_classifier_success, openfigi_success, errors.
        """
        total = self.classification_stats["total_classified"]
        if total == 0:
            return self.classification_stats.copy()

        stats = self.classification_stats.copy()
        stats["pp_classifier_success_rate"] = stats["pp_classifier_success"] / total
        stats["openfigi_success_rate"] = stats["openfigi_success"] / total
        stats["manual_review_rate"] = stats["manual_review_required"] / total
        stats["error_rate"] = stats["errors"] / total

        return stats

    def reset_stats(self):
        """Reset performance statistics."""
        self.classification_stats = {
            "total_classified": 0,
            "pp_classifier_success": 0,
            "openfigi_success": 0,
            "manual_review_required": 0,
            "errors": 0,
            "average_processing_time_ms": 0.0,
        }


async def main():
    """Example usage of fund classification pipeline."""
    logging.basicConfig(level=logging.INFO)

    # Configure pipeline
    config = FundClassificationConfig(
        confidence_threshold=0.7,
        enable_fallback=True,
        batch_size=50,
    )

    pipeline = FundClassificationPipeline(config)

    # Example: Classify a single fund
    result = await pipeline.classify_fund(symbol="SPY", name="SPDR S&P 500 ETF Trust")

    print("Classification result for SPY:")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Source: {result.source.value}")
    print(f"  Classification: {result.classification}")
    print(f"  Processing time: {result.processing_time_ms}ms")

    # Example: Batch classification
    securities = [
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust"},
        {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF"},
        {"symbol": "BND", "name": "Vanguard Total Bond Market ETF"},
    ]

    batch_results = await pipeline.classify_batch(securities)

    print("\nBatch classification results:")
    for result in batch_results:
        print(
            f"  {result.security_id}: {result.confidence:.2f} ({result.source.value})",
        )

    # Performance statistics
    stats = pipeline.get_performance_stats()
    print("\nPerformance statistics:")
    print(f"  Total classified: {stats['total_classified']}")
    print(f"  Average processing time: {stats['average_processing_time_ms']:.1f}ms")
    print(f"  Success rate: {(1 - stats['error_rate']):.1%}")


if __name__ == "__main__":
    asyncio.run(main())
