"""Orchestrate fixed-route fetching and per-field cache reuse."""

from collections.abc import Iterator
from typing import Any, cast

import exchange_calendars as xcals
import pandas as pd

import pysft.core.constants as const
import pysft.core.tase_specific_utils as tase_utils
from pysft.core.cache_contract import HISTORY_COLUMNS, HISTORY_FIELDS, available_fields, merge_data
from pysft.core.constants import DB_ENABLED
from pysft.core.database import get_db_manager
from pysft.core.enums import E_FetchMode, E_FetchType
from pysft.core.fetch_task import fetchTask
from pysft.core.models import _fetchRequest, _YF_fetchReq_Container, fetcher_settings
from pysft.core.price_normalization import required_price_normalization_version
from pysft.core.structures import indicatorRequest
from pysft.core.task_scheduler import taskScheduler
from pysft.core.utilities import classify_fetch_types


def _select_cached_date_span(
    cached_dates: pd.DatetimeIndex, requested_dates: pd.DatetimeIndex,
    calendar_in_period: pd.DatetimeIndex,
) -> pd.DatetimeIndex | None:
    """Legacy conservative span helper retained for compatibility."""
    if cached_dates.empty or requested_dates.empty or calendar_in_period.empty:
        return None
    start = min(range(len(cached_dates)), key=lambda i: abs(
        cast(pd.Timestamp, cached_dates[i]) - cast(pd.Timestamp, calendar_in_period[0])
    ))
    end = min(range(len(cached_dates)), key=lambda i: abs(
        cast(pd.Timestamp, cached_dates[i]) - cast(pd.Timestamp, calendar_in_period[-1])
    ))
    if start == 0 or end >= len(cached_dates) - 1 or start > end:
        return None
    if (
        abs((cached_dates[start - 1] - requested_dates[0]).days) > const.CACHED_DATES_MAX_DELTA
        or abs((cached_dates[end + 1] - requested_dates[-1]).days) > const.CACHED_DATES_MAX_DELTA
    ):
        return None
    return pd.DatetimeIndex(cached_dates[start:end + 1])


