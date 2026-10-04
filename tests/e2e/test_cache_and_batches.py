"""Cache lifecycle and partial-batch behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

import pysft.core.fetcher_manager as fetcher_manager_module
from pysft.core import database
from pysft.core.database import DatabaseManager
from pysft.core.structures import _indicator_data
from pysft.lib import fetch_data
from tests.support.scenarios import YFinanceScenarioFactory

pytestmark = [pytest.mark.e2e]


class TestCacheLifecycle:
    def test_second_current_request_is_served_from_temporary_cache(
        self, pysft_env, provider_gateway
    ):
        today = pd.Timestamp.now().date().isoformat()
        provider_gateway.add(YFinanceScenarioFactory.equity(dates=(today,)))

        first = fetch_data("AAPL", mode="price")
        second = fetch_data("AAPL", mode="price")

        assert second == first
        assert provider_gateway.calls["AAPL"] == 1
        assert pysft_env.scalar_row_count("AAPL") > 0
        assert pysft_env.price_row_count("AAPL") == 1

    def test_explicit_subset_matches_between_fresh_fetch_and_cache_hit(
        self, pysft_env, provider_gateway
    ):
        today = pd.Timestamp.now().date().isoformat()
        provider_gateway.add(YFinanceScenarioFactory.equity(dates=(today,)))

        fresh = fetch_data(
            "AAPL", attributes=["name", "price"], mode="info"
        )
        cached = fetch_data(
            "AAPL", attributes=["name", "price"], mode="price"
        )

        assert cached == fresh
        assert set(fresh["AAPL"]) == {"dates", "name", "price"}
        assert provider_gateway.calls["AAPL"] == 1

    def test_expired_metadata_is_refetched(self, pysft_env, provider_gateway):
        provider_gateway.add(YFinanceScenarioFactory.equity())
        fetch_data("AAPL", mode="info")
        pysft_env.expire_scalar_values("AAPL")

        fetch_data("AAPL", mode="info")

        assert provider_gateway.calls["AAPL"] == 2

    def test_explicit_selection_checks_freshness_only_for_selected_fields(
        self, pysft_env, provider_gateway
    ):
        provider_gateway.add(YFinanceScenarioFactory.equity())
        fetch_data("AAPL", attributes="expense_rate", mode="price")
        pysft_env.expire_scalar_values("AAPL")

        name = fetch_data("AAPL", attributes="name", mode="price")
        expense_rate = fetch_data(
            "AAPL", attributes="expense_rate", mode="price"
        )

        assert name["AAPL"]["name"] == ["AAPL Incorporated"]
        assert expense_rate["AAPL"]["expense_rate"] == [0.0]
        assert provider_gateway.calls["AAPL"] == 2

    def test_cache_can_be_disabled_without_writing_rows(
        self, pysft_env, provider_gateway, monkeypatch
    ):
        provider_gateway.add(YFinanceScenarioFactory.equity())
        monkeypatch.setattr(database, "DB_ENABLED", False)
        monkeypatch.setattr(fetcher_manager_module, "DB_ENABLED", False)

        fetch_data("AAPL", mode="price")
        fetch_data("AAPL", mode="price")

        assert provider_gateway.calls["AAPL"] == 2
        assert pysft_env.scalar_row_count() == 0
        assert pysft_env.price_row_count() == 0

    def test_two_database_connections_share_only_the_temporary_file(self, pysft_env):
        sample = _indicator_data(indicator="AAPL", name="Apple")

        def write_indicator(symbol: str) -> None:
            with DatabaseManager(str(pysft_env.database_path)) as manager:
                manager.cache_indicator_data(symbol, sample, ["name"])

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(write_indicator, ["AAPL", "MSFT"]))

        assert pysft_env.scalar_row_count() == 2


class TestBatchIsolation:
    def test_failed_indicator_does_not_erase_successful_peer(
        self, pysft_env, provider_gateway
    ):
        provider_gateway.add(
            YFinanceScenarioFactory.equity("MSFT", price=300.0),
            YFinanceScenarioFactory.failure("BROKEN"),
        )

        result = fetch_data(["BROKEN", "MSFT"], mode="price")

        assert list(result) == ["BROKEN", "MSFT"]
        assert result["BROKEN"]["price"] is None
        assert result["MSFT"]["price"] == [300.0]
        assert pysft_env.price_row_count("BROKEN") == 0
        assert pysft_env.price_row_count("MSFT") == 1

    def test_duplicate_indicators_do_not_duplicate_provider_work(
        self, pysft_env, provider_gateway
    ):
        provider_gateway.add(YFinanceScenarioFactory.equity())

        result = fetch_data(["AAPL", "AAPL"], mode="price")

        assert list(result) == ["AAPL"]
        assert provider_gateway.calls["AAPL"] == 1
