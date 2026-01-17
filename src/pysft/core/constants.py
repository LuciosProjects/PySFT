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

# import os
# from dotenv import load_dotenv

from pysft.core.structures import CTimeRepr

# Load environment variables from .env file
# load_dotenv()

# General package constants
PACKAGE_NAME = "pysft"

# Memory-related constants
ONE_MB                      = (1024**2)         # One MB in bytes (1024 bytes in 1 KB, 1024 KB in 1 MB and so on...)
ONE_GB                      = (ONE_MB * 1024)   # One GB in bytes
INSTANCE_MAX_MEMORY         = ONE_GB * 2        # Max memory per PySFT instance (2 GB)
MAX_TASK_MEMORY_ALLOCATION  = ONE_MB * 200      # Max memory allocation per fetch task (200 MB)

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
USE_INTERNATIONAL_VAULT = False
SKIP_BIZPORTAL          = False
SKIP_THEMARKER          = True
SKIP_TASE               = False

TASE_GET_REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

TASE_CONTENT_REQUEST_HEADERS = {
    "accept": "*/*",
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    "origin": "REPLACE_WITH_ACTUAL_ORIGIN_URL",
    "Referer": "REPLACE_WITH_ACTUAL_REFERER_URL",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}

THEMARKER_QUOTE_TYPES = ["mtf", "etf", "stock"]
THEMARKER_QUERY_HASH = "1dcdf5374e423ecf9026280b13306f4409e9a4f24192667700f5d1ba11618d8b" 

TASE_HEAD_REQUEST_TIMEOUT = CTimeRepr(10)  # seconds
HTTPX_CLIENT_TIMEOUT = CTimeRepr(30)  # seconds
TASE_HTML_FETCH_TIMEOUT = CTimeRepr(60) # seconds

# multi-processing constants
YF_BATCH_SIZE = 30  # max indicators per yfinance batch request
YF_CONCURRENCY_LIMIT = 3  # max concurrent yfinance batch requests
RATELIMIT_PAUSE = CTimeRepr(2)  # nominal seconds to pause on rate limit hit

YF_K_SEMAPHORES = 5  # number of semaphores for limiting concurrency in yfinance fetcher
TASE_K_SEMAPHORES = 3  # number of semaphores for limiting concurrency in TASE fetcher

# Indicator request dictionary fields
INDICATOR_FIELD     = "indicator"
FETCH_TYPE_FIELD    = "fetch_type"
REQUEST_FIELD       = "request"

# Database constants
DB_ENABLED = False  # Enable database caching
DB_PATH = "pysft_cache.db"  # Default SQLite database path

# Cache TTL (Time-To-Live) in days
LONGTERM_TTL_DAYS = 365  # 1 year for rarely changing fields
MEDIUM_TTL_DAYS = 90     # 90 days for infrequently changing fields
SHORT_TTL_DAYS = 7       # 7 days for frequently changing metrics

# Field categorization by freshness requirements
IMMUTABLE_FIELDS = [
    "ISIN",  # Never changes
]

LONGTERM_TTL_FIELDS = [
    "name",       # Rarely changes (rebranding)
    "quoteType",  # Rarely reclassified
    "currency",   # Almost never changes
]

MEDIUM_TTL_FIELDS = [
    "briefSummary",  # Business updates, restructuring
]

SHORT_TTL_FIELDS = [
    "expense_rate",        # Fund fees
    "dividendYield",       # Dividend data
    "trailingPE",          # Price-to-earnings
    "forwardPE",           # Forward PE
    "beta",                # Volatility measure
    "avgDailyVolume3mnth", # Volume metrics
]

# Price fields - these are always fetched fresh for current data
# For historical data, they use date-based caching
PRICE_FIELDS = [
    "last",
    "open",
    "high",
    "low",
    "volume",
    "price",
    "change_pct",
    "market_cap",
]

# Historical fields that are stored with dates
HISTORICAL_FIELDS = PRICE_FIELDS + ["dates"]