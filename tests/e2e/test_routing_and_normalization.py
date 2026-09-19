"""Provider-routing and normalization E2E tests."""

from __future__ import annotations

from typing import ClassVar

import pandas as pd
import pytest

from pysft.core import tase_specific_utils
from pysft.core.structures import _indicator_data
from pysft.lib import fetch_data
from tests.support.scenarios import TASEScenarioFactory, YFinanceScenarioFactory

pytestmark = [pytest.mark.e2e]


class TestProviderRouting:
    def test_mixed_batch_routes_and_recombines_in_original_order(
        self, pysft_env, provider_gateway
    ):
        provider_gateway.add(
            YFinanceScenarioFactory.equity("AAPL"),
            TASEScenarioFactory.security("9999999", raw_price=250.0),
        )

        result = fetch_data(["AAPL", "9999999"], mode="all")

        assert list(result) == ["AAPL", "9999999"]
        assert ("AAPL", "yfinance") in provider_gateway.routes
        assert ("9999999", "tase") in provider_gateway.routes
        assert result["9999999"]["exchange"] == ["TASE"]

    def test_two_fx_pairs_survive_one_yfinance_batch(self, pysft_env, provider_gateway):
        provider_gateway.add(
            YFinanceScenarioFactory.fx("USDILS=X"),
            YFinanceScenarioFactory.fx("EURUSD=X", prices=(1.08, 1.09)),
        )

        result = fetch_data(["USDILS=X", "EURUSD=X"], mode="price")

        assert result["USDILS=X"]["price"] == [3.6, 3.61]
        assert result["EURUSD=X"]["price"] == [1.08, 1.09]
        assert result["USDILS=X"]["dates"] == ["2024-01-02", "2024-01-03"]


class TestNormalization:
    def test_tase_agorot_is_converted_to_ils_once(self, pysft_env, provider_gateway):
        provider_gateway.add(
            TASEScenarioFactory.security(
                "5111422", raw_price=159.90, raw_currency="ILA"
            )
        )

        result = fetch_data("5111422", mode="all")["5111422"]

        assert result["price"] == pytest.approx([1.599])
        assert result["currency"] == ["ILS"]

    def test_fund_expense_rates_remain_percentages(self, pysft_env, provider_gateway):
        provider_gateway.add(
            YFinanceScenarioFactory.fund("TESTETF", expense_rate=0.25),
            TASEScenarioFactory.fund("9999998", expense_rate=0.65),
        )

        result = fetch_data(["TESTETF", "9999998"], mode="info")

        assert result["TESTETF"]["expense_rate"] == [0.25]
        assert result["9999998"]["expense_rate"] == [0.65]

    def test_maya_parser_applies_agorot_factor_once(self, monkeypatch):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "history": [
                        {
                            "tdt": "01/01/2024",
                            "ort": 150.0,
                            "crt": 150.0,
                            "hrt": 151.0,
                            "lrt": 149.0,
                            "trov": 15000.0,
                        },
                        {
                            "tdt": "02/01/2024",
                            "ort": 159.0,
                            "crt": 159.90,
                            "hrt": 160.0,
                            "lrt": 158.0,
                            "trov": 15990.0,
                        },
                    ]
                }

        class Session:
            headers: ClassVar[dict] = {}

            def get(self, *args, **kwargs):
                return Response()

        monkeypatch.setattr(
            tase_specific_utils.utils, "random_delay", lambda *args: None
        )
        data = _indicator_data(
            indicator="5111422",
            ISIN="IL-5111422",
            quoteType="STOCK",
            dates=[pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-02")],
        )

        assert tase_specific_utils.get_MAYA_TASE_graph_data(data, Session()) is True
        assert data.price == pytest.approx([1.599])
