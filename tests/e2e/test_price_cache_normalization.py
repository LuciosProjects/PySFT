"""Persisted quote-unit migration, cache hits, and failed refresh safety."""

from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest
import requests

from pysft.core import tase_specific_utils
from pysft.core.database import DatabaseManager
from pysft.core.price_normalization import BIZPORTAL_MTF_NORMALIZATION_VERSION
from pysft.core.structures import _indicator_data
from pysft.lib import fetch_data
from tests.e2e.test_routing_and_normalization import _install_raw_bizportal_mtf
from tests.support.scenarios import TASEScenarioFactory

pytestmark = [pytest.mark.e2e]

FUND = "5111422"
DATES = ("2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-04")
VERSION = BIZPORTAL_MTF_NORMALIZATION_VERSION


def seed_history(env, indicator=FUND, quote_type="MTF", price=159.5, version=None):
    """Seed either legacy or versioned rows, including surrounding span dates."""
    dates = [pd.Timestamp(date) for date in DATES]
    data = _indicator_data(
        indicator=indicator, name="Cached name", quoteType=quote_type,
        currency="ILS", dates=dates, price=[price] * len(dates),
        open=[price] * len(dates), high=[price] * len(dates),
        low=[price] * len(dates), volume=[100] * len(dates),
    )
    env.manager.cache_indicator_data(
        indicator, data, ["name", "quoteType", "currency"]
    )
    env.manager.cache_historical_data(
        indicator, dates, data.open, data.high, data.low, data.price, data.volume,
        change_pcts=[0.0] * len(dates),
        normalization_version=version,
    )


def price_rows(env, indicator=FUND):
    return env.manager.connection.execute(
        "SELECT date, close, normalization_version, fetched_at FROM price_history "
        "WHERE indicator = ? ORDER BY date", (indicator,),
    ).fetchall()


