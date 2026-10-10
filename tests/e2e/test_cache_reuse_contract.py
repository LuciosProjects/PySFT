"""Cross-mode cache contract; all scenarios use fixed routes and isolated SQLite."""

from dataclasses import replace

import pandas as pd
import pytest

from pysft.core.structures import _indicator_data
from pysft.lib import fetch_data
from tests.support.scenarios import TASEScenarioFactory, YFinanceScenarioFactory

pytestmark = pytest.mark.e2e
DATES = ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")


@pytest.fixture(params=["yfinance", "tase"])
def route_case(request, provider_gateway, monkeypatch):
    provider = request.param
    ticker = "AAPL" if provider == "yfinance" else "9999999"
    scenario = (
        YFinanceScenarioFactory.equity(ticker, dates=DATES)
        if provider == "yfinance"
        else TASEScenarioFactory.security(ticker, dates=DATES)
    )
    provider_gateway.add(scenario)
    modes = []
    apply = provider_gateway._apply

    def record(req, route):
        modes.append(req.mode.value)
        apply(req, route)

    monkeypatch.setattr(provider_gateway, "_apply", record)
    return ticker, provider, modes, scenario


def test_info_price_all_reuse_without_placeholder_certification(
    pysft_env, provider_gateway, route_case
):
    ticker, route, modes, _ = route_case
    kwargs = dict(start=DATES[0], end=DATES[-1])
    info = fetch_data(ticker, mode="info", **kwargs)[ticker]
    assert pysft_env.price_row_count(ticker) == 0
    attrs = dict(pysft_env.manager.connection.execute(
        "SELECT attribute, value_json FROM indicator_attributes WHERE indicator = ?",
        (ticker,),
    ))
    assert "last" not in attrs
    assert "beta" not in attrs
    assert info["beta"] is None
    price = fetch_data(ticker, mode="price", **kwargs)[ticker]
    combined = fetch_data(ticker, attributes=["name", "price", "expense_rate"], **kwargs)[ticker]
    assert combined["price"] == price["price"]
    assert combined["name"] == info["name"]
    assert combined["expense_rate"] == [0.0]  # Explicit provider zero is valid.
    assert modes == ["info", "price"]
    assert provider_gateway.routes == [(ticker, route)] * 2
    assert pysft_env.price_row_count(ticker) == 4


def test_expanded_overlapping_ranges_are_clipped_sorted_and_reused(
    pysft_env, provider_gateway, route_case
):
    ticker, route, modes, scenario = route_case
    provider_gateway.add((ticker, replace(
        scenario[1], dates=scenario[1].dates[1:3], prices=scenario[1].prices[1:3]
    )))
    short = fetch_data(ticker, attributes="price", start=DATES[1], end=DATES[2])[ticker]
    assert short["dates"] == list(DATES[1:3])
    provider_gateway.add(scenario)
    wide = fetch_data(ticker, attributes="price", start=DATES[0], end=DATES[-1])[ticker]
    assert wide["dates"] == list(DATES)
    overlap = fetch_data(ticker, attributes="price", start=DATES[1], end=DATES[-1])[ticker]
    assert overlap["dates"] == list(DATES[1:])
    assert overlap["price"] == wide["price"][1:]
    assert provider_gateway.calls[ticker] == 2
    assert set(provider_gateway.routes) == {(ticker, route)}
    assert pysft_env.price_row_count(ticker) == 4


def test_metadata_refresh_merges_history_and_failed_refresh_keeps_good_fields(
    pysft_env, provider_gateway, route_case
):
    ticker, route, modes, scenario = route_case
    kwargs = dict(start=DATES[0], end=DATES[-1])
    initial = fetch_data(ticker, attributes=["name", "price", "currency"], **kwargs)[ticker]
    before = pysft_env.manager.connection.execute(
        "SELECT * FROM price_history ORDER BY date"
    ).fetchall()
    pysft_env.expire_scalar_values(ticker)
    refreshed = fetch_data(ticker, attributes=["name", "price", "currency"], **kwargs)[ticker]
    assert refreshed == initial
    assert modes == ["all", "info"]
    assert pysft_env.manager.connection.execute(
        "SELECT * FROM price_history ORDER BY date"
    ).fetchall() == before
    pysft_env.expire_scalar_values(ticker)
    provider_gateway.add((ticker, replace(scenario[1], error="refresh failed")))
    failed = fetch_data(ticker, attributes=["name", "price", "currency"], **kwargs)[ticker]
    assert failed["name"] == initial["name"]
    assert failed["price"] == initial["price"]
    assert failed["currency"] is None
    assert provider_gateway.calls[ticker] == 3


