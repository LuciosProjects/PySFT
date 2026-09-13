# PySFT (Python Security Fetching Tool) - Complete Features List

**Version:** 1.2.0  
**Purpose:** Python package for fetching financial data from multiple sources (Yahoo Finance, TASE) with intelligent caching, scheduling, and analysis capabilities.

---

## 1. MAIN API FUNCTIONS

### Core Data Fetching Functions (`src/pysft/lib/fetchFinancialData.py`)

**Primary Function:**
- `fetchData(indicators, attributes, period, start, end, mode)` / `fetch_data()` (PEP 8 alias)
  - Main entry point for fetching financial data
  - Returns nested dictionary: `{indicator: {"dates": [...], attr: [...], ...}}`
  - Supports multiple indicators and attributes in single call

**Output Format Variants:**
- `fetch_data_as_dict()` - Returns data as Python dictionary
- `fetch_data_as_json()` - Returns data as JSON string
- `fetchData_as_df()` - Returns data as MultiIndex pandas DataFrame (Indicator, Attribute)

---

## 2. HTTP API ENDPOINTS

Location: `src/pysft/http_api.py`

**Running the Server:**
```bash
python -m pysft.http_api
# or
run(host="127.0.0.1", port=8000)
```

**Endpoints:**

| Endpoint | Method | Parameters | Purpose |
|----------|--------|-----------|---------|
| `/health` | GET | - | Health check, returns `{"status": "ok"}` |
| `/fetch` | GET | `indicators` (required), `attributes`, `period`, `start`, `end` | Fetch data via HTTP, returns `{"data": {...}}` |

**Query Parameter Examples:**
```
GET /fetch?indicators=MSFT,AAPL&attributes=price,volume&period=1mo
```

---

## 3. COMMAND-LINE INTERFACE (CLI)

Location: `src/pysft/cli.py`

**Available Options:**

| Option | Type | Purpose |
|--------|------|---------|
| `--version` | flag | Display package version |
| `--no-cache` | flag | Disable database caching, fetch fresh data from web |
| `--cache-db PATH` | string | Custom path to SQLite cache database |

**Usage:**
```bash
python -m pysft --no-cache
python -m pysft --cache-db /path/to/cache.db
```

---

## 4. DATA SOURCES & FETCHERS

### Yahoo Finance Fetcher
- **Location:** `src/pysft/fetchers/fetch_yfinance.py`
- **Supports:** US/Global markets, stocks, ETFs, mutual funds
- **Data:** Real-time and historical price data, company metadata
- **Features:**
  - Batch request processing (configurable batch size: default 30)
  - Concurrent request handling (default 3 concurrent requests)
  - Metadata extraction (ISIN, quote type, exchange, currency, name)
  - Multiple fetch attempts with backoff strategy
  - Rate limiting pause on limit hits

### TASE (Tel Aviv Stock Exchange) Fetchers

#### TASE Real-Time Fetcher
- **Location:** `src/pysft/fetchers/TASE.py`
- **Data Source:** TheMarker website (finance.themarker.com)
- **Supports:**
  - MTF (Mutual Trading Funds)
  - ETF (Exchange Traded Funds)
  - Securities
  - THEMARKER (quote type)
- **Features:**
  - Quote type inference from URL
  - Dividend data fetching from Bizportal
  - Multiple data sources routing based on asset type
  - Automatic YFINANCE equivalent detection to reduce TASE load

#### TASE Historical Fetcher
- **Location:** `src/pysft/fetchers/TASE_historical.py`
- **Purpose:** Fetch historical timeseries data for TASE securities

### Data Source Configuration
- **Constants:** `src/pysft/core/constants.py`
  - `USE_INTERNATIONAL_VAULT = True` - Use international symbol vault
  - `SKIP_BIZPORTAL = False` - Enable Bizportal fetching
  - `SKIP_THEMARKER = True` - Disable TheMarker fetching
  - `SKIP_TASE = False` - Enable TASE fetching

---

## 5. FETCH MODES

Three fetch modes control what type of data is returned:

| Mode | Attributes Returned | Use Case |
|------|-------------------|----------|
| `"all"` | price, last, open, high, low, volume, change_pct, dates, info fields | Complete dataset |
| `"price"` | price, last, open, high, low, volume, change_pct, dates | Time-series price data only |
| `"info"` | Metadata only (name, ISIN, quoteType, currency, exchange, inception date, etc.) | Static information without prices |

---

## 6. SUPPORTED INDICATORS & ATTRIBUTES

### Indicators
- **Ticker symbols:** MSFT, AAPL, GOOG, etc. (Yahoo Finance)
- **TASE codes:** 5142088, 5111422, 1144633 (mutual funds, ETFs)
- **Aliases supported:** ticker, symbol

### Supported Attributes