class TestPriceCacheNormalization:
    @pytest.mark.parametrize("old_price", [159.5, 1.595])
    @pytest.mark.parametrize("old_version", [None, VERSION - 1])
    @pytest.mark.parametrize(
        ("start", "end"), [
            ("2026-10-01", "2026-10-01"),
            ("2026-09-29", "2026-10-01"),
        ],
    )
    def test_unproven_fund_history_refetches_without_rescaling(
        self, pysft_env, provider_gateway, monkeypatch,
        old_price, old_version, start, end,
    ):
        seed_history(pysft_env, price=old_price, version=old_version)
        before = price_rows(pysft_env)
        assert pysft_env.manager.get_cached_dates(FUND).empty
        assert pysft_env.manager.get_historical_data(
            FUND, pd.Timestamp(start), pd.Timestamp(end)
        ) is None
        calls = _install_raw_bizportal_mtf(
            monkeypatch, FUND, 159.5, 'ש"ח',
            ("01/10/2026", "30/09/2026", "29/09/2026", "28/09/2026"),
        )

        result = fetch_data(FUND, mode="price", start=start, end=end)[FUND]

        expected = [1.595] if start == end else [1.575, 1.585, 1.595]
        assert result["price"] == pytest.approx(expected)
        for field in ("open", "high", "low"):
            assert result[field] is None
        assert result["last"] == pytest.approx([1.595])
        assert any(path.endswith("biz_papers_helper.ashx") for path in calls)
        # Fetching one range never certifies legacy rows outside it.
        after = price_rows(pysft_env)
        assert after[0] == before[0]
        assert after[-1] == before[-1]
        refreshed = [row for row in after if start <= str(row[0]) <= end]
        assert all(row[2] == VERSION for row in refreshed)

        count = len(calls)
        assert fetch_data(FUND, attributes=["price", "last"], start=start, end=end)[FUND]["price"] == pytest.approx(expected)
        assert len(calls) == count

    @pytest.mark.parametrize("quote_type", ["MTF", "ETF", "STOCK"])
    def test_known_good_complete_history_is_preserved(
        self, pysft_env, provider_gateway, quote_type
    ):
        seed_history(
            pysft_env, quote_type=quote_type, price=1.595,
            version=VERSION if quote_type == "MTF" else None,
        )
        before = price_rows(pysft_env)

        result = fetch_data(
            FUND, mode="price", start="2026-09-29", end="2026-10-01"
        )[FUND]

        assert result["price"] == pytest.approx([1.595] * 3)
        assert provider_gateway.calls == {}
        assert price_rows(pysft_env) == before

    def test_obsolete_interior_row_cannot_be_a_complete_cache_hit(
        self, pysft_env, provider_gateway, monkeypatch
    ):
        seed_history(pysft_env, price=1.595, version=VERSION)
        pysft_env.set_price_version(FUND, None, "2026-09-30")
        calls = _install_raw_bizportal_mtf(
            monkeypatch, FUND, 159.5, 'ש"ח',
            ("01/10/2026", "30/09/2026", "29/09/2026", "28/09/2026"),
        )

        result = fetch_data(
            FUND, mode="price", start="2026-09-29", end="2026-10-01"
        )[FUND]

        assert result["dates"] == list(DATES[1:4])
        assert result["price"] == pytest.approx([1.575, 1.585, 1.595])
        assert calls
        assert all(row[2] == VERSION for row in price_rows(pysft_env))

    def test_failed_refresh_does_not_revalidate_or_return_legacy_prices(
        self, pysft_env, provider_gateway
    ):
        seed_history(pysft_env)
        before = price_rows(pysft_env)
        provider_gateway.add(TASEScenarioFactory.failure(FUND))

        for _ in range(2):
            result = fetch_data(
                FUND, mode="price", start="2026-10-01", end="2026-10-01"
            )[FUND]
            assert result["price"] is None
            assert pysft_env.manager.get_cached_dates(FUND).empty
            assert price_rows(pysft_env) == before
        assert provider_gateway.calls[FUND] == 2

    @pytest.mark.parametrize("failed_path", ["generalview", "biz_papers_helper"])
    def test_raw_provider_failure_keeps_history_untrusted(
        self, pysft_env, provider_gateway, monkeypatch, failed_path
    ):
        seed_history(pysft_env)
        before = price_rows(pysft_env)
        _install_raw_bizportal_mtf(monkeypatch, FUND, 159.5, 'ש"ח')
        successful_get = requests.Session.get

        def failed_get(session, url, **kwargs):
            if failed_path in url:
                raise requests.RequestException("controlled refresh failure")
            return successful_get(session, url, **kwargs)

        monkeypatch.setattr(requests.Session, "get", failed_get)
        monkeypatch.setattr(
            tase_specific_utils.utils, "random_delay", lambda *args: None
        )
        result = fetch_data(
            FUND, mode="price", start="2026-10-01", end="2026-10-01"
        )[FUND]

        assert result["price"] is None
        assert price_rows(pysft_env) == before
        assert pysft_env.manager.get_cached_dates(FUND).empty

    def test_partial_batch_preserves_unaffected_history_on_fund_failure(
        self, pysft_env, provider_gateway
    ):
        seed_history(pysft_env)
        seed_history(pysft_env, indicator="1144633", quote_type="ETF", price=46.34)
        seed_history(pysft_env, indicator="AAPL", quote_type="EQUITY", price=100)
        before_etf = price_rows(pysft_env, "1144633")
        before_equity = price_rows(pysft_env, "AAPL")
        provider_gateway.add(TASEScenarioFactory.failure(FUND))

        result = fetch_data(
            [FUND, "1144633", "AAPL"], mode="price",
            start="2026-09-29", end="2026-10-01",
        )

        assert result[FUND]["price"] is None
        assert result["1144633"]["price"] == [46.34] * 3
        assert result["AAPL"]["price"] == [100] * 3
        assert provider_gateway.calls == {FUND: 1}
        assert price_rows(pysft_env, "1144633") == before_etf
        assert price_rows(pysft_env, "AAPL") == before_equity

    def test_metadata_refresh_does_not_certify_legacy_history(
        self, pysft_env, provider_gateway
    ):
        seed_history(pysft_env)
        before = price_rows(pysft_env)
        provider_gateway.add(TASEScenarioFactory.fund(FUND))

        fetch_data(FUND, mode="info", start="2026-10-01", end="2026-10-01")

        assert price_rows(pysft_env) == before
        assert pysft_env.manager.get_cached_dates(FUND).empty

    @pytest.mark.parametrize("quote_type", ["MTF", ""])
    def test_related_legacy_scalar_prices_are_excluded_but_metadata_survives(
        self, pysft_env, quote_type
    ):
        seed_history(pysft_env, quote_type=quote_type)
        with pysft_env.manager.connection:
            for field in ("price", "last", "open", "high", "low"):
                pysft_env.manager.connection.execute(
                    "INSERT INTO indicator_attributes "
                    "(indicator, attribute, value_json, fetched_at) VALUES (?, ?, ?, ?)",
                    (FUND, field, json.dumps(159.5), "2026-10-01 12:00:00"),
                )
        data, fresh = pysft_env.manager.get_cached_data(FUND, ["name"])
        assert fresh
        assert data.name == "Cached name"
        assert data.currency == "ILS"
        assert all(getattr(data, field) == 0.0 for field in ("price", "last", "open", "high", "low"))
        _, fresh = pysft_env.manager.get_cached_data(FUND, ["last"])
        assert not fresh

    def test_future_unit_rule_version_bypasses_previously_valid_history(
        self, pysft_env, provider_gateway, monkeypatch
    ):
        from pysft.core import price_normalization

        seed_history(pysft_env, price=1.595, version=VERSION)
        monkeypatch.setattr(
            price_normalization, "BIZPORTAL_MTF_NORMALIZATION_VERSION", VERSION + 1
        )
        _install_raw_bizportal_mtf(monkeypatch, FUND, 159.5, 'ש"ח')

        result = fetch_data(
            FUND, mode="price", start="2026-10-01", end="2026-10-01"
        )[FUND]

        assert result["price"] == pytest.approx([1.595])
        refreshed = [row for row in price_rows(pysft_env) if str(row[0]) == "2026-10-01"]
        assert refreshed[0][2] == VERSION + 1

    def test_unknown_type_is_resolved_without_corrupting_correct_etf_history(
        self, pysft_env, provider_gateway
    ):
        seed_history(pysft_env, quote_type="", price=46.34)
        assert pysft_env.manager.get_cached_dates(FUND).empty
        data = _indicator_data(quoteType="ETF")
        pysft_env.manager.cache_indicator_data(FUND, data, ["quoteType"])
        assert len(pysft_env.manager.get_cached_dates(FUND)) == len(DATES)
        assert all(row[1] == 46.34 for row in price_rows(pysft_env))

    def test_missing_range_is_refetched_but_good_rows_outside_it_survive(
        self, pysft_env, provider_gateway, monkeypatch
    ):
        seed_history(pysft_env, price=1.595, version=VERSION)
        before = price_rows(pysft_env)
        calls = _install_raw_bizportal_mtf(
            monkeypatch, FUND, 159.5, 'ש"ח', ("05/10/2026", "04/10/2026"),
        )
        result = fetch_data(
            FUND, mode="price", start="2026-10-05", end="2026-10-05"
        )[FUND]
        assert result["price"] == pytest.approx([1.595])
        assert calls
        assert price_rows(pysft_env)[:-1] == before