class fetcher_manager:
    def __init__(self, request: _fetchRequest):
        self.parsedInput = request
        self.settings = fetcher_settings(request)
        self.requests: dict[str, dict[str, Any]] = {}
        self.fetched_data: dict[str, dict[str, Any]] = {}
        self.cached_indicators: list[str] = []
        self._cached_results: dict[str, indicatorRequest] = {}

    def managerRoutine(self) -> None:
        # Resolve ticker routing once. Provider route is not a cache key.
        classify_fetch_types(self)
        self.settings.NEED_TASE = tase_utils.find_YF_equivalent(self.requests)
        self._check_cache()
        if any(item[const.FETCH_TYPE_FIELD] == E_FetchType.TASE for item in self.requests.values()):
            tase_utils.get_tase_mtf_listing()
            tase_utils.get_tase_company_listings()
        tasks = self._create_tasks()
        taskScheduler(tasks).run()
        self._cache_fetched_data(tasks)
        self.aggregate_task_results(tasks)

    def _expected_dates(
        self, request: indicatorRequest, fetch_type: E_FetchType, exchange: str = "",
    ) -> pd.DatetimeIndex:
        start, end = pd.Timestamp(self.settings.start_date), pd.Timestamp(self.settings.end_date)
        # Original TASE identifiers can resolve to US or other Yahoo symbols.
        # is_tase_indicator describes origin, not the resolved trading calendar.
        if fetch_type == E_FetchType.TASE or request.indicator.endswith(".TA"):
            calendar = tase_utils.TASE_CALENDAR
        elif exchange.upper() in {"XNAS", "XNYS", "NASDAQ", "NYSE", "NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "BATS"}:
            calendar = xcals.get_calendar("XNYS")
        else:
            # No verified exchange: retain all requested dates instead of
            # silently declaring an original exchange's closed days covered.
            return pd.date_range(start, end)
        try:
            return calendar.sessions_in_range(start, end).tz_localize(None)
        except xcals.errors.DateOutOfBounds:
            # The calendar is finite; outside its bounds, do not claim knowledge
            # of closed days. Provider results remain authoritative.
            return pd.date_range(start, end)

    def _check_cache(self) -> None:
        if not DB_ENABLED:
            return
        db = get_db_manager()
        attrs = self.parsedInput.attributes
        scalar_attrs = [field for field in attrs if field not in HISTORY_FIELDS | {"dates"}]
        price_attrs = [field for field in attrs if field in HISTORY_FIELDS]
        start, end = pd.Timestamp(self.settings.start_date), pd.Timestamp(self.settings.end_date)
        for indicator, item in list(self.requests.items()):
            request = item[const.REQUEST_FIELD]
            scalar, scalar_fresh = db.get_cached_data(indicator, scalar_attrs)
            scalar_fresh = scalar_fresh or not scalar_attrs
            history = db.get_historical_data(indicator, start, end) if price_attrs else None
            expected = self._expected_dates(
                request, item[const.FETCH_TYPE_FIELD], scalar.exchange if scalar else "",
            ) if price_attrs else pd.DatetimeIndex([])
            missing = db.missing_history_dates(indicator, price_attrs, expected)
            price_fresh = not price_attrs or (
                history is not None and missing.empty
                and all(field in available_fields(history) for field in price_attrs)
                and not db.has_outdated_price_history(indicator, start, end)
            )
            merged = merge_data(scalar, history, start, end)
            if history is None:
                merged.dates = list(pd.date_range(start, end))
            cached = indicatorRequest(indicator, mode=self.parsedInput.mode)
            cached.data = merged
            cached.success = True
            self._cached_results[indicator] = cached
            if scalar_fresh and price_fresh:
                self.cached_indicators.append(indicator)
                del self.requests[indicator]
                continue
            need_info = bool(scalar_attrs) and not scalar_fresh
            need_price = bool(price_attrs) and not price_fresh
            mode = E_FetchMode.ALL if need_info and need_price else (
                E_FetchMode.INFO if need_info else E_FetchMode.PRICE
            )
            request.mode = mode
            # Yahoo supports a bounded download. Fetch the envelope of missing
            # sessions (including interior field gaps). TASE's graph APIs do not
            # support date selection: safely fetch and merge the requested range.
            if (
                need_price and not missing.empty
                and item[const.FETCH_TYPE_FIELD] == E_FetchType.YFINANCE
                and not db.has_outdated_price_history(indicator, start, end)
            ):
                request.start_date, request.end_date = missing[0].date(), missing[-1].date()
                request.data.dates = list(pd.date_range(missing[0], missing[-1]))

    def _create_tasks(self) -> list[fetchTask]:
        tasks: list[fetchTask] = []
        groups: dict[tuple, list[indicatorRequest]] = {}
        for item in self.requests.values():
            request = item[const.REQUEST_FIELD]
            if item[const.FETCH_TYPE_FIELD] == E_FetchType.TASE:
                tasks.append(fetchTask(E_FetchType.TASE, request))
            else:
                key = (request.mode, request.start_date, request.end_date)
                groups.setdefault(key, []).append(request)
        for (mode, start, end), requests in groups.items():
            dates = list(pd.date_range(start, end))
            for index in range(0, len(requests), const.YF_BATCH_SIZE):
                container = _YF_fetchReq_Container(requests[index:index + const.YF_BATCH_SIZE], dates, mode)
                tasks.append(fetchTask(E_FetchType.YFINANCE, container))
        return tasks

    @staticmethod
    def _task_results(tasks: list[fetchTask]) -> Iterator[indicatorRequest]:
        for task in tasks:
            result = task.get_results()
            yield from result if isinstance(result, list) else [result]

    def _cache_fetched_data(self, tasks: list[fetchTask]) -> None:
        if not DB_ENABLED:
            return
        db = get_db_manager()
        for res in self._task_results(tasks):
            if res is None or not res.success:
                continue
            fields = available_fields(res.data)
            db.cache_indicator_data(res.original_indicator, res.data, list(fields))
            if res.mode == E_FetchMode.INFO or not fields & set(HISTORY_COLUMNS):
                continue
            dates = res.data.dates
            if not isinstance(dates, list):
                dates = [dates]
            db.cache_historical_data(
                res.original_indicator, dates,
                *[getattr(res.data, field) if field in fields else None for field in HISTORY_COLUMNS],
                normalization_version=required_price_normalization_version(
                    res.original_indicator, res.data.quoteType
                ),
            )

    def aggregate_task_results(self, tasks: list[fetchTask]) -> None:
        results = dict(self._cached_results)
        explicit_range = self.parsedInput.start_ts is not None
        start = pd.Timestamp(self.settings.start_date) if explicit_range else None
        end = pd.Timestamp(self.settings.end_date) if explicit_range else None
        for res in self._task_results(tasks):
            if res is None:
                continue
            previous = results.get(res.original_indicator)
            merged = merge_data(
                previous.data if previous else None,
                res.data if res.success else None, start, end,
            )
            if not res.success and previous is None:
                merged.dates = list(pd.date_range(self.settings.start_date, self.settings.end_date))
            res.data = merged
            if explicit_range and not set(self.parsedInput.attributes) & HISTORY_FIELDS:
                res.data.dates = list(pd.date_range(self.settings.start_date, self.settings.end_date))
            res.success = bool(available_fields(merged))
            results[res.original_indicator] = res
        attrs = self.parsedInput._original_attributes
        for indicator in self.parsedInput._original_indicators:
            if indicator not in results:
                continue
            res = results[indicator]
            fields = available_fields(res.data)
            dates = res.data.dates
            dates = dates if isinstance(dates, list) else [dates]
            entry: dict[str, Any] = {"dates": [pd.Timestamp(date).date().isoformat() for date in dates or []]}
            for field in attrs:
                if field == "dates":
                    continue
                value = getattr(res.data, field) if field in fields else None
                if value is not None and not isinstance(value, list):
                    value = [value]
                entry[field] = value
            self.fetched_data[indicator] = entry

    def getResults(self) -> dict[str, dict[str, Any]]:
        return self.fetched_data