#### Price/Time-Series Attributes
| Attribute | Aliases | Description |
|-----------|---------|-------------|
| `price` | - | Fetch price data |
| `last` | `close` | Last/closing price per timestamp |
| `open` | - | Opening price per timestamp |
| `high` | - | Highest price per timestamp |
| `low` | - | Lowest price per timestamp |
| `volume` | `vol` | Trading volume per timestamp |
| `change_pct` | `change`, `change%` | Percentage price change per timestamp |
| `dates` | `date`, `period`, `periods` | Timestamps of data points |

#### Metadata/Info Attributes
| Attribute | Aliases | Description |
|-----------|---------|-------------|
| `indicator` | `symbol`, `ticker` | Security identifier |
| `name` | - | Full security name |
| `ISIN` | `isin` | International Securities Identification Number |
| `quoteType` | `quote_type`, `type` | Security type (equity, ETF, mutual fund, etc.) |
| `currency` | - | Currency code (USD, EUR, ILS, etc.) |
| `exchange` | `market`, `exc` | Exchange market code (XNAS, XNYS, XTAE) |
| `inceptionDate` | `inception_date` | First issue date |
| `market_cap` | `marketcap`, `cap` | Market capitalization |
| `expense_rate` | `expenserate`, `expense` | Annual expense rate (for funds) |
| `dividendYield` | `dividend_yield`, `dividend`, `yield` | Dividend yield percentage |
| `trailingPE` | `trailing_pe`, `pe` | Trailing Price-to-Earnings ratio |
| `forwardPE` | `forward_pe` | Forward P/E ratio |
| `beta` | - | Beta volatility measure |
| `avgDailyVolume3mnth` | `avg_daily_volume_3mnth`, `avgvolume` | 3-month average daily volume |

#### Special Attribute Groups
- `"all"` - Fetch all available attributes
- `"info"` - Fetch all metadata fields (excludes price/timeseries)

---

## 7. TIME PERIOD PARAMETERS

### By Named Period
- `period`: "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"

### By Date Range
- `start`: Start date (format: "YYYY-MM-DD")
- `end`: End date (format: "YYYY-MM-DD")

---

## 8. DATABASE CACHING FEATURES

Location: `src/pysft/core/database.py`

### Cache Architecture
- **Storage:** SQLite database (default: `src/pysft/data/pysft_cache.db`)
- **Tables:**
  - `indicator_attributes`: Per-attribute metadata with timestamps
  - `price_history`: Historical time-series data with per-row timestamps
- **Thread-Safe:** Built-in context manager for concurrent access

### TTL (Time-To-Live) Model - 2-Tier System

**Immutable Fields (Never Expire):**
- indicator, name, ISIN, inceptionDate, quoteType, exchange

**Volatile Fields (15-Minute TTL):**
- All price/volume data, market_cap, dividendYield, etc.
- Today's timeseries data

**Historical Data Rules:**
- Historical data (except today) is cached indefinitely
- Today's data refreshes every 15 minutes
- Max delta to consider cached dates as full coverage: 31 days

### Cache Configuration
- `DB_ENABLED = True` - Enable/disable caching
- `DB_PATH` - Custom database path
- `TTL_MINUTES = 15` - Refresh interval for volatile fields
- `CACHED_DATES_MAX_DELTA = 31` - Days threshold for cache validity

### Dynamic Field Detection
- Timeseries vs scalar field categorization from `_indicator_data` dataclass
- Automatic field type inspection for intelligent caching

---

## 9. TASK SCHEDULING & EXECUTION

Location: `src/pysft/core/task_scheduler.py`

### Scheduler Features
- **Async execution** of fetch tasks using asyncio
- **Memory budgeting:** Token-based RAM allocation system
- **Concurrency control:** Semaphore-based rate limiting
- **Retry logic:** Configurable attempts and exponential backoff

### Configuration Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_ATTEMPTS` | 3 | Max fetch attempts per task |
| `MAX_YF_ATTEMPTS` | 6 | Max Yahoo Finance attempts (higher due to batching) |
| `YF_BATCH_SIZE` | 30 | Indicators per Yahoo Finance batch request |
| `YF_CONCURRENCY_LIMIT` | 3 | Max concurrent Yahoo Finance batches |
| `TASE_K_SEMAPHORES` | 3 | Concurrent TASE fetchers |
| `YF_K_SEMAPHORES` | 5 | Concurrent Yahoo Finance fetchers |
| `RATELIMIT_PAUSE` | 2s | Pause on rate limit hit |
| `INSTANCE_MAX_MEMORY` | 2 GB | Max memory per PySFT instance |
| `MAX_TASK_MEMORY_ALLOCATION` | 200 MB | Max memory per task |

