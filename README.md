# PySFT
PySFT (Python Security Fetching Tool) is a Python package that fetches financial data for given securities and performs analysis using an LLM agent

The data fetching is being done by scraping the web:
- For US/Global markets, the package is using yfinance python package to fetch data.
- for TASE, regular scraping is being used, tuned for optimal running time
