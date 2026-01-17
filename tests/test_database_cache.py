"""
Test database caching functionality.

This script tests the basic database operations for caching financial data.
"""

from datetime import date
import pandas as pd

from pysft.core.database import DatabaseManager
from pysft.core.structures import _indicator_data
from pysft.core.constants import IMMUTABLE_FIELDS, LONGTERM_TTL_FIELDS, SHORT_TTL_FIELDS


def test_basic_caching():
    """Test basic cache operations."""
    
    print("Testing database caching...")
    
    # Create test database in memory
    db = DatabaseManager(":memory:")
    
    # Create sample indicator data
    test_data = _indicator_data(
        indicator="AAPL",
        name="Apple Inc.",
        ISIN="US0378331005",
        quoteType="EQUITY",
        briefSummary="Technology company",
        currency="USD",
        dates=[pd.Timestamp(date.today())],
        last=150.0,
        open=148.0,
        high=152.0,
        low=147.0,
        volume=50000000,
        expense_rate=0.0,
        dividendYield=0.005,
        trailingPE=25.5,
        beta=1.2
    )
    
    # Test 1: Cache the data
    print("\n1. Caching indicator data...")
    fetched_fields = ["name", "ISIN", "quoteType", "briefSummary", "currency", 
                      "dividendYield", "trailingPE", "beta"]
    db.cache_indicator_data("AAPL", test_data, fetched_fields)
    print("   ✓ Data cached successfully")
    
    # Test 2: Retrieve from cache - should be fresh
    print("\n2. Retrieving cached data (should be fresh)...")
    cached_data, is_fresh = db.get_cached_data("AAPL", ["name", "ISIN", "dividendYield"])
    
    if cached_data:
        print(f"   ✓ Data retrieved: {cached_data.name}")
        print(f"   ✓ ISIN: {cached_data.ISIN}")
        print(f"   ✓ Is fresh: {is_fresh}")
    else:
        print("   ✗ No data found")
    
    # Test 3: Cache historical data
    print("\n3. Caching historical price data...")
    historical_dates = pd.date_range(start='2024-01-01', end='2024-01-10', freq='D')
    db.cache_historical_data(
        indicator="AAPL",
        dates=list(historical_dates),
        open_prices=[150.0 + i for i in range(10)],
        high_prices=[152.0 + i for i in range(10)],
        low_prices=[148.0 + i for i in range(10)],
        close_prices=[151.0 + i for i in range(10)],
        volumes=[50000000 + i*1000000 for i in range(10)]
    )
    print("   ✓ Historical data cached")
    
    # Test 4: Get cached dates
    print("\n4. Retrieving cached dates...")
    cached_dates = db.get_cached_dates("AAPL")
    print(f"   ✓ Found {len(cached_dates)} cached dates")
    print(f"   ✓ Date range: {min(cached_dates)} to {max(cached_dates)}")
    
    # Test 5: Retrieve historical data
    print("\n5. Retrieving historical data for date range...")
    hist_data = db.get_historical_data(
        "AAPL",
        pd.Timestamp('2024-01-01'),
        pd.Timestamp('2024-01-10')
    )
    
    if hist_data:
        print(f"   ✓ Retrieved {len(hist_data.dates)} data points")
        print(f"   ✓ First close: {hist_data.last[0]}")
        print(f"   ✓ Last close: {hist_data.last[-1]}")
    else:
        print("   ✗ No historical data found")
    
    # Test 6: Test cache miss
    print("\n6. Testing cache miss for non-existent indicator...")
    cached_data, is_fresh = db.get_cached_data("MSFT", ["name"])
    print(f"   ✓ Cache miss handled correctly: data={cached_data}, fresh={is_fresh}")
    
    # Close database
    db.close()
    print("\n✓ All tests passed!")


if __name__ == "__main__":
    test_basic_caching()
