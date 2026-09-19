"""Declarative provider scenarios for deterministic E2E tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any

import pandas as pd

from pysft.core import constants
from pysft.core.enums import E_FetchMode, E_FetchType


@dataclass(frozen=True)
class ProviderResult:
    """One controlled provider outcome."""

    provider: str
    dates: tuple[pd.Timestamp, ...]
    prices: tuple[float, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class YFinanceScenarioFactory:
    """Builds readable yfinance outcomes without network calls."""

    @staticmethod
    def equity(
        symbol: str = "AAPL",
        *,
        dates: tuple[str, ...] = ("2024-01-02",),
        price: float = 100.0,
    ) -> tuple[str, ProviderResult]:
        return symbol, ProviderResult(
            provider="yfinance",
            dates=tuple(pd.Timestamp(value) for value in dates),
            prices=tuple(price + index for index in range(len(dates))),
            metadata={
                "name": f"{symbol} Incorporated",
                "ISIN": f"TEST-{symbol}",
                "quoteType": "EQUITY",
                "currency": "USD",
                "exchange": "XNAS",
                "expense_rate": 0.0,
            },
        )

    @staticmethod
    def fund(
        symbol: str = "TESTETF", *, expense_rate: float = 0.25
    ) -> tuple[str, ProviderResult]:
        key, result = YFinanceScenarioFactory.equity(symbol)
        metadata = {**result.metadata, "quoteType": "ETF", "expense_rate": expense_rate}
        return key, ProviderResult(
            result.provider, result.dates, result.prices, metadata
        )

    @staticmethod
    def fx(
        symbol: str, *, prices: tuple[float, ...] = (3.60, 3.61)
    ) -> tuple[str, ProviderResult]:
        return symbol, ProviderResult(
            provider="yfinance",
            dates=(pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")),
            prices=prices,
            metadata={
                "name": symbol,
                "quoteType": "CURRENCY",
                "currency": "USD",
                "exchange": "FX",
            },
        )

    @staticmethod
    def failure(
        symbol: str, message: str = "controlled provider failure"
    ) -> tuple[str, ProviderResult]:
        return symbol, ProviderResult("yfinance", (), (), error=message)


class TASEScenarioFactory:
    """Builds TASE outcomes and applies the production unit policy."""

    @staticmethod
    def security(
        indicator: str = "5111422",
        *,
        raw_price: float = 159.90,
        raw_currency: str = "ILA",
        dates: tuple[str, ...] = ("2024-01-02",),
    ) -> tuple[str, ProviderResult]:
        normalization = constants.CURRENCY_NORMALIZATION[raw_currency]
        normalized = raw_price * normalization["factor"]
        return indicator, ProviderResult(
            provider="tase",
            dates=tuple(pd.Timestamp(value) for value in dates),
            prices=tuple(normalized for _ in dates),
            metadata={
                "name": f"TASE {indicator}",
                "ISIN": f"IL-{indicator}",
                "quoteType": "STOCK",
                "currency": normalization["alias"],
                "exchange": "TASE",
                "expense_rate": 0.0,
            },
        )

    @staticmethod
    def fund(
        indicator: str = "1183441", *, expense_rate: float = 0.65
    ) -> tuple[str, ProviderResult]:
        key, result = TASEScenarioFactory.security(indicator, raw_price=4634.0)
        metadata = {**result.metadata, "quoteType": "MTF", "expense_rate": expense_rate}
        return key, ProviderResult(
            result.provider, result.dates, result.prices, metadata
        )

    @staticmethod
    def failure(
        indicator: str, message: str = "controlled TASE failure"
    ) -> tuple[str, ProviderResult]:
        return indicator, ProviderResult("tase", (), (), error=message)


class DeterministicProviderGateway:
    """Installs provider doubles at the fetch-task boundary."""

    def __init__(self) -> None:
        self.results: dict[str, ProviderResult] = {}
        self.routes: list[tuple[str, str]] = []
        self.calls: dict[str, int] = {}
        self._lock = Lock()

    def add(
        self, *scenarios: tuple[str, ProviderResult]
    ) -> DeterministicProviderGateway:
        self.results.update(dict(scenarios))
        return self

    def install(self, monkeypatch: Any) -> DeterministicProviderGateway:
        import pysft.core.tase_specific_utils as tase_utils
        from pysft.core import fetch_task

        monkeypatch.setattr(fetch_task, "fetch_yfinance", self.fetch_yfinance)
        monkeypatch.setattr(fetch_task, "fetch_TASE", self.fetch_tase)
        monkeypatch.setattr(
            tase_utils,
            "find_YF_equivalent",
            lambda requests: any(
                item[constants.FETCH_TYPE_FIELD] == E_FetchType.TASE
                for item in requests.values()
            ),
        )
        monkeypatch.setattr(tase_utils, "get_tase_mtf_listing", list)
        monkeypatch.setattr(tase_utils, "get_tase_company_listings", list)
        return self

    def fetch_yfinance(self, container: Any) -> None:
        for request in container.requests:
            self._apply(request, "yfinance")
        container.success = all(request.success for request in container.requests)
        container.message = "Deterministic yfinance scenario completed"

    def fetch_tase(self, request: Any) -> None:
        self._apply(request, "tase")

    def _apply(self, request: Any, provider: str) -> None:
        key = request.original_indicator
        with self._lock:
            self.routes.append((key, provider))
            self.calls[key] = self.calls.get(key, 0) + 1

        result = self.results.get(key)
        if result is None or result.provider != provider:
            request.success = False
            request.message = f"No deterministic {provider} scenario for {key}"
            return
        if result.error is not None:
            request.success = False
            request.message = result.error
            return

        prices = list(result.prices)
        request.data.dates = list(result.dates)
        request.data.indicator = key
        if request.mode != E_FetchMode.INFO:
            request.data.price = prices
            request.data.last = prices[-1]
            request.data.open = prices.copy()
            request.data.high = prices.copy()
            request.data.low = prices.copy()
            request.data.volume = [1000 + index for index in range(len(prices))]
            request.data.change_pct = [0.0 for _ in prices]
        if request.mode != E_FetchMode.PRICE:
            for field_name, value in result.metadata.items():
                setattr(request.data, field_name, value)
        request.success = True
        request.message = f"Controlled {provider} success"
