"""
Complete Wells Fargo CSV Parser Implementation
Copy this to: src/security_master/extractor/wells_fargo/parser.py
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID

from ...batch.models import Institution
from ...batch.service import BatchManager
from .models import WellsFargoTransaction

logger = logging.getLogger(__name__)


class WellsFargoParseResult:
    """Result of Wells Fargo CSV parsing operation."""

    def __init__(self, batch_id: UUID):
        self.batch_id = batch_id
        self.total_rows = 0
        self.valid_transactions: list[WellsFargoTransaction] = []
        self.invalid_transactions: list[tuple[int, dict, str]] = (
            []
        )  # (row_num, raw_data, error)
        self.duplicate_transactions: list[WellsFargoTransaction] = []
        self.processing_errors: list[str] = []

    @property
    def success_count(self) -> int:
        return len(self.valid_transactions)

    @property
    def error_count(self) -> int:
        return len(self.invalid_transactions)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicate_transactions)

    @property
    def success_rate(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return self.success_count / self.total_rows


class WellsFargoParser:
    """Wells Fargo CSV transaction parser with validation and error handling."""

    def __init__(self, batch_manager: BatchManager = None):
        self.batch_manager = batch_manager or BatchManager()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def parse_file(
        self,
        file_path: Path,
        created_by: str = "system",
    ) -> WellsFargoParseResult:
        """Parse Wells Fargo CSV file with comprehensive validation.

        Args:
            file_path (Path): Path to the Wells Fargo CSV file to parse.
            created_by (str): Username or system identifier for audit tracking.

        Returns:
            WellsFargoParseResult: Parsed result containing valid, invalid, and duplicate transactions.

        Raises:
            Exception: If an error occurs.
        """

        # Create import batch
        batch = self.batch_manager.create_batch(
            institution=Institution.WELLS_FARGO,
            file_path=file_path,
            created_by=created_by,
        )

        result = WellsFargoParseResult(batch.id)

        try:
            # Start processing
            self.batch_manager.start_processing(batch.id)

            # Parse CSV file
            self._parse_csv_content(file_path, result)

            # Process transactions (validation, deduplication, etc.)
            self._process_transactions(result)

            # Complete batch with statistics
            statistics = {
                "total_records": result.total_rows,
                "valid_records": result.success_count,
                "invalid_records": result.error_count,
                "duplicate_records": result.duplicate_count,
                "skipped_records": 0,
            }

            # Calculate overall data quality score
            if result.valid_transactions:
                quality_scores = [
                    t.calculate_data_quality_score() for t in result.valid_transactions
                ]
                avg_quality_score = sum(quality_scores) / len(quality_scores)
            else:
                avg_quality_score = 0.0

            self.batch_manager.complete_batch(
                batch.id,
                statistics,
                data_quality_score=avg_quality_score,
            )

            self.logger.info(
                f"Parsed Wells Fargo file {file_path.name}: "
                f"{result.success_count}/{result.total_rows} successful, "
                f"{result.error_count} errors, {result.duplicate_count} duplicates",
            )

        except Exception as e:
            self.logger.error(f"Failed to parse Wells Fargo file {file_path}: {e}")
            self.batch_manager.fail_batch(batch.id, str(e))
            result.processing_errors.append(str(e))
            raise

        return result

    def _parse_csv_content(self, file_path: Path, result: WellsFargoParseResult):
        """Parse CSV file content into transaction objects.

        Args:
            file_path (Path): Path to the CSV file to read.
            result (WellsFargoParseResult): Parse result object to populate with transactions.
        """

        with open(file_path, encoding="utf-8") as csvfile:
            # Detect delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)

            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter

            reader = csv.DictReader(csvfile, delimiter=delimiter)

            for row_number, row_data in enumerate(
                reader,
                start=2,
            ):  # Start at 2 (header is row 1)
                result.total_rows += 1

                try:
                    # Clean and prepare row data
                    cleaned_data = self._clean_row_data(row_data)

                    # Parse transaction
                    transaction = WellsFargoTransaction(**cleaned_data)
                    transaction.raw_line_number = row_number

                    result.valid_transactions.append(transaction)

                except Exception as e:
                    error_msg = f"Row {row_number}: {e!s}"
                    result.invalid_transactions.append(
                        (row_number, row_data, error_msg),
                    )
                    self.logger.warning(error_msg)

    def _clean_row_data(self, row_data: dict[str, str]) -> dict[str, any]:
        """Clean and normalize CSV row data.

        Args:
            row_data (dict[str, str]): Raw CSV row dict with string keys and values.

        Returns:
            dict[str, any]: Cleaned row with type-converted values and stripped whitespace.
        """
        cleaned = {}

        for key, value in row_data.items():
            if not key or not value:
                continue

            # Clean whitespace
            clean_key = key.strip()
            clean_value = value.strip()

            # Handle empty values
            if not clean_value or clean_value.lower() in ("", "n/a", "null", "none"):
                cleaned[clean_key] = None
                continue

            # Type conversions based on expected data types
            if "date" in clean_key.lower():
                try:
                    # Try common date formats
                    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"]:
                        try:
                            cleaned[clean_key] = datetime.strptime(
                                clean_value,
                                fmt,
                            ).date()
                            break
                        except ValueError:
                            continue
                    else:
                        # If no format worked, keep as string and let Pydantic handle it
                        cleaned[clean_key] = clean_value
                except Exception:
                    cleaned[clean_key] = clean_value

            elif any(
                word in clean_key.lower()
                for word in ["amount", "price", "quantity", "commission", "fees"]
            ):
                try:
                    # Remove currency symbols and commas
                    numeric_value = (
                        clean_value.replace("$", "")
                        .replace(",", "")
                        .replace("(", "-")
                        .replace(")", "")
                    )
                    cleaned[clean_key] = (
                        float(numeric_value)
                        if "." in numeric_value
                        else int(numeric_value)
                    )
                except ValueError:
                    cleaned[clean_key] = clean_value

            else:
                cleaned[clean_key] = clean_value

        return cleaned

    def _process_transactions(self, result: WellsFargoParseResult):
        """Process parsed transactions for validation and deduplication.

        Args:
            result (WellsFargoParseResult): Parse result object to process in place.
        """

        # Detect duplicates within the file
        seen_transactions = set()
        unique_transactions = []

        for transaction in result.valid_transactions:
            # Create a signature for duplicate detection
            signature = self._create_transaction_signature(transaction)

            if signature in seen_transactions:
                result.duplicate_transactions.append(transaction)
                self.logger.warning(f"Duplicate transaction detected: {signature}")
            else:
                seen_transactions.add(signature)
                unique_transactions.append(transaction)

        result.valid_transactions = unique_transactions

        # Additional business rule validations
        self._validate_business_rules(result)

    def _create_transaction_signature(self, transaction: WellsFargoTransaction) -> str:
        """Create a unique signature for transaction deduplication.

        Args:
            transaction (WellsFargoTransaction): Transaction to generate a deduplication key for.

        Returns:
            str: Pipe-delimited string combining key transaction fields.
        """
        signature_parts = [
            transaction.account_number,
            str(transaction.transaction_date),
            transaction.transaction_type,
            transaction.symbol or "",
            str(transaction.quantity or 0),
            str(transaction.net_amount or 0),
        ]
        return "|".join(signature_parts)

    def _validate_business_rules(self, result: WellsFargoParseResult):
        """Apply business rule validations to transactions.

        Args:
            result (WellsFargoParseResult): Parse result object to validate in place.
        """

        validated_transactions = []

        for transaction in result.valid_transactions:
            validation_errors = []

            # Business rule 1: Buy/Sell transactions must have security information
            if transaction.transaction_type in ["Buy", "Sell"]:
                if not any(
                    [
                        transaction.symbol,
                        transaction.cusip,
                        transaction.security_description,
                    ],
                ):
                    validation_errors.append(
                        "Buy/Sell transaction missing security identification",
                    )

            # Business rule 2: Quantity and price should be consistent with principal
            if all(
                [transaction.quantity, transaction.price, transaction.principal_amount],
            ):
                expected_principal = abs(transaction.quantity * transaction.price)
                actual_principal = abs(transaction.principal_amount)
                if (
                    abs(expected_principal - actual_principal) > 0.05
                ):  # 5 cent tolerance
                    validation_errors.append(
                        f"Principal amount mismatch: expected {expected_principal}, got {actual_principal}",
                    )

            # Business rule 3: Settlement date should be on or after transaction date
            if (
                transaction.settlement_date
                and transaction.settlement_date < transaction.transaction_date
            ):
                validation_errors.append(
                    "Settlement date cannot be before transaction date",
                )

            if validation_errors:
                # Convert to invalid transaction
                row_data = transaction.dict()
                error_msg = "; ".join(validation_errors)
                result.invalid_transactions.append(
                    (
                        transaction.raw_line_number,
                        row_data,
                        f"Business rule validation failed: {error_msg}",
                    ),
                )
                self.logger.warning(f"Transaction validation failed: {error_msg}")
            else:
                validated_transactions.append(transaction)

        result.valid_transactions = validated_transactions

    def get_supported_columns(self) -> list[str]:
        """Get list of supported Wells Fargo CSV columns.

        Returns:
            list[str]: List of expected Wells Fargo CSV column header names.
        """
        return [
            "Account Number",
            "Account Type",
            "Transaction Date",
            "Settlement Date",
            "Transaction Type",
            "Security Description",
            "Symbol",
            "CUSIP",
            "Quantity",
            "Price",
            "Principal Amount",
            "Commission",
            "Fees",
            "Net Amount",
        ]
