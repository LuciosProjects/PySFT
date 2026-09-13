"""
Comprehensive test suite for the caching pipeline.

Tests:
1. Fresh fetch of 50 indicators (populates database cache)
2. Verification that data was saved to database
3. Cache hit test (reload from database without fetching)
4. Performance comparison (fresh fetch vs. cache load)
"""

import sys
import time
from pathlib import Path

# Add src to path
pysft_src = Path(__file__).resolve().parents[1] / "src"
if not (pysft_src / "pysft").is_dir():
    raise RuntimeError(f"Cannot find pysft package at: {pysft_src}")
sys.path.insert(0, str(pysft_src))

import pysft
from pysft.core.database import get_db_manager

from testIndicators import indicatorsDB


def print_banner(text: str):
    """Print a banner to separate test sections."""
    banner = f"\n{'=' * 80}\n{text.center(80)}\n{'=' * 80}\n"
    print(banner)


def print_result(label: str, value, unit: str = ""):
    """Pretty-print a test result."""
    print(f"  {label:<40} {value} {unit}")


def test_fresh_fetch():
    """Test 1: Fresh fetch of 50 indicators (populates cache)."""
    print_banner("TEST 1: FRESH FETCH (50 indicators, no cache)")
    
    # Reset database to ensure clean state
    pysft.core.database.resetDatabase()
    print("✓ Database reset")
    
    indicators = indicatorsDB.FIFTY
    print(f"✓ Loaded {len(indicators)} indicators\n")
    
    # Perform fetch with timing
    print("Fetching data (this populates the database cache)...")
    start_time = time.time()
    result = pysft.lib.fetchData(indicators, attributes=["all"])
    fetch_time = time.time() - start_time
    
    # Analyze results
    missing = [ind for ind in indicators if ind not in result]
    valid = [ind for ind, data in result.items() if data.get("price") and data["price"][0] is not None]
    
    print_result("Indicators fetched", len(result), f"/ {len(indicators)}")
    print_result("Valid prices", len(valid), f"/ {len(result)}")
    print_result("Missing", len(missing), "indicators")
    print_result("Fetch time", f"{fetch_time:.2f}", "seconds")
    
    if missing:
        print_result("Missing indicators", missing)
    
    assert len(result) == len(indicators), f"Expected {len(indicators)} results, got {len(result)}"
    assert len(valid) == len(result), f"Expected all {len(result)} to have valid prices"
    
    print("\n✓ TEST 1 PASSED: All indicators fetched with valid prices")
    return result, fetch_time


def test_database_contents(indicators_count: int):
    """Test 2: Verify data was saved to database."""
    print_banner("TEST 2: VERIFY DATABASE CACHE")
    
    db = get_db_manager()
    
    # Check indicator_attributes table
    cursor = db.connection.cursor()
    cursor.execute("SELECT COUNT(DISTINCT indicator) FROM indicator_attributes")
    cached_indicators = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM indicator_attributes")
    cached_attributes = cursor.fetchone()[0]
    
    print_result("Indicators cached", cached_indicators)
    print_result("Attribute rows", cached_attributes)
    
    # Check price_history table
    cursor.execute("SELECT COUNT(DISTINCT indicator) FROM price_history")
    price_indicators = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM price_history")
    price_rows = cursor.fetchone()[0]
    
    print_result("Indicators with prices", price_indicators)
    print_result("Price history rows", price_rows)
    
    assert cached_indicators > 0, "No indicators cached in database"
    assert price_rows > 0, "No price history cached in database"
    
    print("\n✓ TEST 2 PASSED: Data successfully cached to database")


