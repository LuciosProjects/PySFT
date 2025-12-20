from typing import TYPE_CHECKING, Any
import pandas as pd

# ---- Package imports ----
from pysft.core.utilities import classify_fetch_types, create_task_list
from pysft.core.models import fetcher_settings

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


    def managerRoutine(self) -> None:
        """
        Execute the main routine to fetch and process data based on the request.
        
        Populates self.fetched_data with retrieved indicator information.
        """

        classify_fetch_types(self)
        taskList = create_task_list(self)

        # Initialize task scheduler with taskList, for now we will just serialy execute them
        for task in taskList:
            task.execute()
        
        # Aggregate results to dataframe, unfold lists if needed
        self.aggregate_task_results(taskList)

    
    def aggregate_task_results(self, taskList: list['fetchTask']) -> None:
        """
        Aggregate results from all fetch tasks into a single DataFrame.
        """

        results: dict[str, indicatorRequest] = {}
        for task in taskList:
            task_result = task.get_results()
            if isinstance(task_result, list):
                for res in task_result:
                    results[res.original_indicator] = res
            else:
                results[task_result.original_indicator] = task_result

        # Reorder result list according to the original indicators order
        ordered_results: list[indicatorRequest] = []
        for indicator in self.parsedInput.indicators:
            if indicator in results: # sanity check
                ordered_results.append(results[indicator])

        # Convert to DataFrame
        self.fetched_data = pd.DataFrame()
        for res in ordered_results:
            indicator_DF = pd.DataFrame({field: getattr(res.data, field) for field in self.parsedInput.attributes}, 
                                        index=res.data.dates)
            
            # Add multi-level column labels: (indicator, attribute)
            indicator_DF.columns = pd.MultiIndex.from_product(
                [[getattr(res, "original_indicator")], self.parsedInput.attributes],
                names=['Indicator', 'Attribute']
            )
            self.fetched_data = pd.concat([self.fetched_data, indicator_DF], axis=1)


    def getResults(self) -> pd.DataFrame:
        """
        Retrieve the aggregated fetched data.

        Returns:
            pd.DataFrame: The fetched indicator data.
        """

        return self.fetched_data