### Task Execution Flow
1. **Initialization:** Classify fetch types (YFINANCE, TASE, DATABASE)
2. **Optimization:** Find Yahoo Finance equivalents for TASE indicators
3. **Creation:** Create task list based on fetch types
4. **Scheduling:** Async scheduler with memory and concurrency gates
5. **Caching:** Auto-cache newly fetched data
6. **Aggregation:** Merge cached and newly fetched results

---

## 10. CORE DATA STRUCTURES

Location: `src/pysft/core/structures.py`

### `_indicator_data` (Dataclass)
Holds all fetched indicator information:
```python
@dataclass
class _indicator_data:
    indicator: str              # Ticker/code
    name: str                   # Full name
    ISIN: str                   # Securities ID
    inceptionDate: pd.Timestamp # Issue date
    quoteType: str              # Type classification
    dates: list[pd.Timestamp]   # Data point timestamps
    currency: str               # Currency code
    exchange: str               # Market code
    price: float | list[float]  # Price data
    last: float | list[float]   # Last traded price
    open: float | list[float]   # Opening prices
    high: float | list[float]   # High prices
    low: float | list[float]    # Low prices
    volume: int | list[int]     # Trading volume
    change_pct: float | list[float]  # Price changes
    market_cap: float           # Market capitalization
    expense_rate: float         # Expense ratio (funds)
    dividendYield: float        # Dividend yield
    trailingPE: float           # Trailing P/E
    forwardPE: float            # Forward P/E
    beta: float                 # Volatility measure
    avgDailyVolume3mnth: int    # 3-month avg volume
```

### `indicatorRequest` (Dataclass)
Represents a single indicator fetch request with metadata and results.

### `_fetchRequest` (Dataclass)
Represents the complete user fetch request with:
- Normalized indicators list
- Parsed attributes list
- Resolved date range (start_ts, end_ts)
- Fetch mode

---

## 11. ENUMS & TYPE DEFINITIONS

Location: `src/pysft/core/enums.py`

### Fetch Modes
- `E_FetchMode.ALL` - Complete data
- `E_FetchMode.PRICE` - Price/volume only
- `E_FetchMode.INFO` - Metadata only

### Fetch Types
- `E_FetchType.YFINANCE` - Yahoo Finance source
- `E_FetchType.TASE` - Israeli stock exchange
- `E_FetchType.DATABASE` - Cached local data

### Indicator Types
- `E_IndicatorType.YFINANCE` - YF ticker
- `E_IndicatorType.TASE_MTF` - Mutual fund
- `E_IndicatorType.TASE_ETF` - Traded fund
- `E_IndicatorType.TASE_SEC` - Security
- `E_IndicatorType.TASE_THEMARKER` - TheMarker quote type

### Data Sources
- `E_DataSource.YFINANCE` - Yahoo Finance
- `E_DataSource.TASE` - TASE exchange
- `E_DataSource.THEMARKER` - TheMarker website
- `E_DataSource.INVESTINGCOM` - Investing.com
- `E_DataSource.DATABASE` - Local cache

### TASE Listing Status
- `TASEListingStatus.ACTIVE` - Currently traded
- `TASEListingStatus.MERGED` - Merged security
- `TASEListingStatus.LIQUIDATED` - Liquidated
- `TASEListingStatus.DELISTED` - Delisted

---

## 12. FUND HOLDINGS & EXPOSURE (Prototyping)

Location: `prototyping/test_TASE_Fund_Expo.py`

### Holdings Data Fetching
- **Function:** `test_TASE_Fund_Expo(indicator, quote_type, session)`
- **Data Source:** TASE Maya API (`https://maya.tase.co.il/api/v1/funds/{indicator}/assets`)
- **Supports:** MTF (Mutual Funds), ETF

### Holdings Information Returned
For each asset in a fund/ETF:
- `id` - Asset ID
- `fundId` - Fund identifier
- `managerId` - Fund manager ID
- `managerName` - Fund manager name
- `assetId` - Asset identifier
- `assetName` - Asset name
- `assetType` - Asset type classification
- `fundPercentage` - Percentage of fund portfolio
- `assetValue` - Asset value in NIS (can convert to USD)
- `quantity` - Number of shares/units
- `tradePlace` - Trading venue
- `ticker` - Asset ticker symbol

### Features
- Pagination support (20 assets per page)
- Automatic referer header injection
- Error handling for API requests
- Conversion-ready currency format (NIS)

---

## 13. UTILITIES & TOOLS

### Currency & Scale Normalization (`src/pysft/core/constants.py`)

**Currency Factors:**
```python
CURRENCY_NORMALIZATION = {
    "USD": 1.0,
    "EUR": 1.0,
    "ILS": 1.0,
    "ILA": 0.01  # Israeli Agora (1 ILS = 100 ILA)
}
```

**Numeric Scale Factors:**
- thousand: 1e3
- million / m / M: 1e6
- billion / bn / b / B: 1e9

