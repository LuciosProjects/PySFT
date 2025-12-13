from typing import TYPE_CHECKING, Any
import pandas as pd

# ---- Package imports ----
from pysft.core.utilities import classify_fetch_types, create_task_list
from pysft.core.models import fetcher_settings

if TYPE_CHECKING:
    from pysft.core.models import _fetchRequest

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
        

    def getResults(self) -> pd.DataFrame:
        """
        Retrieve the aggregated fetched data.

        Returns:
            pd.DataFrame: The fetched indicator data.
        """

        # _inidicator_data merging logic would go here? we will see later...

        return self.fetched_data