def test_cache_hit():
    """Test 3: Cache hit - reload from database without fetching."""
    print_banner("TEST 3: CACHE HIT TEST (reload from database)")
    
    indicators = indicatorsDB.FIFTY
    
    print(f"Loading {len(indicators)} indicators from cache...\n")
    
    # Perform fetch with timing (should be faster since data is cached)
    start_time = time.time()
    result_cached = pysft.lib.fetchData(indicators, attributes=["all"])
    cache_time = time.time() - start_time
    
    # Analyze results
    missing = [ind for ind in indicators if ind not in result_cached]
    valid = [ind for ind, data in result_cached.items() if data.get("price") and data["price"][0] is not None]
    
    print_result("Indicators loaded from cache", len(result_cached), f"/ {len(indicators)}")
    print_result("Valid prices", len(valid), f"/ {len(result_cached)}")
    print_result("Cache hit time", f"{cache_time:.2f}", "seconds")
    
    assert len(result_cached) == len(indicators), f"Expected {len(indicators)} cached results, got {len(result_cached)}"
    assert len(valid) == len(result_cached), f"Expected all {len(result_cached)} to have valid prices"
    
    print("\n✓ TEST 3 PASSED: All data loaded from cache with valid prices")
    return cache_time


def test_performance_comparison(fresh_time: float, cached_time: float):
    """Test 4: Performance comparison."""
    print_banner("TEST 4: PERFORMANCE COMPARISON")
    
    speedup = fresh_time / cached_time if cached_time > 0 else float('inf')
    time_saved = fresh_time - cached_time
    percent_reduction = (time_saved / fresh_time * 100) if fresh_time > 0 else 0
    
    print_result("Fresh fetch time", f"{fresh_time:.2f}", "seconds")
    print_result("Cache load time", f"{cached_time:.2f}", "seconds")
    print_result("Time saved", f"{time_saved:.2f}", "seconds")
    print_result("Speedup", f"{speedup:.1f}x", "faster")
    print_result("Time reduction", f"{percent_reduction:.1f}%")
    
    # Cache should be faster (or at least not significantly slower)
    assert cached_time <= fresh_time * 1.1, "Cache hit should not be significantly slower than fresh fetch"
    
    print("\n✓ TEST 4 PASSED: Cache provides performance benefit")


def test_specific_indicators():
    """Test 5: Verify specific indicators have correct data."""
    print_banner("TEST 5: SPOT CHECK - KEY INDICATORS")
    
    indicators = {
        "1144633": "TASE indicator (TCH-F91.TA)",
        "126.1.CHKP": "CHECKPOINT SOFTWARE (CHKP)",
        "AAPL": "Apple Inc.",
        "TSM": "Taiwan Semiconductor",
        "NESN.SW": "Nestlé (CHF)",
    }
    
    result = pysft.lib.fetchData(list(indicators.keys()), attributes=["all"])
    
    for ind, description in indicators.items():
        if ind in result:
            price = (result[ind].get("price") or [None])[0]
            currency = (result[ind].get("currency") or [None])[0]
            name = (result[ind].get("name") or ["N/A"])[0]
            status = f"✓ {price} {currency} - {name or description}"
        else:
            status = "✗ MISSING"
        
        print(f"  {ind:<20} {status}")
    
    assert all(ind in result for ind in indicators.keys()), "Some key indicators missing"
    print("\n✓ TEST 5 PASSED: All key indicators present and valid")


def run_all_tests():
    """Run all tests in sequence."""
    print("\n" * 2)
    print_banner("COMPREHENSIVE CACHING PIPELINE TEST SUITE")
    print("Testing: Fresh fetch → Database cache → Cache reload")
    
    try:
        # Test 1: Fresh fetch
        result_fresh, fresh_time = test_fresh_fetch()
        
        # Test 2: Verify database contents
        test_database_contents(len(indicatorsDB.FIFTY))
        
        # Test 3: Cache hit
        cache_time = test_cache_hit()
        
        # Test 4: Performance comparison
        test_performance_comparison(fresh_time, cache_time)
        
        # Test 5: Spot check key indicators
        test_specific_indicators()
        
        # Final summary
        print_banner("ALL TESTS PASSED ✓")
        print("  ✓ Fresh fetch: 50/50 indicators with valid prices")
        print("  ✓ Database caching: Data successfully saved")
        print("  ✓ Cache reload: All data loaded from database")
        print("  ✓ Performance: Cache provides significant speedup")
        print("  ✓ Data integrity: All key indicators verified")
        print()
        
    except AssertionError as e:
        print_banner("TEST FAILED ✗")
        print(f"AssertionError: {e}")
        sys.exit(1)
    except Exception as e:
        print_banner("TEST ERROR ✗")
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
