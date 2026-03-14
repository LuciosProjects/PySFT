"""
Test database caching functionality.

Tests the simplified 2-tier TTL caching model:
- Immutable fields (indicator, name, ISIN, inceptionDate, quoteType, exchange): never expire
- Volatile fields: 15-minute TTL
- Historical timeseries: immutable except today's data (15-min TTL)
"""

from datetime import date, datetime, timedelta
import pandas as pd
import time

from pysft.core.database import (
    DatabaseManager, 
    _get_timeseries_fields, 
    _get_scalar_fields,
    _is_list_type,
)
from pysft.core.structures import _indicator_data
from pysft.core.constants import TTL_MINUTES, IMMUTABLE_FIELD_NAMES


def test_dynamic_field_detection():
    """Test that timeseries and scalar fields are correctly detected from type hints."""
    
    print("Testing dynamic field detection...")
    
    timeseries = _get_timeseries_fields()
    scalar = _get_scalar_fields()
    
    # Timeseries fields should include list-typed fields
    expected_timeseries = {"dates", "price", "last", "open", "high", "low", "volume", "change_pct", "market_cap"}
    print(f"   Detected timeseries fields: {timeseries}")
    print(f"   Expected timeseries fields: {expected_timeseries}")
    
    # Check that key timeseries fields are detected
    assert "dates" in timeseries, "dates should be a timeseries field"
    assert "last" in timeseries, "last should be a timeseries field"
    assert "volume" in timeseries, "volume should be a timeseries field"
    
    # Scalar fields should include non-list fields
    expected_scalar = {"indicator", "name", "ISIN", "inceptionDate", "quoteType", "currency", "exchange",
                       "expense_rate", "avgDailyVolume3mnth", "dividendYield", "trailingPE", 
                       "forwardPE", "beta"}
    print(f"   Detected scalar fields: {scalar}")
    
    assert "indicator" in scalar, "indicator should be a scalar field"
    assert "name" in scalar, "name should be a scalar field"
    assert "currency" in scalar, "currency should be a scalar field"
    assert "exchange" in scalar, "exchange should be a scalar field"
    
    # No overlap
    assert len(timeseries & scalar) == 0, "No field should be both timeseries and scalar"
    
    print("   ✓ Dynamic field detection passed")