def test_missing_field_is_retried_but_not_persisted(pysft_env, provider_gateway):
    provider_gateway.add(YFinanceScenarioFactory.equity())
    for _ in range(2):
        result = fetch_data("AAPL", attributes=["name", "beta"])
        assert result["AAPL"]["beta"] is None
        assert result["AAPL"]["name"] == ["AAPL Incorporated"]
    assert provider_gateway.calls["AAPL"] == 2
    assert pysft_env.manager.connection.execute(
        "SELECT 1 FROM indicator_attributes WHERE attribute = 'beta'"
    ).fetchone() is None


def test_exact_range_and_single_day_hits_do_not_require_surrounding_rows(
    pysft_env, provider_gateway, route_case
):
    ticker, route, modes, _ = route_case
    first = fetch_data(ticker, mode="price", start=DATES[0], end=DATES[-1])[ticker]
    assert fetch_data(ticker, mode="price", start=DATES[0], end=DATES[-1])[ticker] == first
    one = fetch_data(ticker, attributes=["last", "price"], start=DATES[2], end=DATES[2])[ticker]
    assert one["dates"] == [DATES[2]]
    assert one["price"] == [first["price"][2]]
    assert one["last"] == one["price"]
    assert modes == ["price"]
    assert provider_gateway.routes == [(ticker, route)]


@pytest.mark.parametrize("first_mode", ["info", "all"])
def test_full_presets_reuse_in_both_directions(
    pysft_env, provider_gateway, route_case, first_mode
):
    ticker, route, modes, scenario = route_case
    metadata = {
        field: 1.0 for field in (
            "market_cap", "dividendYield", "trailingPE", "forwardPE", "beta",
            "avgDailyVolume3mnth",
        )
    }
    metadata.update(scenario[1].metadata)
    metadata["inceptionDate"] = pd.Timestamp("2020-01-01")
    provider_gateway.add((ticker, replace(scenario[1], metadata=metadata)))
    kwargs = dict(start=DATES[0], end=DATES[-1])
    info = fetch_data(ticker, mode=first_mode, **kwargs)[ticker]
    price = fetch_data(ticker, mode="price", **kwargs)[ticker]
    all_data = fetch_data(ticker, mode="all", **kwargs)[ticker]
    assert all_data["name"] == info["name"]
    assert all_data["price"] == price["price"]
    assert all_data["expense_rate"] == [0.0]
    expected_modes = ["info", "price"] if first_mode == "info" else ["all"]
    assert modes == expected_modes
    assert fetch_data(ticker, mode="info", **kwargs)[ticker]["name"] == info["name"]
    assert fetch_data(ticker, mode="price", **kwargs)[ticker] == price
    assert modes == expected_modes


def test_interior_missing_field_fetches_only_needed_yahoo_date_and_merges(
    pysft_env, provider_gateway, monkeypatch
):
    provider_gateway.add(YFinanceScenarioFactory.equity(dates=DATES))
    kwargs = dict(start=DATES[0], end=DATES[-1])
    original = fetch_data("AAPL", attributes=["name", "price", "volume"], **kwargs)["AAPL"]
    with pysft_env.manager.connection:
        pysft_env.manager.connection.execute(
            "UPDATE price_history SET volume = NULL WHERE date = ?", (DATES[2],)
        )
    reqs = []
    apply = provider_gateway._apply

    def sparse_refresh(req, route):
        reqs.append((req.mode.value, req.start_date.isoformat(), req.end_date.isoformat()))
        apply(req, route)
        # A partially populated successful provider response must not erase OHLC.
        req.data._present_fields = {"dates", "volume"}
        req.data.dates = [pd.Timestamp(DATES[2])]
        req.data.volume = [123]

    monkeypatch.setattr(provider_gateway, "_apply", sparse_refresh)
    result = fetch_data("AAPL", attributes=["name", "price", "volume"], **kwargs)["AAPL"]
    assert reqs == [("price", DATES[2], DATES[2])]
    assert result["name"] == original["name"]
    assert result["price"] == original["price"]
    assert result["volume"] == [1000, 1001, 123, 1003]
    assert fetch_data("AAPL", attributes=["name", "price", "volume"], **kwargs)["AAPL"] == result
    assert len(reqs) == 1


def test_failed_expansion_returns_only_compatible_rows(pysft_env, provider_gateway, route_case):
    ticker, route, modes, scenario = route_case
    provider_gateway.add((ticker, replace(
        scenario[1], dates=scenario[1].dates[1:3], prices=scenario[1].prices[1:3]
    )))
    short = fetch_data(ticker, mode="price", start=DATES[1], end=DATES[2])[ticker]
    before = pysft_env.manager.connection.execute("SELECT * FROM price_history").fetchall()
    provider_gateway.add((ticker, replace(scenario[1], error="failed expansion")))
    failed = fetch_data(ticker, mode="price", start=DATES[0], end=DATES[-1])[ticker]
    assert failed == short
    assert pysft_env.manager.connection.execute("SELECT * FROM price_history").fetchall() == before
    assert modes == ["price", "price"]


