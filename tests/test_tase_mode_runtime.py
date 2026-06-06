from pathlib import Path
import sys
import importlib

import pandas as pd

# tests/* -> project root -> src
pysft_src = Path(__file__).resolve().parents[1] / "src"
if str(pysft_src) not in sys.path:
    sys.path.insert(0, str(pysft_src))

from pysft.core.enums import E_FetchMode
from pysft.core.structures import indicatorRequest

tase_fetcher = importlib.import_module("pysft.fetchers.TASE")
tase_utils   = importlib.import_module("pysft.core.tase_specific_utils")


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

_STUB_QUOTE_TYPE = "MTF"

def _stub_infer_quote_type(session, url, timeout=10):
    return _STUB_QUOTE_TYPE

def _stub_dividend_data(data, session):
    data.dividendYield = 2.5
    return True

def _stub_general_data(data, session):
    data.name = "Test Fund"
    data.currency = "ILS"
    data.expense_rate = 0.5
    data.market_cap = 1_000_000.0
    return True

def _stub_graph_data(data, session):
    data.price = 100.0
    data.last  = 100.0
    data.open  = 99.0
    data.high  = 101.0
    data.low   = 98.0
    data.volume = 5000
    data.change_pct = 1.0
    data.dates = [pd.Timestamp("2024-01-01")]
    return True


def _make_request(mode: E_FetchMode) -> indicatorRequest:
    return indicatorRequest(
        "123456",
        [pd.Timestamp("2024-01-01")],
        mode=mode,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_info_mode_skips_graph_data(monkeypatch):
    """INFO mode must not call any price-fetching graph endpoint."""

    def _raise_graph(*args, **kwargs):
        raise AssertionError("graph data must not be called in info mode")

    monkeypatch.setattr(tase_fetcher.tase_utils, "infer_tase_quote_type_from_url", _stub_infer_quote_type)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_dividend_data",    _stub_dividend_data)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_general_indicator_data", _stub_general_data)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_graph_data",       _raise_graph)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_MAYA_TASE_graph_data",       _raise_graph)

    req = _make_request(E_FetchMode.INFO)
    tase_fetcher.fetch_TASE(req)

    assert req.success is True
    assert req.data.name == "Test Fund"
    assert req.data.dividendYield == 2.5


def test_price_mode_skips_info_calls(monkeypatch):
    """PRICE mode must not call dividend or general metadata endpoints."""

    def _raise_info(*args, **kwargs):
        raise AssertionError("info calls must not be made in price mode")

    monkeypatch.setattr(tase_fetcher.tase_utils, "infer_tase_quote_type_from_url",      _stub_infer_quote_type)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_dividend_data",         _raise_info)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_general_indicator_data", _raise_info)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_graph_data",            _stub_graph_data)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_MAYA_TASE_graph_data",            _stub_graph_data)

    req = _make_request(E_FetchMode.PRICE)
    tase_fetcher.fetch_TASE(req)

    assert req.success is True
    assert req.data.price == 100.0


def test_all_mode_calls_everything(monkeypatch):
    """ALL mode must call all four data endpoints."""

    calls = {"dividend": 0, "general": 0, "graph": 0}

    def _track_dividend(data, session):
        calls["dividend"] += 1
        return _stub_dividend_data(data, session)

    def _track_general(data, session):
        calls["general"] += 1
        return _stub_general_data(data, session)

    def _track_graph(data, session):
        calls["graph"] += 1
        return _stub_graph_data(data, session)

    monkeypatch.setattr(tase_fetcher.tase_utils, "infer_tase_quote_type_from_url",      _stub_infer_quote_type)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_dividend_data",         _track_dividend)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_general_indicator_data", _track_general)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_Bizportal_graph_data",            _track_graph)
    monkeypatch.setattr(tase_fetcher.tase_utils, "get_MAYA_TASE_graph_data",            _track_graph)

    req = _make_request(E_FetchMode.ALL)
    tase_fetcher.fetch_TASE(req)

    assert req.success is True
    assert calls["dividend"] == 1
    assert calls["general"]  == 1
    assert calls["graph"]    == 1   # MTF branch only calls get_Bizportal_graph_data
