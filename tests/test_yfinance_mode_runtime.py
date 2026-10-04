import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

# tests/* -> project root -> src
pysft_src = Path(__file__).resolve().parents[1] / "src"
if str(pysft_src) not in sys.path:
    sys.path.insert(0, str(pysft_src))

from pysft.core.enums import E_FetchMode
from pysft.core.models import _YF_fetchReq_Container
from pysft.core.structures import indicatorRequest

yf_fetcher = importlib.import_module("pysft.fetchers.fetch_yfinance")

pytestmark = [pytest.mark.unit]


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

    assert calls["download"] == 1
    assert req.success is True
    assert container.success is True
    assert req.data.price == 100.5


def test_price_mode_skips_info_fetch(monkeypatch):
    """price mode must not touch ticker.info or ticker.history (no metadata network calls)."""

    class _NoInfoTicker(_DummyTicker):
        def __init__(self):
            pass  # Do not assign to the guarded info property.

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

    assert req.data.price == 100.5
    assert req.success is True
    assert container.success is True


@pytest.mark.parametrize(
    ("symbol", "factor", "is_tase_indicator", "original_indicator"),
    [
        ("TEST.TA", 0.01, True, "1144633"),
        ("TEST.TA", 0.01, False, "1144633"),
        ("TEST.TA", 0.01, False, "TEST.TA"),
        ("CHKP", 1.0, True, "1144633"),
        ("^TA125.TA", 1.0, True, "1144633"),
    ],
)
@pytest.mark.parametrize("dates", [["2024-01-01"], ["2024-01-01", "2024-01-02"]])
def test_price_mode_preserves_units_for_tase_equivalents(
    monkeypatch, symbol, factor, is_tase_indicator, original_indicator, dates
):
    class PriceOnlyTicker:
        @property
        def info(self):
            raise AssertionError("Price mode must not fetch metadata")

        def history(self, *args, **kwargs):
            raise AssertionError("Valid Price mode must not fetch inception history")

    def download(*args, **kwargs):
        frame = pd.concat([_make_download_frame(symbol) for _ in dates])
        frame.index = pd.DatetimeIndex(dates)
        return frame

    monkeypatch.setattr(yf_fetcher.yf, "download", download)
    monkeypatch.setattr(
        yf_fetcher.yf, "Tickers",
        lambda symbols: type(
            "Tickers", (), {"tickers": {s: PriceOnlyTicker() for s in symbols}}
        )(),
    )
    timestamps = [pd.Timestamp(date) for date in dates]
    req = indicatorRequest(symbol, timestamps, mode=E_FetchMode.PRICE)
    req.original_indicator = original_indicator
    req.is_tase_indicator = is_tase_indicator
    container = _YF_fetchReq_Container([req], timestamps, mode=E_FetchMode.PRICE)
    yf_fetcher.fetch_yfinance(container)

    assert req.success and container.success
    for field, raw in (
        ("price", 100.5), ("open", 100.0), ("high", 101.0), ("low", 99.0),
    ):
        actual = getattr(req.data, field)
        expected = raw * factor if len(dates) == 1 else [raw * factor] * len(dates)
        assert actual == pytest.approx(expected)
    assert req.data.last == pytest.approx(100.5 * factor)
    if factor == 0.01:
        assert req.data.currency == "ILS"


@pytest.mark.parametrize(
    "response_kind", ["none", "empty", "incomplete", "nan", "invalid_open", "error"]
)
def test_price_mode_failed_downloads_remain_failures(monkeypatch, response_kind):
    calls = {"download": 0}

    def _download_stub(*args, **kwargs):
        calls["download"] += 1
        if response_kind == "error":
            raise RuntimeError("Provider unavailable")
        if response_kind == "none":
            return None
        if response_kind == "empty":
            return pd.DataFrame()
        frame = _make_download_frame("AAPL")
        if response_kind == "incomplete":
            return frame.drop(columns="Volume", level=0)
        if response_kind == "nan":
            return frame * float("nan")
        frame[("Open", "AAPL")] = float("nan")
        return frame

    class _EmptyHistoryTicker(_DummyTicker):
        def history(self, period="max", auto_adjust=True):
            return pd.DataFrame()

    monkeypatch.setattr(yf_fetcher.yf, "download", _download_stub)
    monkeypatch.setattr(
        yf_fetcher.yf,
        "Tickers",
        lambda symbols: type(
            "Tickers", (), {"tickers": {s: _EmptyHistoryTicker() for s in symbols}}
        )(),
    )
    req = indicatorRequest("AAPL", [pd.Timestamp("2024-01-01")], mode=E_FetchMode.PRICE)
    container = _YF_fetchReq_Container(
        [req], [pd.Timestamp("2024-01-01")], mode=E_FetchMode.PRICE
    )

    yf_fetcher.fetch_yfinance(container)

    assert req.success is False
    assert container.success is False
    assert calls["download"] == yf_fetcher.const.MAX_YF_ATTEMPTS
