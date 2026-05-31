"""
Portfolio Performance XML export service for complete backup generation.
Generates valid PP XML backup files that can restore a complete PP instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # stdlib has complete type stubs; defusedxml.ElementTree re-exports the same API
    import xml.etree.ElementTree as ET  # nosec B405  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml

    from sqlalchemy.orm import Session
else:
    import defusedxml.ElementTree as ET  # noqa: N817  # safe parser at runtime

from datetime import UTC, datetime
from pathlib import Path

import defusedxml
import defusedxml.minidom as defused_minidom

from security_master.storage.models import SecurityMaster
from security_master.storage.pp_models import (
    PPAccount,
    PPAccountTransaction,
    PPBookmark,
    PPClientConfig,
    PPPortfolio,
    PPPortfolioTransaction,
    PPSecurityPrice,
    PPSetting,
    PPTransactionUnit,
)


class PPXMLExportService:
    """Generate complete Portfolio Performance XML backup from database."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def generate_complete_backup(self, config_name: str = "default") -> str:
        """Generate complete PP XML backup file.

        Args:
            config_name (str): Name of the active PPClientConfig record to use.
                Defaults to "default".

        Returns:
            str: Pretty-printed XML string representing the complete PP backup.

        Raises:
            ValueError: When no active PP configuration is found for config_name.
        """

        # Get client configuration
        config = (
            self.session.query(PPClientConfig)
            .filter_by(config_name=config_name, is_active=True)
            .first()
        )

        if not config:
            msg = f"No active PP configuration found for '{config_name}'"
            raise ValueError(msg)

        # Create root client element
        root = ET.Element("client")

        # Add client metadata
        ET.SubElement(root, "version").text = str(config.version)
        ET.SubElement(root, "baseCurrency").text = config.base_currency

        # Add main sections
        self._add_securities_section(root)
        self._add_watchlists_section(root)
        self._add_accounts_section(root)
        self._add_portfolios_section(root)
        self._add_dashboards_section(root)
        self._add_properties_section(root)
        self._add_settings_section(root)

        # Convert to pretty-printed XML string
        return self._prettify_xml(root)

    def _add_securities_section(self, parent: ET.Element) -> None:
        """Add securities section with complete price history.

        Args:
            parent (ET.Element): Parent XML element to append the securities section to.
        """
        securities_elem = ET.SubElement(parent, "securities")

        # Get all securities with their prices
        securities = self.session.query(SecurityMaster).all()

        for security in securities:
            security_elem = ET.SubElement(securities_elem, "security")

            # Security identification
            ET.SubElement(security_elem, "uuid").text = str(
                security.id,
            )  # Use database ID as UUID for now
            ET.SubElement(security_elem, "name").text = security.name
            ET.SubElement(security_elem, "currencyCode").text = (
                security.currency or "USD"
            )

            if security.note:
                ET.SubElement(security_elem, "note").text = security.note
            if security.isin:
                ET.SubElement(security_elem, "isin").text = security.isin
            if security.symbol:
                ET.SubElement(security_elem, "tickerSymbol").text = security.symbol
            if security.wkn:
                ET.SubElement(security_elem, "wkn").text = security.wkn

            # Quote feed configuration
            ET.SubElement(security_elem, "feed").text = "PP"  # Default to PP feed

            # Add price history
            self._add_price_history(security_elem, security.id)

    def _add_price_history(
        self,
        security_elem: ET.Element,
        security_id: int,
    ) -> None:
        """Add complete price history for a security.

        Args:
            security_elem (ET.Element): XML element for the security to append prices to.
            security_id (int): Database ID of the security whose prices to load.
        """
        prices = (
            self.session.query(PPSecurityPrice)
            .filter_by(security_id=security_id)
            .order_by(PPSecurityPrice.price_date)
            .all()
        )

        if prices:
            prices_elem = ET.SubElement(security_elem, "prices")

            for price in prices:
                price_elem = ET.SubElement(prices_elem, "price")
                price_elem.set("t", price.price_date.strftime("%Y-%m-%d"))
                price_elem.set("v", str(price.price_value))

    def _add_watchlists_section(self, parent: ET.Element) -> None:
        """Add watchlists section (typically empty).

        Args:
            parent (ET.Element): Parent XML element to append the watchlists section to.
        """
        ET.SubElement(parent, "watchlists")

    def _add_accounts_section(self, parent: ET.Element) -> None:
        """Add accounts section with all transactions.

        Args:
            parent (ET.Element): Parent XML element to append the accounts section to.
        """
        accounts_elem = ET.SubElement(parent, "accounts")

        accounts = self.session.query(PPAccount).filter_by(is_retired=False).all()

        for account in accounts:
            account_elem = ET.SubElement(accounts_elem, "account")

            # Account identification
            ET.SubElement(account_elem, "uuid").text = str(account.uuid)
            ET.SubElement(account_elem, "name").text = account.name
            ET.SubElement(account_elem, "currencyCode").text = account.currency_code
            ET.SubElement(account_elem, "isRetired").text = str(
                account.is_retired,
            ).lower()

            # Add account transactions
            self._add_account_transactions(account_elem, account.id)

            # Add account attributes
            if account.attributes:
                attributes_elem = ET.SubElement(account_elem, "attributes")
                ET.SubElement(attributes_elem, "map")  # Empty map for now

            # Add updatedAt timestamp
            ET.SubElement(account_elem, "updatedAt").text = (
                datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
            )

    def _add_account_transactions(
        self,
        account_elem: ET.Element,
        account_id: int,
    ) -> None:
        """Add all transactions for an account.

        Args:
            account_elem (ET.Element): XML element for the account to append transactions to.
            account_id (int): Database ID of the account whose transactions to load.
        """
        transactions = (
            self.session.query(PPAccountTransaction)
            .filter_by(account_id=account_id)
            .order_by(PPAccountTransaction.transaction_date)
            .all()
        )

        if transactions:
            transactions_elem = ET.SubElement(account_elem, "transactions")

            for transaction in transactions:
                trans_elem = ET.SubElement(
                    transactions_elem,
                    "account-transaction",
                )

                # Transaction core data
                ET.SubElement(trans_elem, "uuid").text = str(transaction.uuid)
                ET.SubElement(
                    trans_elem, "date"
                ).text = transaction.transaction_date.strftime("%Y-%m-%dT00:00")
                ET.SubElement(
                    trans_elem, "currencyCode"
                ).text = transaction.currency_code
                ET.SubElement(trans_elem, "amount").text = str(
                    int(transaction.amount * 100),
                )  # PP uses cents

                # Security reference if present
                if transaction.security_id:
                    security_ref = ET.SubElement(trans_elem, "security")
                    security_ref.set(
                        "reference",
                        f"../../../../../securities/security[{transaction.security_id}]",
                    )

                # Shares (usually 0 for account transactions)
                ET.SubElement(trans_elem, "shares").text = str(
                    int(transaction.shares * 100000000),
                )  # PP format

                # Transaction type
                ET.SubElement(trans_elem, "type").text = transaction.transaction_type

                # Add transaction units (fees, taxes)
                self._add_transaction_units(trans_elem, transaction.id, "ACCOUNT")

                # Cross-entry for linked portfolio transactions
                if transaction.cross_entry_type:
                    cross_entry = ET.SubElement(trans_elem, "crossEntry")
                    cross_entry.set("class", transaction.cross_entry_type)
                    # Portfolio reference would be added here for linked transactions

    def _add_transaction_units(
        self,
        transaction_elem: ET.Element,
        transaction_id: int,
        transaction_type: str,
    ) -> None:
        """Add fee and tax units for a transaction.

        Args:
            transaction_elem (ET.Element): XML element for the transaction to append units to.
            transaction_id (int): Database ID of the transaction whose units to load.
            transaction_type (str): Type discriminator used to filter units ("ACCOUNT"
                or "PORTFOLIO").
        """
        units = (
            self.session.query(PPTransactionUnit)
            .filter_by(transaction_id=transaction_id, transaction_type=transaction_type)
            .all()
        )

        for unit in units:
            unit_elem = ET.SubElement(transaction_elem, "unit")
            unit_elem.set("type", unit.unit_type)

            amount_elem = ET.SubElement(unit_elem, "amount")
            amount_elem.set("currency", unit.currency_code)
            amount_elem.text = str(int(unit.amount * 100))  # PP uses cents

    def _add_portfolios_section(self, parent: ET.Element) -> None:
        """Add portfolios section with all portfolio transactions.

        Args:
            parent (ET.Element): Parent XML element to append the portfolios section to.
        """
        portfolios_elem = ET.SubElement(parent, "portfolios")

        portfolios = self.session.query(PPPortfolio).filter_by(is_retired=False).all()

        for portfolio in portfolios:
            portfolio_elem = ET.SubElement(portfolios_elem, "portfolio")

            # Portfolio identification
            ET.SubElement(portfolio_elem, "uuid").text = str(portfolio.uuid)
            ET.SubElement(portfolio_elem, "name").text = portfolio.name
            ET.SubElement(portfolio_elem, "isRetired").text = str(
                portfolio.is_retired,
            ).lower()

            # Reference account
            if portfolio.reference_account:
                ref_account_elem = ET.SubElement(
                    portfolio_elem,
                    "referenceAccount",
                )
                ET.SubElement(ref_account_elem, "uuid").text = str(
                    portfolio.reference_account.uuid,
                )
                ET.SubElement(
                    ref_account_elem, "name"
                ).text = portfolio.reference_account.name
                ET.SubElement(
                    ref_account_elem, "currencyCode"
                ).text = portfolio.reference_account.currency_code
                ET.SubElement(ref_account_elem, "isRetired").text = str(
                    portfolio.reference_account.is_retired,
                ).lower()

                # Empty transactions for reference account
                ET.SubElement(ref_account_elem, "transactions")

                # Empty attributes
                attributes_elem = ET.SubElement(ref_account_elem, "attributes")
                ET.SubElement(attributes_elem, "map")

                # Updated timestamp
                ET.SubElement(ref_account_elem, "updatedAt").text = (
                    datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
                )

            # Add portfolio transactions
            self._add_portfolio_transactions(portfolio_elem, portfolio.id)

    def _add_portfolio_transactions(
        self,
        portfolio_elem: ET.Element,
        portfolio_id: int,
    ) -> None:
        """Add all transactions for a portfolio.

        Args:
            portfolio_elem (ET.Element): XML element for the portfolio to append transactions to.
            portfolio_id (int): Database ID of the portfolio whose transactions to load.
        """
        transactions = (
            self.session.query(PPPortfolioTransaction)
            .filter_by(portfolio_id=portfolio_id)
            .order_by(PPPortfolioTransaction.transaction_date)
            .all()
        )

        if transactions:
            transactions_elem = ET.SubElement(portfolio_elem, "transactions")

            for transaction in transactions:
                trans_elem = ET.SubElement(
                    transactions_elem,
                    "portfolio-transaction",
                )

                # Transaction core data
                ET.SubElement(trans_elem, "uuid").text = str(transaction.uuid)
                ET.SubElement(
                    trans_elem, "date"
                ).text = transaction.transaction_date.strftime("%Y-%m-%dT00:00")
                ET.SubElement(
                    trans_elem, "currencyCode"
                ).text = transaction.currency_code
                ET.SubElement(trans_elem, "amount").text = str(
                    int(transaction.amount * 100),
                )  # PP uses cents

                # Security reference (required for portfolio transactions)
                security_ref = ET.SubElement(trans_elem, "security")
                security_ref.set(
                    "reference",
                    f"../../../../../../../../../securities/security[{transaction.security_id}]",
                )

                # Shares (required for portfolio transactions)
                ET.SubElement(trans_elem, "shares").text = str(
                    int(transaction.shares * 100000000),
                )  # PP format

                # Transaction type
                ET.SubElement(trans_elem, "type").text = transaction.transaction_type

                # Add transaction units (fees, taxes)
                self._add_transaction_units(trans_elem, transaction.id, "PORTFOLIO")

                # Cross-entry for linked account transaction
                if transaction.linked_account_transaction:
                    cross_entry = ET.SubElement(trans_elem, "crossEntry")
                    cross_entry.set("class", "buysell")  # Most common type

                    # Portfolio reference
                    portfolio_ref = ET.SubElement(cross_entry, "portfolio")
                    portfolio_ref.set("reference", "../../../..")

                    # Portfolio transaction reference
                    portfolio_trans_ref = ET.SubElement(
                        cross_entry,
                        "portfolioTransaction",
                    )
                    portfolio_trans_ref.set("reference", "../..")

                    # Account reference
                    account_ref = ET.SubElement(cross_entry, "account")
                    account_ref.set("reference", "../../../../../../../..")

                    # Account transaction details
                    account_trans = ET.SubElement(
                        cross_entry,
                        "accountTransaction",
                    )
                    linked_trans = transaction.linked_account_transaction

                    ET.SubElement(account_trans, "uuid").text = str(
                        linked_trans.uuid,
                    )
                    ET.SubElement(
                        account_trans, "date"
                    ).text = linked_trans.transaction_date.strftime("%Y-%m-%dT00:00")
                    ET.SubElement(
                        account_trans, "currencyCode"
                    ).text = linked_trans.currency_code
                    ET.SubElement(account_trans, "amount").text = str(
                        int(linked_trans.amount * 100),
                    )

                    if linked_trans.security_id:
                        security_ref = ET.SubElement(account_trans, "security")
                        security_ref.set(
                            "reference",
                            f"../../../../../../../../../../../securities/security[{linked_trans.security_id}]",
                        )

                    # Cross-entry reference back
                    cross_ref = ET.SubElement(account_trans, "crossEntry")
                    cross_ref.set("class", "buysell")
                    cross_ref.set("reference", "../..")

                    ET.SubElement(account_trans, "shares").text = str(
                        int(linked_trans.shares * 100000000),
                    )
                    ET.SubElement(
                        account_trans, "type"
                    ).text = linked_trans.transaction_type

    def _add_dashboards_section(self, parent: ET.Element) -> None:
        """Add dashboards section (typically empty).

        Args:
            parent (ET.Element): Parent XML element to append the dashboards section to.
        """
        ET.SubElement(parent, "dashboards")

    def _add_properties_section(self, parent: ET.Element) -> None:
        """Add properties section from settings.

        Args:
            parent (ET.Element): Parent XML element to append the properties section to.
        """
        properties_elem = ET.SubElement(parent, "properties")

        # Get properties from settings
        properties = (
            self.session.query(PPSetting).filter_by(setting_category="properties").all()
        )

        for prop in properties:
            entry_elem = ET.SubElement(properties_elem, "entry")
            ET.SubElement(entry_elem, "string").text = prop.setting_key
            ET.SubElement(entry_elem, "string").text = prop.setting_value

    def _add_settings_section(self, parent: ET.Element) -> None:
        """Add settings section with bookmarks.

        Args:
            parent (ET.Element): Parent XML element to append the settings section to.
        """
        settings_elem = ET.SubElement(parent, "settings")

        # Add bookmarks
        bookmarks_elem = ET.SubElement(settings_elem, "bookmarks")
        bookmarks = self.session.query(PPBookmark).order_by(PPBookmark.sort_order).all()

        for bookmark in bookmarks:
            bookmark_elem = ET.SubElement(bookmarks_elem, "bookmark")
            ET.SubElement(bookmark_elem, "label").text = bookmark.label
            ET.SubElement(bookmark_elem, "pattern").text = bookmark.pattern

    def _prettify_xml(self, elem: ET.Element) -> str:
        """Return a pretty-printed XML string for the Element.

        Args:
            elem (ET.Element): Root XML Element to serialize and prettify.

        Returns:
            str: Indented XML string with two-space indentation.

        Raises:
            ValueError: When defusedxml raises DefusedXmlException during parsing.
        """
        rough_string = ET.tostring(elem, "unicode")
        try:
            reparsed = defused_minidom.parseString(rough_string)
            return str(reparsed.toprettyxml(indent="  "))
        except defusedxml.DefusedXmlException as e:
            msg = f"XML prettification failed: {e}"
            raise ValueError(msg) from e

    def export_to_file(self, file_path: str, config_name: str = "default") -> None:
        """Export complete PP XML backup to file.

        Args:
            file_path (str): Filesystem path where the XML file will be written.
            config_name (str): Name of the active PPClientConfig record to use.
                Defaults to "default".
        """
        xml_content = self.generate_complete_backup(config_name)

        with Path(file_path).open("w", encoding="utf-8") as f:
            f.write(xml_content)

    def validate_export(self, xml_content: str) -> dict[str, int]:
        """Validate exported XML and return statistics.

        Args:
            xml_content (str): XML string to validate and count elements in.

        Returns:
            dict[str, int]: Counts for securities, accounts, portfolios,
            account_transactions, portfolio_transactions, prices, and bookmarks.

        Raises:
            ValueError: When the XML is invalid or defusedxml raises an exception.
        """
        try:
            # Use defusedxml for safe parsing to validate the generated output
            root = ET.fromstring(xml_content)

            return {
                "securities": len(root.findall(".//security")),
                "accounts": len(root.findall(".//accounts/account")),
                "portfolios": len(root.findall(".//portfolios/portfolio")),
                "account_transactions": len(root.findall(".//account-transaction")),
                "portfolio_transactions": len(root.findall(".//portfolio-transaction")),
                "prices": len(root.findall(".//price")),
                "bookmarks": len(root.findall(".//bookmark")),
            }

        except (ET.ParseError, defusedxml.DefusedXmlException) as e:
            msg = f"Invalid XML generated: {e}"
            raise ValueError(msg) from e


# Utility functions for PP data conversion
def pp_amount_to_decimal(pp_amount: int) -> float:
    """Convert PP integer amount (cents) to decimal.

    Args:
        pp_amount (int): PP integer amount in cents.

    Returns:
        float: Amount as a float (divided by 100).
    """
    return pp_amount / 100.0


def decimal_to_pp_amount(amount: float) -> int:
    """Convert decimal amount to PP integer (cents).

    Args:
        amount (float): Decimal amount to convert.

    Returns:
        int: PP integer amount (multiplied by 100).
    """
    return int(amount * 100)


def pp_shares_to_decimal(pp_shares: int) -> float:
    """Convert PP integer shares to decimal.

    Args:
        pp_shares (int): PP integer share count.

    Returns:
        float: Share count as a float (divided by 100,000,000).
    """
    return pp_shares / 100000000.0


def decimal_to_pp_shares(shares: float) -> int:
    """Convert decimal shares to PP integer format.

    Args:
        shares (float): Decimal share count to convert.

    Returns:
        int: PP integer share count (multiplied by 100,000,000).
    """
    return int(shares * 100000000)
