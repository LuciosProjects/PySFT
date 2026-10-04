"""Provider-routing and normalization E2E tests."""

from __future__ import annotations

import importlib
import json
from typing import ClassVar
from urllib.parse import urlparse

import pandas as pd
import pytest
import requests

from pysft.core import tase_specific_utils
from pysft.core.structures import _indicator_data
from pysft.lib import fetch_data
from tests.support.scenarios import TASEScenarioFactory, YFinanceScenarioFactory

pytestmark = [pytest.mark.e2e]

fetch_task_module = importlib.import_module("pysft.core.fetch_task")
tase_fetcher_module = importlib.import_module("pysft.fetchers.TASE")


def _install_raw_bizportal_mtf(
    monkeypatch: pytest.MonkeyPatch,
    indicator: str,
    raw_price: float,
    currency_label: str,
    graph_dates: tuple[str, ...] = ("01/10/2026", "30/09/2026"),
) -> list[str]:
    """Route the public API through the production TASE fetcher and raw parsers."""
    monkeypatch.setattr(fetch_task_module, "fetch_TASE", tase_fetcher_module.fetch_TASE)
    calls: list[str] = []

    class Response:
        status_code = 200

        def __init__(
            self, *, text: str = "", content: bytes | None = None, url: str = ""
        ) -> None:
            self.text = text
            self.content = content if content is not None else text.encode()
            self.url = url

        def raise_for_status(self) -> None:
            return None

    def head(_session: requests.Session, _url: str, **_kwargs: object) -> Response:
        return Response(url=f"https://finance.themarker.com/mtf/{indicator}")

    def get(
        _session: requests.Session, url: str, **_kwargs: object
    ) -> Response:
        path = urlparse(url).path
        calls.append(path)
        if "/quote/dividends/" in path:
            return Response(text="<html><body>No dividend history</body></html>")
        if "/quote/generalview/" in path:
            page = f"""
                <div class="paper_top_title">
                    <h1 class="paper_h1">TASE test fund {indicator}</h1>
                </div>
                <dl>
                    <dt>מטבע</dt><dd>{currency_label}</dd>
                    <dt>דמי ניהול</dt><dd>0.2%</dd>
                    <dt>דמי נאמנות</dt><dd>0.1%</dd>
                    <dt>תאריך הקמה</dt><dd>01/01/2020</dd>
                    <dt>היקף נכסים</dt><dd>100</dd>
                </dl>
            """
            return Response(text=page)
        if path.endswith("/ajax/biz_papers_helper.ashx"):
            graph = [
                {"D_p": date, "C_p": raw_price - index, "V_p": 100}
                for index, date in enumerate(graph_dates)
            ]
            return Response(content=json.dumps(graph).encode())
        raise AssertionError(f"Unexpected provider URL: {url}")

    monkeypatch.setattr(requests.Session, "head", head)
    monkeypatch.setattr(requests.Session, "get", get)
    return calls


