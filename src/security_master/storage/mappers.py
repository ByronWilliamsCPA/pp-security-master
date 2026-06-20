"""Portfolio Performance mapping managers and security-matching utilities for Kubera data."""

from typing import Any

from sqlalchemy.orm import Session

from .models import KuberaSection, KuberaSheet


class PortfolioMappingManager:
    """Manages mappings between Kubera sheets/sections and Portfolio Performance groups/accounts."""

    def __init__(self, session: Session) -> None:
        self.session = session

        # Default mappings based on common patterns
        self.default_sheet_mappings = {
            "IRA": "IRA",
            "SDIRA": "Self-Directed IRA",
            "Crypto": "Crypto",
            "Real Estate": "Real Estate",
            "Residence": "Residence",
            "Loans": "Liabilities",
            "Other Assets": "Other Assets",
            "Annuity": "Annuity",
        }

        # Common section to account mappings
        self.default_section_mappings = {
            "Wells fargo": "Wells Fargo",
            "Interactive Brokers": "Interactive Brokers",
            "AltoIRA": "AltoIRA",
            "Prudential": "Prudential",
            "Equity Trust Metals": "Equity Trust Metals",
            "WFF SD IRA": "WFF SD IRA",
            "WFF SD IRA LLC": "WFF SD IRA LLC",
        }

    def get_or_create_sheet_mapping(
        self,
        sheet_id: str,
        sheet_name: str,
    ) -> KuberaSheet:
        """Get existing sheet mapping or create new one with default PP group mapping.

        Args:
            sheet_id: Unique identifier for the Kubera sheet.
            sheet_name: Human-readable name of the Kubera sheet.

        Returns:
            Existing or newly created KuberaSheet ORM instance.
        """
        sheet = self.session.query(KuberaSheet).filter_by(sheet_id=sheet_id).first()

        if not sheet:
            pp_group = self.default_sheet_mappings.get(sheet_name, sheet_name)
            sheet = KuberaSheet(
                sheet_id=sheet_id,
                sheet_name=sheet_name,
                pp_group_name=pp_group,
            )
            self.session.add(sheet)
            self.session.flush()  # Get the ID

        return sheet

    def get_or_create_section_mapping(
        self,
        section_id: str,
        section_name: str,
        sheet: KuberaSheet,
    ) -> KuberaSection:
        """Get existing section mapping or create new one with default PP account mapping.

        Args:
            section_id: Unique identifier for the Kubera section.
            section_name: Human-readable name of the Kubera section.
            sheet: Parent KuberaSheet that owns this section.

        Returns:
            Existing or newly created KuberaSection ORM instance.
        """
        section = (
            self.session.query(KuberaSection).filter_by(section_id=section_id).first()
        )

        if not section:
            pp_account = self.default_section_mappings.get(section_name, section_name)
            section = KuberaSection(
                section_id=section_id,
                section_name=section_name,
                sheet_id=sheet.id,
                pp_account_name=pp_account,
            )
            self.session.add(section)
            self.session.flush()  # Get the ID

        return section

    def update_sheet_mapping(self, sheet_id: str, pp_group_name: str) -> bool:
        """Update the Portfolio Performance group mapping for a sheet.

        Args:
            sheet_id: Unique identifier for the Kubera sheet to update.
            pp_group_name: Portfolio Performance group name to assign.

        Returns:
            True when the sheet was found and updated. False when not found.
        """
        sheet = self.session.query(KuberaSheet).filter_by(sheet_id=sheet_id).first()
        if sheet:
            sheet.pp_group_name = pp_group_name
            return True
        return False

    def update_section_mapping(self, section_id: str, pp_account_name: str) -> bool:
        """Update the Portfolio Performance account mapping for a section.

        Args:
            section_id: Unique identifier for the Kubera section to update.
            pp_account_name: Portfolio Performance account name to assign.

        Returns:
            True when the section was found and updated. False when not found.
        """
        section = (
            self.session.query(KuberaSection).filter_by(section_id=section_id).first()
        )
        if section:
            section.pp_account_name = pp_account_name
            return True
        return False

    def get_pp_mapping(
        self,
        sheet_id: str,
        section_id: str,
    ) -> tuple[str | None, str | None]:
        """Get Portfolio Performance group and account names for a Kubera sheet/section.

        Args:
            sheet_id: Unique identifier for the Kubera sheet.
            section_id: Unique identifier for the Kubera section.

        Returns:
            Tuple of (pp_group_name, pp_account_name). Both elements are None
            when no matching mapping exists.
        """
        section = (
            self.session.query(KuberaSection)
            .join(KuberaSheet)
            .filter(KuberaSheet.sheet_id == sheet_id)
            .filter(KuberaSection.section_id == section_id)
            .first()
        )

        if section and section.sheet:
            return section.sheet.pp_group_name, section.pp_account_name

        return None, None

    def list_unmapped_sheets(self) -> list[KuberaSheet]:
        """Get list of sheets without Portfolio Performance group mappings.

        Returns:
            List of KuberaSheet instances where pp_group_name is None.
        """
        return (
            self.session.query(KuberaSheet)
            .filter(KuberaSheet.pp_group_name.is_(None))
            .all()
        )

    def list_unmapped_sections(self) -> list[KuberaSection]:
        """Get list of sections without Portfolio Performance account mappings.

        Returns:
            List of KuberaSection instances where pp_account_name is None.
        """
        return (
            self.session.query(KuberaSection)
            .filter(KuberaSection.pp_account_name.is_(None))
            .all()
        )

    def get_mapping_summary(self) -> dict[str, dict[str, Any]]:
        """Get summary of all current mappings.

        Returns:
            Nested dict keyed by sheet name, where each value contains
            pp_group and a sections sub-dict mapping section names to
            their pp_account values.
        """
        mappings: dict[str, dict[str, Any]] = {}

        sheets = self.session.query(KuberaSheet).all()
        for sheet in sheets:
            sheet_mapping: dict[str, Any] = {
                "pp_group": sheet.pp_group_name,
                "sections": {},
            }

            for section in sheet.sections:
                sheet_mapping["sections"][section.section_name] = {
                    "pp_account": section.pp_account_name,
                }

            mappings[sheet.sheet_name] = sheet_mapping

        return mappings


