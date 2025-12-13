# ---- Standard library imports ----
from typing import Callable
import asyncio

# ---- Package imports ----
from pysft.core.enums import E_FetchType
from pysft.core.structures import outputCls

from pysft.fetchers.fetch_yfinance import fetch_yfinance
from pysft.fetchers.TASE_fast import fetch_TASE_fast
from pysft.fetchers.TASE_historical import fetch_TASE_historical

class fetchTask:
    def __init__(self, fetch_type: E_FetchType, data: outputCls):
        self.fetch_type = fetch_type
        self.data: outputCls = data
        self.fetchFcn: Callable

        self.setFetchFcn()

    def setFetchFcn(self):
        """
        This method sets the appropriate fetch function based on the fetch type.
        """
        if self.fetch_type == E_FetchType.YFINANCE:
            self.fetchFcn = fetch_yfinance
        elif self.fetch_type == E_FetchType.TASE_FAST:
            self.fetchFcn = fetch_TASE_fast
        elif self.fetch_type == E_FetchType.TASE_HISTORICAL:
            self.fetchFcn = fetch_TASE_historical
        else:
            raise ValueError(f"Unsupported fetch type encountered: {self.fetch_type}")
        
    def execute(self):
        """
        Execute the fetch function synchronously.
        """
        self.fetchFcn(self.data)

    def execute_async(self):
        """
        Execute the fetch function asynchronously.
        """
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self.fetchFcn, self.data)

    def get_results(self) -> outputCls | list[outputCls]:
        """
        Retrieve the fetched data after execution.
        """
        return self.data
