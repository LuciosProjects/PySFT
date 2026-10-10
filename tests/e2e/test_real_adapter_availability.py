"""Availability regressions through production adapters rather than scenario data."""

import importlib

import pandas as pd
import pytest

from pysft.core.cache_contract import available_fields
from pysft.core.structures import _indicator_data
from pysft.core.yf_specific_utils import safe_extract_value_float, safe_extract_value_int
from pysft.lib import fetch_data
from tests.e2e.test_routing_and_normalization import _install_raw_bizportal_mtf

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("field", ["open", "high", "low", "change_pct"])
def test_real_fund_graph_cannot_certify_unavailable_cells(
    pysft_env, provider_gateway, monkeypatch, field
):
    # One observed close has no previous close from which to compute a change.
    calls = _install_raw_bizportal_mtf(
        monkeypatch, "5111422", 159.5, 'ש"ח', ("01/10/2026",)
    )
    kwargs = dict(start="2026-10-01", end="2026-10-01")
    first = fetch_data("5111422", attributes=["price", field], **kwargs)["5111422"]
    assert first["price"] == pytest.approx([1.595])
    assert first[field] is None
    row = pysft_env.manager.connection.execute(
        "SELECT open, high, low, close, change_pct FROM price_history"
    ).fetchone()
    assert row == (None, None, None, 1.595, None)
    count = len(calls)
    second = fetch_data("5111422", attributes=["price", field], **kwargs)["5111422"]
    assert second == first
    assert len(calls) > count  # Absent OHLC must not turn into a full cache hit.
    count = len(calls)
    assert fetch_data("5111422", attributes="price", **kwargs)["5111422"]["price"] == pytest.approx([1.595])
    assert len(calls) == count  # The genuine close remains independently reusable.


def test_legacy_fund_ohlc_copies_do_not_become_proven_on_refresh(
    pysft_env, provider_gateway, monkeypatch
):
    db = pysft_env.manager
    date = pd.Timestamp("2026-10-01")
    db.cache_indicator_data("5111422", _indicator_data(quoteType="MTF"), ["quoteType"])
    db.cache_historical_data(
        "5111422", [date], 1.595, 1.595, 1.595, 1.595, 100,
        normalization_version=1,
    )
    with db.connection:
        db.connection.execute("UPDATE price_history SET field_fetched_at = NULL")
    data = db.get_historical_data("5111422", date, date)
    assert data.price == [1.595]
    assert not {"open", "high", "low"} & available_fields(data)
    _install_raw_bizportal_mtf(monkeypatch, "5111422", 159.5, 'ש"ח')
    result = fetch_data(
        "5111422", attributes=["price", "open"], start="2026-10-01", end="2026-10-01"
    )["5111422"]
    assert result["price"] == pytest.approx([1.595])
    assert result["open"] is None
    assert db.connection.execute("SELECT open, high, low FROM price_history").fetchone() == (
        None, None, None,
    )


@pytest.mark.parametrize("extractor", [safe_extract_value_float, safe_extract_value_int])
def test_yahoo_extractors_preserve_real_zeroes_without_inventing_them(extractor):
    assert extractor(pd.Series([0])) == 0
    assert extractor(pd.Series([0, 12])) == [0, 12]
    for values in ([], [float("nan")], ["not a number"]):
        assert extractor(pd.Series(values)) == []


def test_real_yahoo_history_has_no_wraparound_change_or_placeholder_volume(
    pysft_env, provider_gateway, monkeypatch
):
    task_module = importlib.import_module("pysft.core.fetch_task")
    adapter = importlib.import_module("pysft.fetchers.fetch_yfinance")
    monkeypatch.setattr(task_module, "fetch_yfinance", adapter.fetch_yfinance)
    monkeypatch.setattr(adapter.yf, "Tickers", lambda symbols: type(
        "Tickers", (), {"tickers": {symbol: object() for symbol in symbols}}
    )())
    frame = pd.DataFrame(
        [[10, 11, 9, 10, 0], [11, 13, 10, 12, 123]],
        index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]),
        columns=pd.MultiIndex.from_product([
            ["Open", "High", "Low", "Close", "Volume"], ["AAPL"],
        ]),
    )
    monkeypatch.setattr(adapter.yf, "download", lambda *args, **kwargs: frame)
    result = fetch_data(
        "AAPL", mode="price", start="2024-01-02", end="2024-01-03"
    )["AAPL"]
    assert result["volume"] == [0, 123]
    assert result["change_pct"][0] is None
    assert result["change_pct"][1] == pytest.approx(20)
    row = pysft_env.manager.connection.execute(
        "SELECT volume, change_pct FROM price_history ORDER BY date"
    ).fetchall()
    assert row[0] == (0, None)
    assert row[1][0] == 123