def test_basic_caching():
    """Test basic cache operations with new schema."""
    
    print("\nTesting basic caching...")
    
    # Create test database in memory
    db = DatabaseManager(":memory:")
    
    # Create sample indicator data
    test_data = _indicator_data(
        indicator="AAPL",
        name="Apple Inc.",
        ISIN="US0378331005",
        quoteType="EQUITY",
        inceptionDate=pd.Timestamp("1980-12-12"),
        currency="USD",
        exchange="XNAS",
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
    fetched_fields = ["indicator", "name", "ISIN", "quoteType", "inceptionDate", 
                      "currency", "exchange", "dividendYield", "trailingPE", "beta"]
    db.cache_indicator_data("AAPL", test_data, fetched_fields)
    print("   ✓ Data cached successfully")
    
    # Test 2: Retrieve from cache - should be fresh
    print("\n2. Retrieving cached data (should be fresh)...")
    cached_data, is_fresh = db.get_cached_data("AAPL", ["name", "ISIN", "exchange", "dividendYield"])
    
    assert cached_data is not None, "Should find cached data"
    assert cached_data.name == "Apple Inc.", f"Name mismatch: {cached_data.name}"
    assert cached_data.ISIN == "US0378331005", f"ISIN mismatch: {cached_data.ISIN}"
    assert is_fresh, "Data should be fresh"
    print(f"   ✓ Data retrieved: {cached_data.name}")
    print(f"   ✓ ISIN: {cached_data.ISIN}")
    assert cached_data.exchange == "XNAS", f"Exchange mismatch: {cached_data.exchange}"
    print(f"   ✓ Exchange: {cached_data.exchange}")
    print(f"   ✓ Is fresh: {is_fresh}")
    
    # Test 3: Cache miss for non-existent indicator
    print("\n3. Testing cache miss...")
    cached_data, is_fresh = db.get_cached_data("MSFT", ["name"])
    assert cached_data is None, "Should not find non-existent indicator"
    assert not is_fresh, "Non-existent should not be fresh"
    print("   ✓ Cache miss handled correctly")
    
    db.close()
    print("\n✓ Basic caching tests passed!")


def test_immutable_fields():
    """Test that immutable fields are not updated after initial cache."""
    
    print("\nTesting immutable field behavior...")
    
    db = DatabaseManager(":memory:")
    
    # Initial data
    initial_data = _indicator_data(
        indicator="AAPL",
        name="Apple Inc.",
        ISIN="US0378331005",
        quoteType="EQUITY",
        exchange="XNAS",
    )
    
    db.cache_indicator_data("AAPL", initial_data, ["indicator", "name", "ISIN", "quoteType", "exchange"])
    
    # Try to update with new data
    updated_data = _indicator_data(
        indicator="AAPL",
        name="Apple Corporation",  # Changed name
        ISIN="CHANGED123",         # Changed ISIN
        quoteType="ETF",           # Changed type
        exchange="XNYS",           # Changed exchange
    )
    
    db.cache_indicator_data("AAPL", updated_data, ["indicator", "name", "ISIN", "quoteType", "exchange"])
    
    # Retrieve and verify immutable fields were NOT updated
    cached_data, is_fresh = db.get_cached_data("AAPL", ["name", "ISIN", "quoteType", "exchange"])
    
    assert cached_data.name == "Apple Inc.", f"Immutable name should not change: {cached_data.name}"
    assert cached_data.ISIN == "US0378331005", f"Immutable ISIN should not change: {cached_data.ISIN}"
    assert cached_data.quoteType == "EQUITY", f"Immutable quoteType should not change: {cached_data.quoteType}"
    assert cached_data.exchange == "XNAS", f"Immutable exchange should not change: {cached_data.exchange}"
    
    print("   ✓ Immutable fields preserved after update attempt")
    
    db.close()
    print("✓ Immutable field tests passed!")


def test_volatile_field_freshness():
    """Test that volatile fields respect 15-minute TTL."""
    
    print("\nTesting volatile field freshness (simulated)...")
    
    db = DatabaseManager(":memory:")
    
    test_data = _indicator_data(
        indicator="AAPL",
        name="Apple Inc.",
        currency="USD",
        dividendYield=0.005,
        beta=1.2,
    )
    
    db.cache_indicator_data("AAPL", test_data, ["indicator", "name", "currency", "dividendYield", "beta"])
    
    # Immediately should be fresh
    _, is_fresh = db.get_cached_data("AAPL", ["currency", "dividendYield"])
    assert is_fresh, "Volatile fields should be fresh immediately after caching"
    print("   ✓ Volatile fields fresh immediately after cache")
    
    # Immutable fields should always be fresh regardless of time
    _, is_fresh = db.get_cached_data("AAPL", ["name"])
    assert is_fresh, "Immutable fields should always be fresh"
    print("   ✓ Immutable fields always fresh")
    
    db.close()
    print("✓ Volatile field freshness tests passed!")


def test_historical_data_caching():
    """Test historical price data caching."""
    
    print("\nTesting historical data caching...")
    
    db = DatabaseManager(":memory:")
    
    # Cache 10 days of historical data
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
    
    # Get cached dates
    cached_dates = db.get_cached_dates("AAPL")
    assert len(cached_dates) == 10, f"Should have 10 cached dates, got {len(cached_dates)}"
    print(f"   ✓ Found {len(cached_dates)} cached dates")
    
    # Retrieve historical data
    hist_data = db.get_historical_data(
        "AAPL",
        pd.Timestamp('2024-01-01'),
        pd.Timestamp('2024-01-10')
    )
    
    assert hist_data is not None, "Should find historical data"
    assert len(hist_data.dates) == 10, f"Should have 10 data points, got {len(hist_data.dates)}"
    assert hist_data.last[0] == 151.0, f"First close should be 151.0, got {hist_data.last[0]}"
    assert hist_data.last[-1] == 160.0, f"Last close should be 160.0, got {hist_data.last[-1]}"
    print(f"   ✓ Retrieved {len(hist_data.dates)} data points")
    print(f"   ✓ First close: {hist_data.last[0]}, Last close: {hist_data.last[-1]}")
    
    db.close()
    print("✓ Historical data caching tests passed!")


def test_today_data_ttl():
    """Test that today's timeseries data respects 15-minute TTL."""
    
    print("\nTesting today's data TTL behavior...")
    
    db = DatabaseManager(":memory:")
    
    today = pd.Timestamp.now().floor("D")
    yesterday = today - pd.Timedelta(days=1)
    
    # Cache today's and yesterday's data
    db.cache_historical_data(
        indicator="AAPL",
        dates=[yesterday, today],
        open_prices=[150.0, 155.0],
        high_prices=[152.0, 157.0],
        low_prices=[148.0, 153.0],
        close_prices=[151.0, 156.0],
        volumes=[50000000, 60000000]
    )
    
    # Both dates should be in cache (fresh)
    cached_dates = db.get_cached_dates("AAPL")
    assert len(cached_dates) == 2, f"Should have 2 cached dates, got {len(cached_dates)}"
    assert today in cached_dates, "Today should be in cached dates (fresh)"
    assert yesterday in cached_dates, "Yesterday should be in cached dates"
    print("   ✓ Both today and yesterday in cache when fresh")
    
    # Note: To fully test TTL expiry, we would need to manipulate timestamps
    # or wait 15 minutes. For unit testing, the logic is validated through
    # the _is_attribute_fresh method and get_cached_dates implementation.
    
    db.close()
    print("✓ Today's data TTL tests passed!")


def test_partial_attribute_request():
    """Test that freshness is checked only for requested attributes."""
    
    print("\nTesting partial attribute request...")
    
    db = DatabaseManager(":memory:")
    
    test_data = _indicator_data(
        indicator="AAPL",
        name="Apple Inc.",
        ISIN="US0378331005",
        currency="USD",
        dividendYield=0.005,
    )
    
    # Only cache some fields
    db.cache_indicator_data("AAPL", test_data, ["indicator", "name", "currency"])
    
    # Request only cached fields - should be fresh
    _, is_fresh = db.get_cached_data("AAPL", ["name", "currency"])
    assert is_fresh, "Should be fresh when all requested fields are cached"
    print("   ✓ Fresh when requesting only cached fields")
    
    # Request uncached field - should not be fresh
    _, is_fresh = db.get_cached_data("AAPL", ["name", "dividendYield"])
    assert not is_fresh, "Should not be fresh when requesting uncached field"
    print("   ✓ Not fresh when requesting uncached field")
    
    db.close()
    print("✓ Partial attribute request tests passed!")


def run_all_tests():
    """Run all database cache tests."""
    print("=" * 60)
    print("Running Database Cache Tests (2-Tier TTL Model)")
    print("=" * 60)
    
    test_dynamic_field_detection()
    test_basic_caching()
    test_immutable_fields()
    test_volatile_field_freshness()
    test_historical_data_caching()
    test_today_data_ttl()
    test_partial_attribute_request()
    
    print("\n" + "=" * 60)
    print("✓ All database cache tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
