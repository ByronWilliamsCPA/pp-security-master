"""
Test configuration validation for the testing setup.
"""

import pytest


@pytest.mark.unit
def test_pytest_markers_work():
    """Test that our custom pytest markers work correctly."""
    # This test itself validates that the unit marker works
    assert True


@pytest.mark.unit
@pytest.mark.fast
def test_multiple_markers():
    """Test that multiple markers can be applied."""
    assert True


@pytest.mark.unit
def test_sample_fixtures(sample_security_data, sample_fund_data):
    """Test that our fixtures are working correctly.

    Args:
        sample_security_data: Pytest fixture providing a sample Apple equity dict.
        sample_fund_data: Pytest fixture providing a sample SPY ETF dict.
    """
    # Test security data fixture
    assert sample_security_data["isin"] == "US0378331005"
    assert sample_security_data["symbol"] == "AAPL"
    assert sample_security_data["security_type"] == "equity"

    # Test fund data fixture
    assert sample_fund_data["symbol"] == "SPY"
    assert sample_fund_data["security_type"] == "fund"


@pytest.mark.unit
def test_temp_directory_fixture(temp_directory):
    """Test that temporary directory fixture works.

    Args:
        temp_directory: Pytest fixture providing a fresh temporary directory path.
    """
    assert temp_directory.exists()
    assert temp_directory.is_dir()

    # Create a test file
    test_file = temp_directory / "test.txt"
    test_file.write_text("test content")
    assert test_file.exists()
    assert test_file.read_text() == "test content"


@pytest.mark.unit
def test_invalid_inputs_fixture(invalid_isin_inputs):
    """Test that invalid input fixtures provide expected data.

    Args:
        invalid_isin_inputs: Parametrized pytest fixture yielding one invalid ISIN value per iteration.
    """
    # This will run once for each parameter in the fixture
    # All these inputs are designed to be invalid in some way

    # Valid ISINs have 12 characters, start with 2-letter country code, and have proper check digit
    is_valid_length = (
        isinstance(invalid_isin_inputs, str) and len(invalid_isin_inputs) == 12
    )
    is_valid_type = isinstance(invalid_isin_inputs, str)
    has_valid_country = (
        isinstance(invalid_isin_inputs, str)
        and len(invalid_isin_inputs) >= 2
        and invalid_isin_inputs[:2].isalpha()
        and invalid_isin_inputs[:2] != "XX"
    )  # XX is not a valid country code

    # At least one of these should be false for invalid inputs
    assert not (is_valid_length and is_valid_type and has_valid_country)


@pytest.mark.unit
def test_mock_fixtures(mock_openfigi_client, mock_database_connection):
    """Test that mock fixtures are properly configured.

    Args:
        mock_openfigi_client: Mocked OpenFIGI API client for isolation.
        mock_database_connection: Mocked database connection context for isolation.
    """
    # Test OpenFIGI client mock
    assert mock_openfigi_client is not None
    response = mock_openfigi_client.classify_security.return_value
    assert "data" in response
    assert len(response["data"]) > 0
    assert response["data"][0]["ticker"] == "AAPL"

    # Test database connection mock
    assert mock_database_connection is not None
    assert mock_database_connection.cursor is not None


@pytest.mark.unit
def test_environment_setup():
    """Test that test environment is properly configured."""
    import os

    # Check that test environment variables are set
    assert os.environ.get("TESTING") == "true"
    assert os.environ.get("LOG_LEVEL") == "DEBUG"

    # Check that test database URL is set
    db_url = os.environ.get("DATABASE_URL")
    assert db_url is not None
    assert "test" in db_url.lower()


@pytest.mark.security
@pytest.mark.unit
def test_security_fixtures(malicious_inputs):
    """Test security-related fixtures.

    Args:
        malicious_inputs: Pytest fixture providing a list of attack strings for security validation.
    """
    assert malicious_inputs is not None
    # Should contain various attack patterns
    assert isinstance(malicious_inputs, list)
    assert len(malicious_inputs) > 0

    # Check for some expected attack patterns
    malicious_strings = "".join(malicious_inputs).lower()
    assert any(
        [
            "script" in malicious_strings,  # XSS
            "drop" in malicious_strings,  # SQL injection
            ".." in malicious_strings,  # Path traversal
        ],
    )


@pytest.mark.performance
@pytest.mark.unit
def test_benchmark_fixture(benchmark_data):
    """Test performance-related fixtures.

    Args:
        benchmark_data: Pytest fixture providing a 1000-item ISIN list and timing threshold for perf tests.
    """
    assert benchmark_data is not None
    assert "large_security_list" in benchmark_data
    assert "max_processing_time" in benchmark_data
    assert isinstance(benchmark_data["large_security_list"], list)
    assert len(benchmark_data["large_security_list"]) > 100


# Test for pytest-benchmark integration
@pytest.mark.perf
@pytest.mark.unit
def test_benchmark_example(benchmark):
    """Example of using pytest-benchmark.

    Args:
        benchmark: Pytest-benchmark fixture used to time the wrapped callable.
    """

    def simple_function():
        return sum(range(100))

    result = benchmark(simple_function)
    assert result == sum(range(100))
