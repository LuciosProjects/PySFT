"""Opt-in smoke tests against real external providers."""

from __future__ import annotations

import os

import pytest

from pysft.lib import fetch_data

pytestmark = [pytest.mark.live]


class TestLiveProviders:
    def test_aapl_current_price(self, pysft_env):
        result = fetch_data("AAPL", mode="price")
        assert result["AAPL"]["price"]
        assert result["AAPL"]["price"][-1] > 0

    def test_fx_batch(self, pysft_env):
        result = fetch_data(["USDILS=X", "EURUSD=X"], mode="price")
        assert set(result) == {"USDILS=X", "EURUSD=X"}
        assert all(result[symbol]["price"] for symbol in result)

    def test_tase_price_when_credentials_are_configured(self, pysft_env):
        if not os.environ.get("TASE_DATAHUB_API_KEY"):
            pytest.skip("TASE_DATAHUB_API_KEY is not configured")
        result = fetch_data("1183441", mode="price")
        assert result["1183441"]["price"]
