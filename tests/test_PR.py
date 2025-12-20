# -------- Standard library imports --------

# -------- Third-party imports --------
import pytest
import pandas as pd

# -------- Package imports --------
from pysft.lib import fetchData

from testIndicators import indicatorsDB

MAX_INDICATOR_STR_PER_LINE = 10

def print_indicators_list(indicators: list[str]) -> None:
    """
    Utility function to print the list of indicators in a formatted manner.
    """
    indicatorStr = ""
    counter = 0
    for indicator in indicators:
        if counter >= MAX_INDICATOR_STR_PER_LINE:
            # remove the last comma and space
            indicatorStr = indicatorStr[:-2]
            indicatorStr += "\n"
            counter = 0

        indicatorStr += f"{indicator}, "
        counter += 1

    print(f"Indicators:\n{indicatorStr}")

@pytest.fixture
def getTestIndicators() -> list[str]:
    indicators = indicatorsDB.US

    print(f"Setting up indicators for test - total: {len(indicators)}")

    return indicators

@pytest.fixture
def getRequiredAttributes() -> list[str]:
    return ["name", "price", "high", "low", "open", "volume", "expense_rate", "currency", "quoteType", "change_pct"]

@pytest.fixture
def getDateRange() -> tuple[str, str]:
    return ("2025-07-01", "2025-08-01")

# Single indicator fetch test
def test_single_indicator_fetch(getTestIndicators):
    """
    Test fetching data for a single indicator.
    """

    singleInd = getTestIndicators[0]
    print(f"Testing single indicator fetch for: {singleInd}")

    quote = fetchData(indicators=singleInd)

    # Basic existence checks
    assert quote is not None, "in 'test_single_indicator_fetch', fetched data is None."
    assert not quote.empty, "in 'test_single_indicator_fetch', fetched data is empty."

    # DataFrame structure checks
    assert quote.columns.names == ["Indicator", "Attribute"], "in 'test_single_indicator_fetch', Column names do not match, expected - [\"Indicator\", \"Attribute\"]."

    # Indicator presence check
    assert singleInd in quote, f"in 'test_single_indicator_fetch', fetched data does not contain expected indicator: {singleInd}."

    # Indicator content checks
    assert not quote[singleInd].empty, f"in 'test_single_indicator_fetch', fetched data for indicator {singleInd} is empty."

    assert isinstance(quote[singleInd].index, pd.DatetimeIndex) and quote[singleInd].index.__len__() == 1, "in 'test_single_indicator_fetch', index is not a DatetimeIndex object or does not contain exactly one entry."
    assert 'price' in quote[singleInd].columns, f"in 'test_single_indicator_fetch', 'price' attribute not found for indicator {singleInd}."
    assert quote[singleInd]['price'].iloc[0] > 0.0, f"in 'test_single_indicator_fetch', 'price' attribute is invalid (not greater than 0, should expect a positive price number) for indicator {singleInd}."

    print(f"Single indicator fetch test for {singleInd} passed.")

# Multiple indicators fetch test, with date range
def test_multiple_indicators_fetch(getTestIndicators, getDateRange):
    """
    Test fetching data for multiple indicators.
    """

    print(f"Testing multiple indicators fetch for total: {len(getTestIndicators)} indicators.")
    print_indicators_list(getTestIndicators)

    quotes = fetchData(indicators=getTestIndicators, start=getDateRange[0], end=getDateRange[1])

    # Basic existence checks
    assert quotes is not None, "in 'test_multiple_indicators_fetch', fetched data is None."
    assert not quotes.empty, "in 'test_multiple_indicators_fetch', fetched data is empty."

    # DataFrame structure checks
    assert quotes.columns.names == ["Indicator", "Attribute"], "in 'test_multiple_indicators_fetch', Column names do not match, expected - [\"Indicator\", \"Attribute\"]."

    # Indicator presence check
    dateRange_check = False
    for indicator in getTestIndicators:
        assert indicator in quotes, f"in 'test_multiple_indicators_fetch', fetched data does not contain expected indicator: {indicator}."

        # Indicator content checks
        assert not quotes[indicator].empty, f"in 'test_multiple_indicators_fetch', fetched data for indicator {indicator} is empty."

        if not dateRange_check:
            assert (quotes[indicator].index >= pd.to_datetime(getDateRange[0])).all() and (quotes[indicator].index <= pd.to_datetime(getDateRange[1])).all(), f"in 'test_multiple_indicators_fetch', index is not DatetimeIndex of the specified date range for indicator."
            dateRange_check = True

        assert 'price' in quotes[indicator].columns, f"in 'test_multiple_indicators_fetch', 'price' attribute not found for indicator {indicator}."
        assert pd.notna(quotes[indicator]['price']).all(), f"in 'test_multiple_indicators_fetch', 'price' attribute contains NaN for indicator {indicator}."
        assert (quotes[indicator]['price'] > 0.0).all(), f"in 'test_multiple_indicators_fetch', 'price' attribute has invalid values (not greater than 0, should expect positive price numbers) for indicator {indicator}."

    print(f"Multiple indicators fetch test for total: {len(getTestIndicators)} indicators passed.")

# Multiple indicators fetch test, with required attributes and date range
def test_fetch_with_required_attributes(getTestIndicators, getRequiredAttributes, getDateRange):
    """
    Test fetching data for multiple indicators with specific required attributes.
    """

    print(f"Testing multiple indicators fetch with required attributes for total: {len(getTestIndicators)} indicators.")
    print_indicators_list(getTestIndicators)

    quotes = fetchData(indicators=getTestIndicators, attributes=getRequiredAttributes, start=getDateRange[0], end=getDateRange[1])

    # Basic existence checks
    assert quotes is not None, "in 'test_fetch_with_required_attributes', fetched data is None."
    assert not quotes.empty, "in 'test_fetch_with_required_attributes', fetched data is empty."

    # DataFrame structure checks
    assert quotes.columns.names == ["Indicator", "Attribute"], "in 'test_fetch_with_required_attributes', Column names do not match, expected - [\"Indicator\", \"Attribute\"]."

    # Indicator presence check
    dateRange_check = False
    for indicator in getTestIndicators:
        assert indicator in quotes, f"in 'test_fetch_with_required_attributes', fetched data does not contain expected indicator: {indicator}."
        # Indicator content checks
        assert not quotes[indicator].empty, f"in 'test_fetch_with_required_attributes', fetched data for indicator {indicator} is empty."

        if not dateRange_check:
            assert (quotes[indicator].index >= pd.to_datetime(getDateRange[0])).all() and (quotes[indicator].index <= pd.to_datetime(getDateRange[1])).all(), f"in 'test_multiple_indicators_fetch', index is not DatetimeIndex of the specified date range for indicator."
            dateRange_check = True

        for attribute in getRequiredAttributes:
            assert attribute in quotes[indicator].columns, f"in 'test_fetch_with_required_attributes', '{attribute}' attribute not found for indicator {indicator}."

            if attribute == 'price':
                assert pd.notna(quotes[indicator]['price']).all(), f"in 'test_fetch_with_required_attributes', 'price' attribute contains NaN for indicator {indicator}."
                assert (quotes[indicator]['price'] > 0.0).all(), f"in 'test_fetch_with_required_attributes', 'price' attribute has invalid values (not greater than 0, should expect positive price numbers) for indicator {indicator}."

    print(f"Multiple indicators fetch with required attributes test for total: {len(getTestIndicators)} indicators passed.")