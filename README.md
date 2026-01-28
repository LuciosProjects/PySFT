# PySFT
PySFT (Python Security Fetching Tool) is a Python package that fetches financial data for given securities and performs analysis using a LLM agent

The data fetching is being done by scraping the web:
- For US/Global markets, the package is using yfinance Python package to fetch data.
- for TASE, regular scraping is being used, tuned for optimal running time

## Minimal HTTP API
Run a lightweight HTTP server using the standard library:

```bash
python -m pysft.http_api
```

Endpoints:
- `GET /health`
- `GET /fetch?indicators=MSFT,AAPL&attributes=price,volume&period=1mo`
