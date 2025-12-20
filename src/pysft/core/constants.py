"""
PySFT_Constants
----------------

Centralized constants for the PySFT project.

This module defines immutable values used across the codebase to avoid magic
numbers/strings, improve readability, and enable consistent configuration.
Typical contents include:
- Application-wide string literals (e.g., environment keys, resource names)
- Default configuration values (e.g., timeouts, buffer sizes)
- Numeric limits and thresholds (e.g., retries, max items)
- Standardized file extensions, MIME types, and paths
- Enum-like string constants for modes, statuses, and event types

Import this module wherever shared constants are needed to keep values
declarative, discoverable, and maintainable.
"""

from pysft.core.structures import CTimeRepr

# General package constants
PACKAGE_NAME = "pysft"

# Memory-related constants
ONE_MB                      = (1024**2)         # One MB in bytes (1024 bytes in 1 KB, 1024 KB in 1 MB and so on...)
ONE_GB                      = (ONE_MB * 1024)   # One GB in bytes
INSTANCE_MAX_MEMORY         = ONE_GB * 2       # Max memory per PySFT instance (2 GB)

# Fetcher constants
MAX_ATTEMPTS            = 3  # max fetch attempts
MAX_YF_ATTEMPTS         = 6  # max yfinance fetch attempts, takes more bacause of batching and rate limits
INITIAL_DAYS_HALF_SPAN  = 3 # initial days half-span for data fetch window
HALF_SPAN_INCREMENT     = 3 # days to increment half-span per attempt

CURRENCY_NORMALIZATION = {
    # Currency conversion factors for calculations

    "USD": {"factor": 1.0, "alias": "USD"},     # US Dollar
    "EUR": {"factor": 1.0, "alias": "EUR"},     # Euro
    "ILS": {"factor": 1.0, "alias": "ILS"},     # Israeli Shekel
    "ILA": {"factor": 0.01, "alias": "ILS"},    # Israeli Agora (1 ILS = 100 ILA)
}

# YFinance-specific constants
YF_REQUIRED_DATAFRAME_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
YFINANCE_DATE_FORMAT = "%Y-%m-%d"
YF_API_CALL_TIMEOUT = CTimeRepr(20)  # seconds

# TASE specific constants
TASE_REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

# multi-processing constants
YF_BATCH_SIZE = 30  # max indicators per yfinance batch request
YF_CONCURRENCY_LIMIT = 3  # max concurrent yfinance batch requests
RATELIMIT_PAUSE = CTimeRepr(2)  # nominal seconds to pause on rate limit hit

# Indicator request dictionary fields
INDICATOR_FIELD     = "indicator"
FETCH_TYPE_FIELD    = "fetch_type"
REQUEST_FIELD       = "request"