class SecurityMatcher:
    """Matches securities between Portfolio Performance and Kubera holdings."""

    @staticmethod
    def match_by_isin(pp_isin: str, kubera_isin: str) -> bool:
        """Match securities by ISIN (most reliable).

        Args:
            pp_isin: ISIN from the Portfolio Performance security.
            kubera_isin: ISIN from the Kubera holding.

        Returns:
            True when both ISINs are non-empty and match case-insensitively.
        """
        if not pp_isin or not kubera_isin:
            return False
        return pp_isin.upper().strip() == kubera_isin.upper().strip()

    @staticmethod
    def match_by_ticker(pp_symbol: str, kubera_ticker: str) -> bool:
        """Match securities by ticker/symbol.

        Args:
            pp_symbol: Ticker symbol from the Portfolio Performance security.
            kubera_ticker: Ticker from the Kubera holding.

        Returns:
            True when both values are non-empty and match case-insensitively.
        """
        if not pp_symbol or not kubera_ticker:
            return False
        return pp_symbol.upper().strip() == kubera_ticker.upper().strip()

    @staticmethod
    def match_by_name(pp_name: str, kubera_name: str, threshold: float = 0.8) -> bool:
        """Match securities by name similarity (fuzzy matching).

        Args:
            pp_name: Security name from Portfolio Performance.
            kubera_name: Holding name from Kubera.
            threshold: Minimum word-overlap ratio to consider a match. Defaults to 0.8.

        Returns:
            True when names match exactly, one contains the other, or word-overlap
            ratio meets the threshold. False when either name is empty or below threshold.
        """
        if not pp_name or not kubera_name:
            return False

        # Simple similarity check - could be enhanced with libraries like fuzzywuzzy
        pp_clean = pp_name.upper().strip()
        kubera_clean = kubera_name.upper().strip()

        # Exact match
        if pp_clean == kubera_clean:
            return True

        # Check if one name contains the other
        if pp_clean in kubera_clean or kubera_clean in pp_clean:
            return True

        # Simple word overlap check
        pp_words = set(pp_clean.split())
        kubera_words = set(kubera_clean.split())

        if len(pp_words) == 0 or len(kubera_words) == 0:
            return False

        overlap = len(pp_words.intersection(kubera_words))
        max_words = max(len(pp_words), len(kubera_words))

        return (overlap / max_words) >= threshold

    @classmethod
    def find_best_match(
        cls,
        pp_security: dict[str, Any],
        kubera_holdings: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Find the best matching Kubera holding for a Portfolio Performance security.

        Args:
            pp_security: Dict representing a Portfolio Performance security with
                optional keys isin, symbol, and name.
            kubera_holdings: List of Kubera holding dicts to search.

        Returns:
            The best-matching Kubera holding dict, or None when no match is found.
            Tries ISIN first, then ticker, then name similarity.
        """

        # Try ISIN match first (most reliable)
        if pp_security.get("isin"):
            for holding in kubera_holdings:
                kubera_isin = holding.get("isin")
                if kubera_isin and cls.match_by_isin(pp_security["isin"], kubera_isin):
                    return holding

        # Try ticker match
        if pp_security.get("symbol"):
            for holding in kubera_holdings:
                kubera_ticker = holding.get("ticker")
                if kubera_ticker and cls.match_by_ticker(
                    pp_security["symbol"],
                    kubera_ticker,
                ):
                    return holding

        # Try name match
        if pp_security.get("name"):
            for holding in kubera_holdings:
                kubera_name = holding.get("name")
                if kubera_name and cls.match_by_name(pp_security["name"], kubera_name):
                    return holding

        return None

    @staticmethod
    def calculate_variance(pp_value: float, kubera_value: float) -> tuple[float, float]:
        """Calculate absolute and percentage variance between two values.

        Args:
            pp_value: Reference value from Portfolio Performance.
            kubera_value: Comparison value from Kubera.

        Returns:
            Tuple of (absolute_variance, percentage_variance). When pp_value is
            zero, percentage_variance is 100.0 if kubera_value is non-zero, else 0.0.
        """
        variance = kubera_value - pp_value

        if pp_value == 0:
            percentage = 100.0 if kubera_value != 0 else 0.0
        else:
            percentage = (variance / pp_value) * 100

        return variance, percentage
