# PySFT - Python Security Fetching Tool

[![PyPI version](https://img.shields.io/pypi/v/pysft.svg)](https://pypi.org/project/pysft/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

PySFT is a comprehensive Python package for fetching financial data from multiple sources (Yahoo Finance, TASE) with intelligent caching, async processing, and LLM-ready output formats. It provides Python API, REST API, and CLI interfaces for seamless integration into trading systems, portfolio analysis tools, and financial applications.

## ✨ Key Features

- **📊 Multi-Source Data**: Yahoo Finance (global markets), TASE Real-time & Historical (Israeli exchange)
- **⚡ High-Performance**: Async task scheduling with configurable concurrency, intelligent batching (30 indicators/batch)
- **💾 Smart Caching**: 2-tier TTL model with configurable expiration (immutable fields never expire, volatile fields refresh every 15 min)
- **🔄 3 Access Methods**: Python API, REST/HTTP endpoints, Command-line interface
- **📈 20+ Attributes**: OHLCV prices, dividend yield, market cap, P/E ratios, currency normalization, and more
- **🎯 3 Fetch Modes**: `"all"` (complete data), `"price"` (time-series only), `"info"` (metadata only)
- **💰 Fund Holdings Integration**: Fetch mutual fund/ETF asset composition from TASE
- **📍 Currency Support**: Automatic currency conversion for international securities (CHF, TWD, CNY, etc.)
- **🛡️ Error Resilience**: Graceful fallbacks, exponential backoff, detailed error reporting

## 📦 Installation

### From PyPI
```bash
pip install pysft
```

### From source
```bash
git clone https://github.com/LuciosProjects/PySFT
cd PySFT
pip install -e .
```

**Requirements**: Python 3.11+

## 🚀 Quick Start

### Python API
```python
from pysft.lib.fetchFinancialData import fetch_data

# Fetch price data for multiple indicators
data = fetch_data(
    indicators=['AAPL', 'MSFT', '1115.IL'],  # Stocks and TASE indicators
    attributes=['price', 'volume', 'change_pct'],
    period='1mo'
)

# Returns nested dict: {indicator: {attribute: [values], ...}, ...}
print(data['AAPL']['price'])  # [150.5, 151.2, 149.8, ...]
```

### REST API
```bash
# Start the HTTP server
python -m pysft.http_api

# In another terminal, query the API
curl "http://localhost:8000/fetch?indicators=AAPL,MSFT&attributes=price,volume&period=1mo"
curl "http://localhost:8000/health"
```

### Command Line
```bash
# Show version and cache status
python -m pysft.cli --version

# Disable caching for this session
python -m pysft.cli --no-cache

# Use custom cache database
python -m pysft.cli --cache-db /path/to/custom.db
```

## 📚 Usage Examples

### Fetch Multiple Indicators with All Data
```python
from pysft.lib.fetchFinancialData import fetch_data

# Get complete datasets
result = fetch_data(
    indicators=['AAPL', 'GOOGL', 'NESN.SW', 'INLONEXT:ZOMH'],
    attributes='all',  # All available attributes
    period='6mo',
    mode='all'  # Complete data
)
```

### Price-Only Time Series
```python
# Get OHLCV + change_pct only (faster, lower memory)
prices = fetch_data(
    indicators=['MSFT', 'TSLA'],
    mode='price'  # Returns: price, last, open, high, low, volume, change_pct, dates
)
```

### Metadata-Only Lookup
```python
# Get security information without prices
info = fetch_data(
    indicators=['AAPL'],
    mode='info'  # Returns: name, ISIN, currency, exchange, market_cap, P/E, etc.
)
print(info['AAPL']['name'])     # "Apple Inc."
print(info['AAPL']['currency'])  # "USD"
```

### Custom Date Range
```python
# Specify exact dates
data = fetch_data(
    indicators=['BTC-USD'],
    start='2023-01-01',
    end='2023-12-31'
)
```

### Fund Holdings Data
```python
from pysft.lib.fetchExposure import fetch_fund_holdings

# Get mutual fund/ETF asset composition
holdings = fetch_fund_holdings(
    fund_id='1144633',  # TASE mutual fund
    date='2024-01-15'
)
```

## 📋 Supported Data Sources

### Yahoo Finance
- **Coverage**: Global markets (US, EU, Asia-Pacific, etc.)
- **Indicators**: Stocks, ETFs, indices, cryptos, forex
- **Attributes**: OHLCV, dividends, splits, financial metrics
- **Real-time Updates**: Daily close and minute-level data
- **Rate Limiting**: 30 indicators per batch, configurable concurrency

### TASE (Tel Aviv Stock Exchange)
- **Coverage**: Israeli markets (stocks, ETFs, bonds, funds, indices)
- **Real-time**: Direct scraping with optimized request scheduling
- **Historical**: Time-series data with configurable granularity
- **Format Examples**: 
  - `'1115.IL'` - BLUE SHARES fund
  - `'INLONEXT:ZOMH'` - International symbol mapping
  - `'126.1.CHKP'` - Checkpoint Software (mapped to US ticker)

## 🏷️ Supported Attributes

### Price & Volume
| Attribute | Source | Description |
|-----------|--------|-------------|
| `date` | All | Date of the data point |
| `price` / `last` | All | Latest closing price |
| `open` | YF, TASE | Opening price |
| `high` | YF, TASE | Highest price of the period |
| `low` | YF, TASE | Lowest price of the period |
| `volume` | YF, TASE | Trading volume |
| `change_pct` | All | Percentage change |

### Financial Metrics
| Attribute | Source | Description |
|-----------|--------|-------------|
| `currency` | All | Quote currency (USD, ILS, EUR, CHF, etc.) |
| `market_cap` | YF, TASE | Market capitalization |
| `dividendYield` | YF, TASE | Annual dividend yield (%) |
| `trailingPE` | YF, TASE | P/E ratio (trailing 12 months) |
| `forwardPE` | YF | P/E ratio (forward estimate) |
| `beta` | YF | Price volatility vs. market |
| `expense_rate` | YF, TASE | Fund expense ratio (%) |

### Metadata
| Attribute | Source | Description |
|-----------|--------|-------------|
| `name` | All | Security name |
| `ISIN` | YF, TASE | International identification number |
| `quoteType` | YF, TASE | Type (EQUITY, ETF, CRYPTOCURRENCY, etc.) |
| `exchange` | All | Trading exchange |
| `inceptionDate` | YF, TASE | Fund launch date |

## ⚙️ Advanced Features

### Intelligent Caching
```python
from pysft.core import constants

# Configure cache location
constants.DB_PATH = '/custom/path/pysft_cache.db'

# Disable caching completely
constants.DB_ENABLED = False

# Cache features:
# - Immutable fields (name, ISIN, currency): never expire
# - Volatile fields (prices, volumes): expire after 15 minutes
# - Automatic TTL-based refresh on query
```

### Async Task Scheduling
```python
from pysft.core.task_scheduler import taskScheduler
from pysft.core.models import _fetchRequest

# Configure concurrency
scheduler = taskScheduler(
    max_concurrent_requests=10,      # Parallel request limit
    memory_budget_mb=500,             # Max memory for task queue
    semaphore_wait_timeout_sec=30     # Request timeout
)

# Scheduler features:
# - Memory-aware task queuing
# - Configurable semaphore-based rate limiting
# - Worker pool with automatic backpressure
```

### Custom Database Configuration
```python
from pysft.core.database import DatabaseManager

# Use custom SQLite database
db = DatabaseManager(db_path='/data/custom_cache.db')

# Cache historical data
db.cache_historical_data(
    indicator='AAPL',
    open_prices=[100.5, 101.2, 100.8],
    high_prices=[101.0, 102.3, 101.5],
    low_prices=[100.0, 100.8, 100.0],
    close_prices=[100.8, 101.0, 101.2],
    volumes=[50000000, 45000000, 55000000],
    change_pcts=[0.5, 1.2, -0.2],
    fetch_date='2024-01-15'
)

# Retrieve cached data
data = db.get_cached_data(indicator='AAPL')
prices = db.get_historical_data(indicator='AAPL', days=30)
```

### Batch Processing Control
```python
from pysft.core import constants

# Adjust batch size for Yahoo Finance requests
constants.YF_BATCH_SIZE = 50  # Larger batches (default: 30)

# This affects:
# - Network efficiency (fewer requests)
# - Memory usage (more data in flight)
# - API rate limits (fewer hits per second)
```

### Currency Normalization
```python
from pysft.core.yf_specific_utils import get_usd_conversion_factor

# Automatic conversion for international securities
data = fetch_data(
    indicators=['NESN.SW', 'TSM', 'BABA'],  # CHF, TWD, CNY respectively
    attributes='price'
)

# Prices automatically converted to USD equivalent
# CHF (Swiss Franc) → USD
# TWD (Taiwan Dollar) → USD
# CNY (Chinese Yuan) → USD
```

## 🏗️ Architecture Overview

### Components
- **Fetcher Manager** (`core/fetcher_manager.py`): Orchestrates requests across all data sources with caching
- **Task Scheduler** (`core/task_scheduler.py`): Async worker pool with memory budgets and rate limiting
- **Database Manager** (`core/database.py`): SQLite-based caching with TTL model and automatic refresh
- **Fetchers** (`fetchers/`): Yahoo Finance, TASE real-time, TASE historical implementations
- **Holdings API** (`holdings/`): Fund composition and asset exposure analysis

### Data Flow
```
API Request
    ↓
[Cache Hit?] → Return cached data (with TTL check)
    ↓ (miss)
[Route by Source]
    ├→ Yahoo Finance fetcher
    ├→ TASE real-time scraper
    ├→ TASE historical fetcher
    ↓
[Async Task Scheduler] → Batch & execute requests
    ↓
[Results Aggregator] → Merge data from all sources
    ↓
[Database Cache] → Store with TTL metadata
    ↓
[Output Formatter] → Dict/JSON/DataFrame
    ↓
Return to user
```

### Database Schema
```sql
-- Indicator metadata
CREATE TABLE indicator_attributes (
    id INTEGER PRIMARY KEY,
    indicator TEXT,
    attribute TEXT,
    value TEXT,
    data_type TEXT,
    fetch_date TIMESTAMP,
    expiration_date TIMESTAMP
);

-- Historical price data
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY,
    indicator TEXT,
    date DATE,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    volume INTEGER,
    change_pct REAL,
    fetch_date TIMESTAMP
);
```

## 📊 Output Formats

### Nested Dictionary (Default)
```python
result = fetch_data(['AAPL'], attributes=['price', 'volume', 'change_pct'])
# {
#     'AAPL': {
#         'price': [150.5, 151.2, 149.8, ...],
#         'volume': [50000000, 45000000, 55000000, ...],
#         'change_pct': [0.5, 1.2, -0.2, ...]
#     }
# }
```

### JSON Export
```python
import json
data = fetch_data(['AAPL', 'GOOGL'])
json_str = json.dumps(data)
```

### Pandas DataFrame
```python
import pandas as pd
data = fetch_data(['AAPL', 'MSFT'], attributes=['price', 'volume'])
df = pd.DataFrame(data).T  # Rows: indicators, Columns: attributes
```

## 🔍 Error Handling & Debugging

### Graceful Degradation
- Missing indicator → skip with warning
- Partial data from source → return available data
- Network timeout → retry with exponential backoff
- Cache miss → transparent fallback to fresh fetch

### Debugging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable detailed logging of all requests
data = fetch_data(['AAPL'], attributes='all')
# Logs: routing decisions, cache hits/misses, API calls, errors
```

### Common Issues
| Issue | Solution |
|-------|----------|
| "Indicator not found" | Check ticker format (AAPL, 1115.IL, INLONEXT:ZOMH) |
| "No cached data" | First fetch always gets fresh data; use `period` param |
| "Rate limited" | Reduce batch size or add delays via `taskScheduler` config |
| "Currency mismatch" | Use standardized tickers (AAPL for US stocks, 1115.IL for TASE) |

## 📝 Configuration

### Environment Variables
```bash
# .env file or system environment
PYSFT_DB_ENABLE=true              # Enable/disable caching
PYSFT_DB_PATH=/custom/cache.db    # Custom cache location
PYSFT_CACHE_TTL_MINUTES=15        # Cache expiration (default: 15)
PYSFT_MAX_CONCURRENT=10            # Parallel request limit
PYSFT_MEMORY_BUDGET_MB=500         # Task queue memory limit
```

### Programmatic Configuration
```python
from pysft.core import constants

constants.DB_ENABLED = True
constants.DB_PATH = '/data/pysft_cache.db'
constants.YF_BATCH_SIZE = 50
constants.TASE_TIMEOUT_SEC = 30
```

## 🧪 Testing

Run the comprehensive test suite:
```bash
# All tests
python -m pytest tests/

# Specific test
python -m pytest tests/test_caching_pipeline.py -v

# With coverage
python -m pytest --cov=src/pysft tests/
```

## 🤝 Contributing

Contributions welcome! Areas of interest:
- Additional data sources (Crypto, Forex brokers)
- Enhanced caching strategies
- WebSocket real-time updates
- More financial indicators
- Performance optimizations

## 📄 License

Proprietary - See [LICENSE](LICENSE) file

## 🔗 Links

- **Repository**: https://github.com/LuciosProjects/PySFT
- **PyPI**: https://pypi.org/project/pysft/
- **Data Sources**: 
  - [Yahoo Finance](https://finance.yahoo.com/)
  - [TASE - Tel Aviv Stock Exchange](https://www.tase.co.il/)

## 📞 Support

For issues, questions, or feature requests, please open a GitHub issue or contact the maintainers.

---

**Last Updated**: April 2024  
**Version**: 1.2.0  
**Python**: 3.11+
