from typing import TYPE_CHECKING
from aiohttp import request
import pandas as pd

# ---- Package imports ----
from pysft.models import _indicator_data, fetcher_settings

if TYPE_CHECKING:
    from pysft.models import _fetchRequest

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
        self.fetched_data = pd.DataFrame()

    def managerRoutine(self) -> None:
        """
        Execute the main routine to fetch and process data based on the request.
        
        Populates self.fetched_data with retrieved indicator information.
        """
        
        pass

    def getResults(self) -> pd.DataFrame:
        """
        Retrieve the aggregated fetched data.

        Returns:
            pd.DataFrame: The fetched indicator data.
        """

        # _inidicator_data merging logic would go here? we will see later...

        return self.fetched_data