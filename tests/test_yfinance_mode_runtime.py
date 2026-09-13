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


class _DummyTicker:
    def __init__(self) -> None:
        self.info = {
            "quoteType": "EQUITY",
            "longName": "Apple Inc.",
            "currency": "USD",
            "exchange": "XNAS",
            "averageDailyVolume3Month": 100,
            "marketCap": 1000,
            "yield": 0.02,
            "trailingPE": 20.0,
            "forwardPE": 18.0,
            "beta": 1.1,
        }
        self.isin = "US0378331005"

    def history(self, period="max", auto_adjust=True):
        index = pd.DatetimeIndex([pd.Timestamp("2024-01-01")])
        return pd.DataFrame(
            {
                "Open": [100.0],
                "High": [101.0],
                "Low": [99.0],
                "Close": [100.5],
                "Volume": [1000],
            },
            index=index,
        )


class _DummyTickers:
    def __init__(self, symbols):
        self.tickers = {symbol: _DummyTicker() for symbol in symbols}


def _make_download_frame(symbol: str) -> pd.DataFrame:
    index = pd.DatetimeIndex([pd.Timestamp("2024-01-01")])
    columns = pd.MultiIndex.from_tuples(
        [
            ("Open", symbol),
            ("High", symbol),
            ("Low", symbol),
            ("Close", symbol),
            ("Volume", symbol),
        ]
    )
    data = [[100.0, 101.0, 99.0, 100.5, 1000]]
    return pd.DataFrame(data, index=index, columns=columns)


def test_info_mode_skips_download_and_history(monkeypatch):
    calls = {"download": 0, "history": 0}

    def _download_stub(*args, **kwargs):
        calls["download"] += 1
        return _make_download_frame("AAPL")

    class _NoHistoryTicker(_DummyTicker):
        def history(self, period="max", auto_adjust=True):
            calls["history"] += 1
            raise AssertionError("history should not be called in info mode")

    class _NoHistoryTickers:
        def __init__(self, symbols):
            self.tickers = {symbol: _NoHistoryTicker() for symbol in symbols}

    monkeypatch.setattr(yf_fetcher.yf, "download", _download_stub)
    monkeypatch.setattr(yf_fetcher.yf, "Tickers", lambda symbols: _NoHistoryTickers(symbols))

    req = indicatorRequest("AAPL", [pd.Timestamp("2024-01-01")], mode=E_FetchMode.INFO)
    container = _YF_fetchReq_Container([req], [pd.Timestamp("2024-01-01")], mode=E_FetchMode.INFO)

    yf_fetcher.fetch_yfinance(container)

    assert container.success is True
    assert req.success is True
    assert calls["download"] == 0
    assert calls["history"] == 0
    assert req.data.name == "Apple Inc."


def test_price_mode_uses_download(monkeypatch):
    calls = {"download": 0}

    def _download_stub(*args, **kwargs):
        calls["download"] += 1
        return _make_download_frame("AAPL")

    monkeypatch.setattr(yf_fetcher.yf, "download", _download_stub)
    monkeypatch.setattr(yf_fetcher.yf, "Tickers", lambda symbols: _DummyTickers(symbols))

    req = indicatorRequest("AAPL", [pd.Timestamp("2024-01-01")], mode=E_FetchMode.PRICE)
    container = _YF_fetchReq_Container([req], [pd.Timestamp("2024-01-01")], mode=E_FetchMode.PRICE)

    yf_fetcher.fetch_yfinance(container)

    assert calls["download"] > 0


def test_price_mode_skips_info_fetch(monkeypatch):
    """price mode must not touch ticker.info or ticker.history (no metadata network calls)."""

    class _NoInfoTicker(_DummyTicker):
        @property
        def info(self):
            raise AssertionError("ticker.info must not be accessed in price mode")

        def history(self, period="max", auto_adjust=True):
            raise AssertionError("ticker.history must not be called in price mode")

    class _NoInfoTickers:
        def __init__(self, symbols):
            self.tickers = {symbol: _NoInfoTicker() for symbol in symbols}

    def _download_stub(*args, **kwargs):
        return _make_download_frame("AAPL")

    monkeypatch.setattr(yf_fetcher.yf, "download", _download_stub)
    monkeypatch.setattr(yf_fetcher.yf, "Tickers", lambda symbols: _NoInfoTickers(symbols))

    req = indicatorRequest("AAPL", [pd.Timestamp("2024-01-01")], mode=E_FetchMode.PRICE)
    container = _YF_fetchReq_Container([req], [pd.Timestamp("2024-01-01")], mode=E_FetchMode.PRICE)

    yf_fetcher.fetch_yfinance(container)

    assert req.data.price is not None  # price data was populated
