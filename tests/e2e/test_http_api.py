"""HTTP API behavior using the real request handler and loopback transport."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from tests.support.environment import HttpServerHarness
from tests.support.scenarios import YFinanceScenarioFactory

pytestmark = [pytest.mark.e2e]


class TestHttpApi:
    def test_health_endpoint(self, pysft_env):
        with HttpServerHarness() as server:
            status, payload = server.get_json("/health")

        assert status == 200
        assert payload == {"status": "ok"}

    def test_fetch_endpoint_matches_python_contract(self, pysft_env, provider_gateway):
        provider_gateway.add(YFinanceScenarioFactory.equity())

        with HttpServerHarness() as server:
            status, payload = server.get_json("/fetch?indicators=AAPL&attributes=price")

        assert status == 200
        assert payload["data"]["AAPL"]["price"] == [100.0]

    def test_missing_indicators_returns_json_bad_request(self, pysft_env):
        with HttpServerHarness() as server:
            with pytest.raises(HTTPError) as captured:
                urlopen(f"{server.base_url}/fetch", timeout=5)
            payload = json.loads(captured.value.read().decode("utf-8"))

        assert captured.value.code == 400
        assert payload == {"error": "Missing required query parameter: indicators"}

    def test_unknown_path_returns_json_not_found(self, pysft_env):
        with HttpServerHarness() as server, pytest.raises(HTTPError) as captured:
            urlopen(f"{server.base_url}/missing", timeout=5)

        assert captured.value.code == 404

    def test_concurrent_requests_remain_isolated(self, pysft_env, provider_gateway):
        provider_gateway.add(
            YFinanceScenarioFactory.equity("AAPL"),
            YFinanceScenarioFactory.equity("MSFT", price=200.0),
        )

        with HttpServerHarness() as server:

            def fetch(symbol: str):
                return server.get_json(f"/fetch?indicators={symbol}")[1]["data"][
                    symbol
                ]["price"][0]

            with ThreadPoolExecutor(max_workers=2) as pool:
                prices = list(pool.map(fetch, ["AAPL", "MSFT"]))

        assert prices == [100.0, 200.0]