**Currency Symbols to Code:**
- $ → USD
- € → EUR
- ₪ → ILS
- ¥ → JPY
- £ → GBP

### Translator Tool (`src/pysft/tools/translator.py`)
- Hebrew to English translation utility for TASE-specific content

### Logger Tool (`src/pysft/tools/logger.py`)
- Centralized logging configuration for all modules

### TASE Utilities (`src/pysft/core/tase_specific_utils.py`)
- TASE-specific constants and helper functions
- Exchange calendar integration (XTAE calendar)
- Duplicate TASE security database
- HTML scraping utilities for TASE data extraction

---

## 14. INPUT VALIDATION & ATTRIBUTE ALIASES

Location: `src/pysft/core/io.py`

### Supported Attribute Aliases
Flexible input accepting multiple names for same attributes:
- Price variants: price, last, close
- Volume variants: volume, vol
- Date variants: dates, date, period, periods
- Exchange variants: exchange, market, exc
- And many more (see complete mapping in code)

### Input Normalization
- Case-insensitive attribute parsing
- Comma-separated list support
- Automatic conversion to canonical names

---

## 15. PACKAGE STRUCTURE & EXPORTS

**Main Package:** `src/pysft/__init__.py`
- Exports: `lib`, `data` submodules
- Version: Accessible via `__version__`

**Submodules:**
- `pysft.lib` - Main API functions (fetchData, etc.)
- `pysft.data` - Data resources (security lists, international symbols, indicator lists)
- `pysft.core` - Core utilities, models, and structures
- `pysft.fetchers` - Data source fetchers
- `pysft.tools` - Logging and utility tools
- `pysft.http_api` - HTTP server interface

---

## 16. CONFIGURATION FILES

### Project Configuration
- `pyproject.toml` - Package metadata and development configuration
- `requirements.txt` - Package dependencies
- `requirements.lock.txt` - Locked dependency versions

### Data Resources
- `src/pysft/data/indicator_international_symbols.json` - International symbol mappings
- `src/pysft/data/international_symbols_archive.json` - Historical symbol data
- `src/pysft/data/securitiesinfo.csv` - Securities reference data
- `src/pysft/data/TASE_security_list.py` - TASE security listings

---

## 17. ERROR HANDLING & RETRY STRATEGY

### Retry Configuration
- **Max Attempts:** Configurable (default: 3)
- **Backoff:** Incremental with configurable base
- **Half-Span Expansion:** Initial (3 days) → Increment (3 days) per attempt
- **Timeout Management:** Per-request context

### Error Reporting
- Detailed error messages with attempt numbers
- Stack traces logged for debugging
- Graceful fallback to other data sources

---

## 18. PERFORMANCE FEATURES

### Optimization Strategies
1. **Smart Caching:** TTL-based cache invalidation
2. **Batch Processing:** Grouped requests to reduce API calls
3. **Concurrent Fetching:** Async task execution with memory budgeting
4. **YFINANCE Equivalent Detection:** Reduces TASE load by finding duplicates
5. **Connection Pooling:** Session reuse across requests
6. **Rate Limiting:** Intelligent pause on rate limit hits

### Concurrency Control
- Semaphore-based limiting for each data source
- Memory budget enforcement
- Backoff strategies on failures

---

## 19. EXAMPLE USAGE

### Basic Price Data
```python
from pysft.lib.fetchFinancialData import fetch_data

data = fetch_data(
    indicators=["MSFT", "AAPL"],
    attributes=["price", "volume"],
    period="1mo",
    mode="price"
)
```

### Complete Metadata
```python
data = fetch_data(
    indicators="MSFT",
    mode="info"  # Returns metadata only
)
```

### Custom Date Range
```python
data = fetch_data(
    indicators="MSFT",
    start="2024-01-01",
    end="2024-12-31",
    attributes=["open", "close", "volume"]
)
```

### TASE Holdings
```python
from prototyping.test_TASE_Fund_Expo import test_TASE_Fund_Expo
from requests import Session

holdings = test_TASE_Fund_Expo("5142088", "MTF", Session())
```

### HTTP API
```bash
curl "http://localhost:8000/fetch?indicators=MSFT,AAPL&attributes=price,volume&period=1mo"
```

---

## 20. SUMMARY STATISTICS

- **Data Sources:** 3 (Yahoo Finance, TASE Real-time, TASE Historical)
- **Supported Attributes:** 20+ (price, volume, OHLC, metadata, ratios)
- **Fetch Modes:** 3 (all, price, info)
- **API Access Methods:** 3 (Python functions, HTTP endpoints, CLI)
- **Output Formats:** 3 (dict, JSON, DataFrame)
- **Cache Strategies:** 2-tier TTL model
- **Concurrency Strategy:** Async with semaphores and memory budgeting

