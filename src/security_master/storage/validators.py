"""Validation logic and data-quality scoring for SecurityMaster records."""

import re
from decimal import Decimal

from .models import SecurityMaster


class SecurityDataValidator:
    """Validates security data for quality and completeness."""

    # ISIN validation pattern
    ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

    # WKN validation pattern (German securities)
    WKN_PATTERN = re.compile(r"^[A-Z0-9]{6}$")

    # Symbol validation (basic pattern)
    SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._-]{1,20}$")

    @classmethod
    def validate_isin(cls, isin: str | None) -> bool:
        """Validate ISIN format and check digit.

        Args:
            isin: ISIN string to validate, or None for optional fields.

        Returns:
            True when isin is None, empty, or passes format and check-digit
            validation. False when format or check digit is invalid.
        """
        if not isin:
            return True  # Optional field

        if not cls.ISIN_PATTERN.match(isin):
            return False

        # ISIN check digit validation
        chars: list[str] = []
        for char in isin[:-1]:
            if char.isdigit():
                chars.append(char)
            else:
                chars.extend(str(ord(char) - ord("A") + 10))

        # ISO 6166 check digit: Luhn (modulus 10 "double-add-double"). Walking
        # right-to-left over the converted digits, double every second digit and
        # reduce any two-digit product to its digit sum (e.g. 7*2=14 -> 1+4=5).
        # For a single decimal digit, subtracting 9 from the doubled value equals
        # that digit sum, since 2*d in 10..18 maps to (2*d) - 9.
        num_str = "".join(chars)
        check_sum = 0
        for i, digit in enumerate(reversed(num_str)):
            value = int(digit)
            if i % 2 == 0:
                value *= 2
                if value > 9:
                    value -= 9
            check_sum += value

        return (10 - (check_sum % 10)) % 10 == int(isin[-1])

    @classmethod
    def validate_wkn(cls, wkn: str | None) -> bool:
        """Validate WKN format.

        Args:
            wkn: WKN string to validate, or None for optional fields.

        Returns:
            True when wkn is None, empty, or matches the 6-character alphanumeric
            pattern. False when the format is invalid.
        """
        if not wkn:
            return True  # Optional field
        return bool(cls.WKN_PATTERN.match(wkn))

    @classmethod
    def validate_symbol(cls, symbol: str | None) -> bool:
        """Validate trading symbol format.

        Args:
            symbol: Ticker symbol to validate, or None for optional fields.

        Returns:
            True when symbol is None, empty, or matches the allowed pattern.
            False when the format is invalid.
        """
        if not symbol:
            return True  # Optional field
        return bool(cls.SYMBOL_PATTERN.match(symbol))

    @classmethod
    def validate_currency(cls, currency: str) -> bool:
        """Validate currency code (ISO 4217).

        Args:
            currency: Three-letter currency code to validate.

        Returns:
            True when currency is a non-empty 3-character uppercase string.
            False otherwise.
        """
        return bool(
            currency
            and len(currency) == 3
            and currency.isalpha()
            and currency.isupper()
        )

    @classmethod
    def _identification_score(cls, security: SecurityMaster) -> Decimal:
        """Score core identification fields (name, ISIN, symbol, WKN) at 40% weight.

        Args:
            security: SecurityMaster record to score.

        Returns:
            Decimal contribution (0.0 to 0.4) from identification completeness.
        """
        earned = 0
        total = 5  # 1 name + 2 ISIN + 1 symbol + 1 WKN

        if security.name:
            earned += 1
        if cls.validate_isin(security.isin) and security.isin:
            earned += 2  # ISIN is most important
        if cls.validate_symbol(security.symbol) and security.symbol:
            earned += 1
        if cls.validate_wkn(security.wkn) and security.wkn:
            earned += 1

        return Decimal(str(earned / total * 0.4))

    @classmethod
    def _pricing_score(cls, security: SecurityMaster) -> Decimal:
        """Score pricing data fields (price, date, currency) at 20% weight.

        Args:
            security: SecurityMaster record to score.

        Returns:
            Decimal contribution (0.0 to 0.2) from pricing completeness.
        """
        earned = 0
        total = 3

        if security.latest_price is not None:
            earned += 1
        if security.latest_date:
            earned += 1
        if security.currency and cls.validate_currency(security.currency):
            earned += 1

        return Decimal(str(earned / total * 0.2))

    @classmethod
    def _classification_and_source_score(cls, security: SecurityMaster) -> Decimal:
        """Score classification fields (30%) and data source fields (10%).

        Args:
            security: SecurityMaster record to score.

        Returns:
            Decimal contribution (0.0 to 0.4) from classification and source completeness.
        """
        classification_fields = [
            security.sector,
            security.type_of_security_level1,
            security.asset_classes_level1,
            security.region,
            security.market,
        ]
        classification_total = len(classification_fields)
        classification_earned = sum(1 for f in classification_fields if f)
        classification_contribution = Decimal(
            str(classification_earned / classification_total * 0.3)
        )

        source_earned = sum(
            [bool(security.quote_feed_latest), bool(security.data_source)]
        )
        source_contribution = Decimal(str(source_earned / 2 * 0.1))

        return classification_contribution + source_contribution

    @classmethod
    def calculate_data_quality_score(cls, security: SecurityMaster) -> Decimal:
        """Calculate data quality score (0.00-1.00) based on completeness and validity.

        Args:
            security: SecurityMaster record to score.

        Returns:
            Decimal score between 0.00 and 1.00 representing data quality,
            weighted across identification, pricing, classification, and source fields.
        """
        score = (
            cls._identification_score(security)
            + cls._pricing_score(security)
            + cls._classification_and_source_score(security)
        )
        return min(score, Decimal("1.00"))

    @classmethod
    def validate_security(cls, security: SecurityMaster) -> tuple[bool, list[str]]:
        """Validate a security record and return validation status and errors.

        Args:
            security: SecurityMaster record to validate.

        Returns:
            Tuple of (is_valid, errors) where is_valid is True when no errors
            were found and errors is a list of human-readable error messages.
        """
        errors: list[str] = []

        # Required fields
        if not security.name:
            errors.append("Name is required")

        if not security.currency:
            errors.append("Currency is required")
        elif not cls.validate_currency(security.currency):
            errors.append(f"Invalid currency code: {security.currency}")

        # Format validations
        if not cls.validate_isin(security.isin):
            errors.append(f"Invalid ISIN: {security.isin}")

        if not cls.validate_wkn(security.wkn):
            errors.append(f"Invalid WKN: {security.wkn}")

        if not cls.validate_symbol(security.symbol):
            errors.append(f"Invalid symbol: {security.symbol}")

        # Business rule validations
        if security.latest_price is not None and security.latest_price < 0:
            errors.append("Latest price cannot be negative")

        if security.ter is not None and (security.ter < 0 or security.ter > 10):
            errors.append("TER must be between 0% and 10%")

        return len(errors) == 0, errors
