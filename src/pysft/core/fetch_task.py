# ---- Standard library imports ----
import time
from typing import Callable
import asyncio

# ---- Package imports ----
from pysft.core import constants as const
from pysft.core.enums import E_FetchType
from pysft.core.structures import outputCls, indicatorRequest
from pysft.core import utilities as utils

from pysft.fetchers.fetch_yfinance import fetch_yfinance
from pysft.fetchers.TASE import fetch_TASE
# from pysft.fetchers.TASE_historical import fetch_TASE_historical

class fetchTask:
    def __init__(self, fetch_type: E_FetchType, data: outputCls):
        self.fetch_type = fetch_type
        self.data: outputCls = data
        self.fetchFcn: Callable
        self.result: indicatorRequest | list[indicatorRequest] = []

        self.setFetchFcn()

        self.est_mem_req_bytes = const.MAX_TASK_MEMORY_ALLOCATION # estimated memory requirement in bytes
        
        self.created_at = time.time()

    def setFetchFcn(self):
        """
        This method sets the appropriate fetch function based on the fetch type.
        """
        if self.fetch_type == E_FetchType.YFINANCE:
            self.fetchFcn = fetch_yfinance
        elif self.fetch_type == E_FetchType.TASE:
            self.fetchFcn = fetch_TASE
        # elif self.fetch_type == E_FetchType.TASE_HISTORICAL:
        #     self.fetchFcn = fetch_TASE
        else:
            raise ValueError(f"Unsupported fetch type encountered: {self.fetch_type}")
        
    def execute(self):
        """
        Execute the fetch function synchronously.
        """
        self.fetchFcn(self.data)
        self.prepare_results()

    async def execute_async(self):
        """
        Execute the fetch function asynchronously.
        """
        rate_limit_nominal_seconds = const.RATELIMIT_PAUSE.seconds()
        utils.random_delay(rate_limit_nominal_seconds - 0.5, rate_limit_nominal_seconds + 0.5) # delay task execution in async mode to avoid rate limiting

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.fetchFcn, self.data)

        self.prepare_results()

    def prepare_results(self):
        """
        Prepare the results after fetching is done.
        """
        if hasattr(self.data, 'requests'):
            self.result = getattr(self.data, 'requests')
        else:
            self.result = getattr(self, 'data')

    def get_results(self) -> indicatorRequest | list[indicatorRequest]:
        """
        Retrieve the fetched data after execution.
        """

        return self.result
