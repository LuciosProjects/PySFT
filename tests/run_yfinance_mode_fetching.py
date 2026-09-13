from pathlib import Path
import sys
import importlib

import pandas as pd

# tests/* -> project root -> src
pysft_src = Path(__file__).resolve().parents[1] / "src"
if str(pysft_src) not in sys.path:
    sys.path.insert(0, str(pysft_src))

from pysft.core.enums import E_FetchMode
from pysft.core.models import _YF_fetchReq_Container
from pysft.core.structures import indicatorRequest

yf_fetcher = importlib.import_module("pysft.fetchers.fetch_yfinance")


class _DemoTicker:
    def __init__(self):
        self.info = {
            "quoteType": "EQUITY",
            "longName": "Demo Security",
            "currency": "USD",
            "exchange": "XNAS",
        }
        self.isin = "US0000000000"

    def history(self, period="max", auto_adjust=True):
        raise AssertionError("history should not be called in info mode")


class _DemoTickers:
    def __init__(self, symbols):
        self.tickers = {symbol: _DemoTicker() for symbol in symbols}


def main() -> int:
    download_called = {"value": 0}

    def _download_stub(*args, **kwargs):
        download_called["value"] += 1
        raise AssertionError("yf.download should not be called in mode='info'")

    original_download = yf_fetcher.yf.download
    original_tickers = yf_fetcher.yf.Tickers

    try:
        yf_fetcher.yf.download = _download_stub
        yf_fetcher.yf.Tickers = lambda symbols: _DemoTickers(symbols)

        req = indicatorRequest("AAPL", [pd.Timestamp("2024-01-01")], mode=E_FetchMode.INFO)
        container = _YF_fetchReq_Container([req], [pd.Timestamp("2024-01-01")], mode=E_FetchMode.INFO)

        yf_fetcher.fetch_yfinance(container)

        assert container.success is True
        assert req.success is True
        assert download_called["value"] == 0
        assert req.data.name == "Demo Security"
        print("PASS: mode='info' skipped yf.download and history calls while populating metadata.")
        return 0

    finally:
        yf_fetcher.yf.download = original_download
        yf_fetcher.yf.Tickers = original_tickers


if __name__ == "__main__":
    raise SystemExit(main())