def test_today_partial_refresh_does_not_freshen_unfetched_cells(pysft_env):
    db = pysft_env.manager
    today = pd.Timestamp.now().normalize()
    db.cache_historical_data("AAPL", [today], 10, 11, 9, 10, 100, 0)
    with db.connection:
        db.connection.execute(
            "UPDATE price_history SET fetched_at = datetime('now', '-1 day'), "
            "field_fetched_at = NULL"
        )
    assert db.get_historical_data("AAPL", today, today) is None
    db.cache_historical_data("AAPL", [today], None, None, None, 12, None, None)
    data = db.get_historical_data("AAPL", today, today)
    assert data.price == [12]
    assert data.open == [None]
    assert data.volume == [None]
    assert db.missing_history_dates("AAPL", ["open"], pd.DatetimeIndex([today])).equals(
        pd.DatetimeIndex([today])
    )


def test_unavailable_values_never_become_immutable_cache_hits(pysft_env):
    db = pysft_env.manager
    db.cache_indicator_data(
        "AAPL", _indicator_data(name="", ISIN=None, beta=float("nan"), expense_rate=0),
        ["name", "ISIN", "beta", "expense_rate"],
    )
    assert pysft_env.scalar_row_count("AAPL") == 1
    _, fresh = db.get_cached_data("AAPL", ["name"])
    assert not fresh
    _, fresh = db.get_cached_data("AAPL", ["expense_rate"])
    assert fresh


def test_today_expiration_refetches_and_failure_never_returns_stale_prices(
    pysft_env, provider_gateway
):
    today = pd.Timestamp.now().date().isoformat()
    provider_gateway.add(YFinanceScenarioFactory.equity(dates=(today,)))
    first = fetch_data("AAPL", mode="price")["AAPL"]
    with pysft_env.manager.connection:
        pysft_env.manager.connection.execute(
            "UPDATE price_history SET fetched_at = datetime('now', '-1 day')"
        )
    refreshed = fetch_data("AAPL", mode="price")["AAPL"]
    assert refreshed == first
    assert provider_gateway.calls["AAPL"] == 2
    with pysft_env.manager.connection:
        pysft_env.manager.connection.execute(
            "UPDATE price_history SET fetched_at = datetime('now', '-1 day')"
        )
    before = pysft_env.manager.connection.execute("SELECT * FROM price_history").fetchall()
    provider_gateway.add(YFinanceScenarioFactory.failure("AAPL"))
    failed = fetch_data("AAPL", mode="price")["AAPL"]
    assert failed["price"] is None
    assert failed["last"] is None
    assert failed["dates"] == [today]
    assert pysft_env.manager.connection.execute("SELECT * FROM price_history").fetchall() == before


def test_old_scalar_defaults_cannot_prove_availability(pysft_env, provider_gateway):
    with pysft_env.manager.connection:
        pysft_env.manager.connection.execute(
            "INSERT INTO indicator_attributes "
            "(indicator, attribute, value_json, fetched_at) "
            "VALUES ('AAPL', 'beta', '0.0', datetime('now'))"
        )
    provider_gateway.add(YFinanceScenarioFactory.equity())
    result = fetch_data("AAPL", attributes="beta")["AAPL"]
    assert result["beta"] is None
    assert provider_gateway.calls["AAPL"] == 1


@pytest.mark.parametrize("exchange", ["", "XNAS"])
def test_yahoo_routed_tase_identifier_does_not_skip_us_friday(
    pysft_env, provider_gateway, monkeypatch, exchange
):
    ticker = "126.1.CHKP"
    thursday, friday = "2024-01-04", "2024-01-05"
    if exchange:
        pysft_env.manager.cache_indicator_data(
            ticker, _indicator_data(exchange=exchange), ["exchange"]
        )
    requests = []
    apply = provider_gateway._apply

    def record(req, route):
        requests.append((req.indicator, route, req.start_date.isoformat(), req.end_date.isoformat()))
        apply(req, route)

    monkeypatch.setattr(provider_gateway, "_apply", record)
    provider_gateway.add(YFinanceScenarioFactory.equity(ticker, dates=(thursday,)))
    fetch_data(ticker, attributes="price", start=thursday, end=thursday)
    provider_gateway.add(YFinanceScenarioFactory.equity(ticker, dates=(thursday, friday)))
    expanded = fetch_data(ticker, attributes="price", start=thursday, end=friday)[ticker]
    assert expanded["dates"] == [thursday, friday]
    assert expanded["price"] == [100, 101]
    assert requests == [
        ("CHKP", "yfinance", thursday, thursday),
        ("CHKP", "yfinance", friday, friday),
    ]
    assert provider_gateway.routes == [(ticker, "yfinance")] * 2
    assert pysft_env.price_row_count(ticker) == 2
    assert fetch_data(ticker, attributes="price", start=thursday, end=friday)[ticker] == expanded
    assert provider_gateway.calls[ticker] == 2