class TestProviderRouting:
    @pytest.mark.parametrize(
        ("indicator", "symbol"),
        [("AAPL", "AAPL"), ("1101666", "ABRA.TA"), ("IN-FF1.TA", "IN-FF1.TA")],
    )
    def test_price_mode_exposes_real_yfinance_results_without_metadata(
        self, pysft_env, provider_gateway, monkeypatch, indicator, symbol
    ):
        yf_fetcher = importlib.import_module("pysft.fetchers.fetch_yfinance")
        calls = []
        containers = []

        class PriceOnlyTicker:
            @property
            def info(self):
                raise AssertionError("Price mode must not access metadata")

            @property
            def isin(self):
                raise AssertionError("Price mode must not access ISIN metadata")

            def history(self, *args, **kwargs):
                raise AssertionError("Valid price mode must not request history")

        def download(symbols, **kwargs):
            calls.append(symbols)
            assert symbols == [symbol]
            return pd.DataFrame(
                [[100.0, 101.0, 99.0, 100.5, 1000]],
                index=pd.DatetimeIndex(["2024-01-02"]),
                columns=pd.MultiIndex.from_product(
                    [["Open", "High", "Low", "Close", "Volume"], [symbol]]
                ),
            )

        def fetch(container):
            containers.append(container)
            yf_fetcher.fetch_yfinance(container)

        monkeypatch.setattr(fetch_task_module, "fetch_yfinance", fetch)
        monkeypatch.setattr(yf_fetcher.yf, "download", download)
        monkeypatch.setattr(
            yf_fetcher.yf,
            "Tickers",
            lambda symbols: type(
                "Tickers", (), {"tickers": {s: PriceOnlyTicker() for s in symbols}}
            )(),
        )

        result = fetch_data(
            indicator, mode="price", start="2024-01-02", end="2024-01-02"
        )

        assert list(result) == [indicator]
        assert result[indicator]["dates"] == ["2024-01-02"]
        factor = 0.01 if symbol.endswith(".TA") else 1.0
        for field, raw in (
            ("price", 100.5), ("last", 100.5), ("open", 100.0),
            ("high", 101.0), ("low", 99.0),
        ):
            assert result[indicator][field] == pytest.approx([raw * factor])
        assert len(calls) == 1
        assert len(containers) == 1
        assert containers[0].success is True
        assert containers[0].requests[0].success is True

        cached = fetch_data(
            indicator, mode="price", start="2024-01-02", end="2024-01-02"
        )
        for field in ("price", "last", "open", "high", "low"):
            assert cached[indicator][field] == result[indicator][field]
        assert len(calls) == 1  # Real temporary SQLite hit, no provider refetch.

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
    @pytest.mark.parametrize(
        ("indicator", "raw_price"),
        [("5111422", 159.5), ("5117379", 117.75)],
    )
    @pytest.mark.parametrize("mode", ["price", "all", "info"])
    def test_bizportal_mtf_agorot_are_normalized_through_public_api(
        self,
        pysft_env,
        provider_gateway,
        monkeypatch,
        indicator,
        raw_price,
        mode,
    ):
        _install_raw_bizportal_mtf(monkeypatch, indicator, raw_price, 'ש"ח')

        result = fetch_data(
            indicator,
            mode=mode,
            start="2026-10-01",
            end="2026-10-01",
        )[indicator]

        if mode != "info":
            for field in ("price", "open", "high", "low"):
                assert result[field] == pytest.approx([raw_price / 100])
            assert result["last"] == pytest.approx([raw_price / 100])
        if mode != "price":
            assert result["currency"] == ["ILS"]

    def test_mtf_with_cached_ils_alias_still_loads_source_quote_units(
        self, pysft_env, provider_gateway, monkeypatch
    ):
        _install_raw_bizportal_mtf(monkeypatch, "5111422", 159.5, 'ש"ח')
        data = _indicator_data(
            indicator="5111422",
            quoteType="MTF",
            currency="ILS",
            dates=[pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-01")],
        )
        with requests.Session() as session:
            assert tase_specific_utils.get_Bizportal_graph_data(data, session)
        for field in ("price", "open", "high", "low"):
            assert getattr(data, field) == pytest.approx([1.595])
        assert data.last == pytest.approx(1.595)
        assert data.currency == "ILS"

    @pytest.mark.parametrize(
        ("currency_label", "expected_currency", "expected_price"),
        [
            ("שקל", "ILS", 159.5),
            ("₪", "ILS", 159.5),
            ("דולר", "USD", 159.5),
            ("אגורות", "ILS", 1.595),
        ],
    )
    def test_bizportal_scales_only_the_verified_currency_label(
        self,
        pysft_env,
        provider_gateway,
        monkeypatch,
        currency_label,
        expected_currency,
        expected_price,
    ):
        indicator = "5111422"
        _install_raw_bizportal_mtf(
            monkeypatch, indicator, 159.5, currency_label
        )

        result = fetch_data(
            indicator,
            mode="all",
            start="2026-10-01",
            end="2026-10-01",
        )[indicator]

        assert result["price"] == pytest.approx([expected_price])
        assert result["currency"] == [expected_currency]

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

    @pytest.mark.parametrize(
        ("indicator", "quote_type"),
        [("5111422", "STOCK"), ("1144633", "ETF"), ("1183441", "ETF")],
    )
    def test_maya_parser_applies_agorot_factor_once(self, monkeypatch, indicator, quote_type):
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
            indicator=indicator,
            ISIN="IL-5111422",
            quoteType=quote_type,
            dates=[pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-02")],
        )

        assert tase_specific_utils.get_MAYA_TASE_graph_data(data, Session()) is True
        assert data.price == pytest.approx([1.599])
