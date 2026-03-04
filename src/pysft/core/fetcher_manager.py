from typing import TYPE_CHECKING, Any, Set
import pandas as pd
import numpy as np

# ---- Package imports ----
import pysft.core.constants as const
from pysft.core.enums import E_FetchType
from pysft.core.utilities import classify_fetch_types, create_task_list
from pysft.core.models import fetcher_settings
from pysft.core.database import get_db_manager, _get_timeseries_fields
from pysft.core.structures import indicatorRequest, _indicator_data
from pysft.core.constants import DB_ENABLED
# from pysft.core.io import _parse_attributes

import pysft.core.tase_specific_utils as tase_utils

from pysft.core.task_scheduler import taskScheduler

if TYPE_CHECKING:
    from pysft.core.structures import indicatorRequest
    from pysft.core.models import _fetchRequest
    from pysft.core.fetch_task import fetchTask

class fetcher_manager:
    """
    Manage the fetching of indicator data based on a fetch request.

    This manager orchestrates the retrieval and aggregation of financial indicator
    data according to specified criteria.

    Args:
        request (_fetchRequest): The fetch request containing indicators, attributes, and time range.

    Returns:
        pd.DataFrame: A DataFrame containing the aggregated fetched indicator data.
    """

    def __init__(self, request: '_fetchRequest'):

        self.parsedInput = request
        self.settings = fetcher_settings(request)
        self.requests: dict[str, dict[str, Any]] = {}
        self.fetched_data: pd.DataFrame # output field to be populated with fetched data
        self.cached_indicators: list[str] = [] # indicators found fully cached in the database
        self._timeseries_fields = _get_timeseries_fields()

    def managerRoutine(self) -> None:
        """
        Execute the main routine to fetch and process data based on the request.
        
        Populates self.fetched_data with retrieved indicator information.
        """

        # Check cache first
        self._check_cache()
        
        # Only classify and fetch for indicators not fully cached
        classify_fetch_types(self)

        # find a YF equivalent amonth teh TASE indicators to reduce TASE fetch load, it MUST be done after fetch type classification
        self.settings.NEED_TASE = tase_utils.find_YF_equivalent(self.requests)

        if self.settings.NEED_TASE:
            tase_utils.get_tase_mtf_listing() # Initialize the TASE_MTF_LISTINGS global variable
            # tase_utils.get_tase_security_listings(pd.Timestamp.today().date()) # Initialize TASE_SECURITY_LISTINGS global variable
            tase_utils.get_tase_company_listings() # Initialize TASE_COMPANIES_LISTING global variable

        taskList = create_task_list(self)

        # Initialize and run task scheduler
        scheduler = taskScheduler(taskList)

        # Initialize task scheduler with taskList, for now we will just serialy execute them
        scheduler.run()
        
        # for task in taskList:
        #     task.execute()
        
        # Cache the newly fetched data
        self._cache_fetched_data(taskList)
        
        # Aggregate results to dataframe, unfold lists if needed
        self.aggregate_task_results(taskList)

    
    def aggregate_task_results(self, taskList: list['fetchTask']) -> None:
        """
        Aggregate results from all fetch tasks into a single DataFrame.
        
        Handles merging of partially cached indicators with newly fetched data.
        """

        results: dict[str, indicatorRequest] = {}
        db = get_db_manager() if DB_ENABLED else None
        
        # Add cached results first
        if hasattr(self, '_cached_results'):
            results.update(self._cached_results)
        
        # Add newly fetched results, merging with partial cache if needed
        for task in taskList:
            task_result = task.get_results()
            fetched_results = task_result if isinstance(task_result, list) else [task_result]
            
            for res in fetched_results:
                indicator = res.original_indicator
                
                results[indicator] = res

        # Reorder result list according to the original indicators order
        # Use the original request indicators (before cache filtering)
        original_indicators = getattr(self.parsedInput, '_original_indicators', self.parsedInput.indicators)
        ordered_results: list[indicatorRequest] = []
        for indicator in original_indicators:
            if indicator in results: # sanity check
                ordered_results.append(results[indicator])

        # Convert to DataFrame
        # Use original requested attributes, not the forced "all" attributes
        requested_attrs = getattr(self.parsedInput, '_original_attributes', self.parsedInput.attributes)
        self.fetched_data = pd.DataFrame()
        for res in ordered_results:
            if res.success:
                indicator_DF = pd.DataFrame({field: getattr(res.data, field) for field in requested_attrs}, 
                                        index=(res.data.dates if isinstance(res.data.dates, list) else [res.data.dates]))
            else:
                # Create empty DataFrame with NaN values for requested attributes
                indicator_DF = pd.DataFrame({field: [float('nan')] * (len(res.data.dates) if isinstance(res.data.dates, list) else 1) for field in requested_attrs}, 
                                        index=(res.data.dates if isinstance(res.data.dates, list) else [res.data.dates]))
            
            # Add multi-level column labels: (indicator, attribute)
            indicator_DF.columns = pd.MultiIndex.from_product(
                [[getattr(res, "original_indicator")], requested_attrs],
                names=['Indicator', 'Attribute']
            )
            self.fetched_data = pd.concat([self.fetched_data, indicator_DF], axis=1)
            
            del indicator_DF  # free memory


    def _check_cache(self) -> None:
        """
        Check cache for requested indicators and populate results if fresh data exists.
        
        For timeseries requests (with date range), also checks cached historical data
        and determines which dates need fetching.
        
        Modifies:
            - parsedInput.indicators: removes fully cached indicators
            - self.cached_indicators: tracks fully cached indicators
            - self.partially_cached_indicators: indicator -> cached dates
            - self.missing_dates: indicator -> dates needing fetch
            - self._cached_results: cached indicatorRequest objects
        """
        
        if not DB_ENABLED:
            return
        
        db = get_db_manager()
        cached_results: dict[str, indicatorRequest] = {}
        indicators_to_fetch: list[str] = []

        # Check if this is a timeseries request (has date range)
        is_timeseries_request = self._is_timeseries_request()
        requested_dates = self._get_requested_dates() if is_timeseries_request else pd.DatetimeIndex([])
        
        for indicator in self.parsedInput.indicators:
            # Get cached scalar data and check freshness
            cached_data, scalar_fresh = db.get_cached_data(indicator, self.parsedInput.attributes)
            
            # No scalar freshness means we need to fetch (Currently commented to test other logic)
            if not scalar_fresh:
                indicators_to_fetch.append(indicator)
                continue

            if is_timeseries_request and not requested_dates.empty:
                # Check timeseries cache
                cached_dates = db.get_cached_dates(indicator)

                # If cached_dates has a date before requested_dates[0] but not more than 1 month earlier,
                # and after requested_dates[-1] but not more than 1 month later, we can assume a full cache of the span of the requested dates
                if cached_dates.empty:
                    # No cached dates at all
                    indicators_to_fetch.append(indicator)
                    continue
                else:
                    # Cached data exists

                    # Check if requested date range is fully covered by cached dates according to trading calendar logic (allowing for some uncertainty at the edges)
                    calendar_in_period = tase_utils.TASE_CALENDAR.sessions_in_range(requested_dates[0], requested_dates[-1])
                    i_start_span = np.argmin(abs(cached_dates - calendar_in_period[0]))
                    i_end_span = np.argmin(abs(cached_dates - calendar_in_period[-1]))

                    if (i_end_span < len(cached_dates) - 1 and \
                        abs((cached_dates[i_start_span-1] - requested_dates[0]).days) <= const.CACHED_DATES_MAX_DELTA) and \
                          (abs((cached_dates[i_end_span+1] - requested_dates[-1]).days) <= const.CACHED_DATES_MAX_DELTA):
                        requested_dates = pd.DatetimeIndex(cached_dates[i_start_span:i_end_span+1])
                    else:
                        # Uncertainty in cached span, need to fetch
                        indicators_to_fetch.append(indicator)
                        continue
                
                    # All dates cached and scalars fresh - fully cached
                    hist_data = db.get_historical_data(
                        indicator,
                        self.parsedInput.start_ts,
                        self.parsedInput.end_ts
                    )
                    
                    if hist_data:
                        # Merge scalar metadata with historical timeseries
                        merged_data = self._merge_cached_data(cached_data, hist_data)
                        
                        req = indicatorRequest(indicator=indicator, dates=merged_data.dates)
                        req.data = merged_data
                        req.original_indicator = indicator
                        req.success = True
                        req.start_date = self.settings.start_date
                        req.end_date = self.settings.end_date
                        req.message = "Data retrieved from database cache."

                        cached_results[indicator] = req
                        self.cached_indicators.append(indicator)
                    else:
                        # No historical data found, need to fetch
                        indicators_to_fetch.append(indicator)
            
            elif cached_data and scalar_fresh:
                # Check if price exists in cached_data for the requested date (for non-timeseries, just current price)
                # All dates cached and scalars fresh - fully cached
                hist_data = db.get_historical_data(
                    indicator,
                    pd.Timestamp(self.settings.start_date),
                    pd.Timestamp(self.settings.end_date)
                )

                if hist_data:
                    # Historical data exists for the requested date, get data for the requested date
                    req = indicatorRequest(indicator=indicator, dates=cached_data.dates)
                    req.data = cached_data
                    req.original_indicator = indicator
                    req.success = True
                    # req.start_date = self.settings.start_date
                    # req.end_date = self.settings.end_date
                    
                    for attr in self._timeseries_fields:
                        value = getattr(hist_data, attr)
                        setattr(req.data, attr, value[0] if type(value) in [list, np.ndarray] else value)

                    req.message = "Data retrieved from database cache."

                    cached_results[indicator] = req
                    self.cached_indicators.append(indicator)
                else:
                    # No historical data found, need to fetch
                    indicators_to_fetch.append(indicator)
            else:
                # Need to fetch
                indicators_to_fetch.append(indicator)
        
        # Store cached results for aggregation
        if cached_results:
            if not hasattr(self, '_cached_results'):
                self._cached_results = {}
            self._cached_results.update(cached_results)
        
        # Update parsedInput to only fetch non-cached indicators
        if indicators_to_fetch:
            self.parsedInput.indicators = indicators_to_fetch
        else:
            # All indicators cached, no need to fetch
            self.parsedInput.indicators = []
    
    def _is_timeseries_request(self) -> bool:
        """Check if request is for timeseries data (has date range)."""
        return (self.settings.end_date - self.settings.start_date).days > 1 and \
                any(attr in self._timeseries_fields for attr in self.parsedInput.attributes) 
    
    def _get_requested_dates(self) -> pd.DatetimeIndex:
        """Generate all dates in the requested range."""

        # if (self.settings.end_date - self.settings.start_date).days < 1:
        #     # start and end dates are the same
        #     return pd.DatetimeIndex(pd.to_datetime([self.settings.start_date]))

        # Generate date range
        date_range = pd.date_range(
            start=self.settings.start_date,
            end=self.settings.end_date,
        )
        return date_range
    
    def _merge_cached_data(
        self, 
        scalar_data: _indicator_data | None, 
        timeseries_data: _indicator_data
    ) -> _indicator_data:
        """
        Merge scalar metadata with timeseries historical data.
        
        Args:
            scalar_data: Cached scalar fields (name, ISIN, etc.)
            timeseries_data: Cached historical prices
            
        Returns:
            Combined _indicator_data
        """
        if scalar_data is None:
            return timeseries_data
        
        # Start with timeseries data (has dates, prices, etc.)
        merged = timeseries_data
        
        # Copy scalar fields from scalar_data
        scalar_fields = set(_indicator_data.__dataclass_fields__.keys()) - self._timeseries_fields
        for field in scalar_fields:
            scalar_value = getattr(scalar_data, field, None)
            if scalar_value is not None and scalar_value != "" and scalar_value != 0:
                setattr(merged, field, scalar_value)
        
        return merged


    def _cache_fetched_data(self, taskList: list['fetchTask']) -> None:
        """
        Cache successfully fetched indicator data.
        
        Args:
            taskList: List of completed fetch tasks
        """
        if not DB_ENABLED:
            return
        
        db = get_db_manager()
        
        for task in taskList:
            task_result = task.get_results()
            results = task_result if isinstance(task_result, list) else [task_result]
            
            for res in results:
                if not res.success:
                    continue
                
                indicator = res.original_indicator
                data = res.data
                
                # Determine which fields were actually fetched
                # Get all non-default fields from the data
                fetched_fields = []
                for field_name in data.__dataclass_fields__:
                    value = getattr(data, field_name)
                    if  value is not None and \
                        ((isinstance(value, list) or isinstance(value, np.ndarray)) and len(value) > 0) or \
                        value != 0 or value != 0.0 or value != "":
                        fetched_fields.append(field_name)
                
                # Cache metadata and metrics
                db.cache_indicator_data(indicator, data, fetched_fields)
                
                # Cache data
                db.cache_historical_data(
                    indicator=indicator,
                    dates=data.dates,
                    open_prices=data.open,
                    high_prices=data.high,
                    low_prices=data.low,
                    close_prices=data.price,
                    volumes=data.volume,
                    change_pcts=data.change_pct
                    # market_caps=data.market_cap if isinstance(data.market_cap, list) or isinstance(data.market_cap, np.ndarray) else None
                )


    def getResults(self) -> pd.DataFrame:
        """
        Retrieve the aggregated fetched data.

        Returns:
            pd.DataFrame: The fetched indicator data.
        """

        return self.fetched_data