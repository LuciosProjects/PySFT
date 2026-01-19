from typing import TYPE_CHECKING, Any
import pandas as pd

# ---- Package imports ----
import pysft.core.constants as const
from pysft.core.enums import E_FetchType
from pysft.core.utilities import classify_fetch_types, create_task_list
from pysft.core.models import fetcher_settings
from pysft.core.database import get_db_manager
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
        self.cached_indicators: set[str] = set()  # Track which indicators came from cache


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
        """

        results: dict[str, indicatorRequest] = {}
        
        # Add cached results first
        if hasattr(self, '_cached_results'):
            results.update(self._cached_results)
        
        # Add newly fetched results
        for task in taskList:
            task_result = task.get_results()
            if isinstance(task_result, list):
                for res in task_result:
                    results[res.original_indicator] = res
            else:
                results[task_result.original_indicator] = task_result

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
            indicator_DF = pd.DataFrame({field: getattr(res.data, field) for field in requested_attrs}, 
                                        index=res.data.dates)
            
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
        Modifies parsedInput to exclude cached indicators and force 'all' attributes for web fetch.
        """
        if not DB_ENABLED:
            return
        
        db = get_db_manager()
        cached_results: dict[str, indicatorRequest] = {}
        indicators_to_fetch: list[str] = []
        
        for indicator in self.parsedInput.indicators:
            # Get cached data and check freshness
            cached_data, is_fresh = db.get_cached_data(indicator, self.parsedInput.attributes)
            
            if cached_data and is_fresh:
                # Create successful indicatorRequest from cache
                req = indicatorRequest(indicator=indicator, dates=cached_data.dates)
                req.data = cached_data
                req.original_indicator = indicator
                req.success = True
                req.start_date = self.settings.start_date
                req.end_date = self.settings.end_date
                
                cached_results[indicator] = req
                self.cached_indicators.add(indicator)
            else:
                # Need to fetch from web
                indicators_to_fetch.append(indicator)
        
        # Store cached results for aggregation
        if cached_results:
            if not hasattr(self, '_cached_results'):
                self._cached_results = {}
            self._cached_results.update(cached_results)
        
        # Update parsedInput to only fetch non-cached indicators
        # and force fetching ALL attributes to keep cache complete
        if indicators_to_fetch:
            self.parsedInput.indicators = indicators_to_fetch
            # # Force fetch all attributes to maintain complete cache
            # self.parsedInput.attributes = _parse_attributes("all")
        else:
            # All indicators cached, no need to fetch
            self.parsedInput.indicators = []


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
                    # Skip empty/default values
                    if field_name == "indicator" or field_name == "dates":
                        continue
                    if value and value != 0 and value != 0.0 and value != "" and value != []:
                        fetched_fields.append(field_name)
                
                # Cache metadata and metrics
                db.cache_indicator_data(indicator, data, fetched_fields)
                
                # Cache historical data if present
                if isinstance(data.dates, list) and len(data.dates) > 1:
                    # Only cache if we have list data (historical, not current)
                    if isinstance(data.last, list):
                        db.cache_historical_data(
                            indicator=indicator,
                            dates=data.dates,
                            open_prices=data.open if isinstance(data.open, list) else [data.open] * len(data.dates),
                            high_prices=data.high if isinstance(data.high, list) else [data.high] * len(data.dates),
                            low_prices=data.low if isinstance(data.low, list) else [data.low] * len(data.dates),
                            close_prices=data.last if isinstance(data.last, list) else [data.last] * len(data.dates),
                            volumes=data.volume if isinstance(data.volume, list) else [data.volume] * len(data.dates),
                            change_pcts=data.change_pct if isinstance(data.change_pct, list) else None,
                            market_caps=data.market_cap if isinstance(data.market_cap, list) else None
                        )


    def getResults(self) -> pd.DataFrame:
        """
        Retrieve the aggregated fetched data.

        Returns:
            pd.DataFrame: The fetched indicator data.
        """

        return self.fetched_data