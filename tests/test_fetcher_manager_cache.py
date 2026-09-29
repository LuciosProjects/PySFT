"""Tests for historical cache-span selection."""

from __future__ import annotations

import pandas as pd
import pytest

from pysft.core.fetcher_manager import _select_cached_date_span

pytestmark = [pytest.mark.unit]


class TestCachedDateSpan:
    def test_selects_a_safely_surrounded_span(self) -> None:
        cached_dates = pd.date_range("2024-01-01", "2024-01-10")
        requested_dates = pd.date_range("2024-01-03", "2024-01-05")
        calendar_in_period = pd.date_range("2024-01-03", "2024-01-05")

        result = _select_cached_date_span(
            cached_dates,
            requested_dates,
            calendar_in_period,
        )

        assert result is not None
        assert result.equals(pd.date_range("2024-01-03", "2024-01-05"))

    @pytest.mark.parametrize(
        ("requested_dates", "calendar_in_period"),
        [
            (
                pd.date_range("2024-01-01", "2024-01-03"),
                pd.date_range("2024-01-01", "2024-01-03"),
            ),
            (
                pd.date_range("2024-01-08", "2024-01-10"),
                pd.date_range("2024-01-08", "2024-01-10"),
            ),
        ],
    )
    def test_rejects_spans_without_both_safe_neighbors(
        self,
        requested_dates: pd.DatetimeIndex,
        calendar_in_period: pd.DatetimeIndex,
    ) -> None:
        cached_dates = pd.date_range("2024-01-01", "2024-01-10")

        assert (
            _select_cached_date_span(
                cached_dates,
                requested_dates,
                calendar_in_period,
            )
            is None
        )

    def test_rejects_an_empty_trading_calendar_range(self) -> None:
        assert (
            _select_cached_date_span(
                pd.date_range("2024-01-01", "2024-01-10"),
                pd.date_range("2024-01-06", "2024-01-07"),
                pd.DatetimeIndex([]),
            )
            is None
        )