def test_legacy_schema_migrates_in_place_and_persists_versions(pysft_env):
    path = str(pysft_env.database_path)
    # The isolated environment has not opened the DB yet.
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE indicator_attributes (
                indicator TEXT NOT NULL, attribute TEXT NOT NULL,
                value_json TEXT NOT NULL, fetched_at TIMESTAMP NOT NULL,
                PRIMARY KEY (indicator, attribute)
            );
            CREATE TABLE price_history (
                indicator TEXT NOT NULL, date DATE NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                volume INTEGER, change_pct REAL, fetched_at TIMESTAMP NOT NULL,
                PRIMARY KEY (indicator, date)
            );
        """)
        connection.execute(
            "INSERT INTO price_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (FUND, "2026-10-01", 159.5, 159.5, 159.5, 159.5, 100, 0, "2026-10-01 12:00:00"),
        )
    with DatabaseManager(path) as manager:
        assert manager.get_cached_dates(FUND).empty
        assert manager.connection.execute(
            "SELECT close, normalization_version FROM price_history"
        ).fetchone() == (159.5, None)
        manager.cache_indicator_data(
            FUND, _indicator_data(quoteType="MTF"), ["quoteType"]
        )
        manager.cache_historical_data(
            FUND, [pd.Timestamp("2026-10-01")], 1.595, 1.595, 1.595, 1.595, 100,
            normalization_version=VERSION,
        )
    with DatabaseManager(path) as reopened:
        assert list(reopened.get_cached_dates(FUND)) == [pd.Timestamp("2026-10-01")]
        assert reopened.get_historical_data(
            FUND, pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-01")
        ).price == [1.595]