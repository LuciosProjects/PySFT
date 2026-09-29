"""PySFT fetch task.

A `fetchTask` encapsulates:
- the fetch type (E_FetchType)
- either a single indicator request or a batched yfinance request container
- the concrete blocking fetch function

Schedulers should treat a task as a black box and only call:
- `await task.execute_async()`  (preferred)
- or `task.execute()`           (sync)

Design note
-----------
Most fetchers in PySFT are I/O-bound and blocking (requests / 3rd-party libs).
`execute_async()` therefore runs the underlying fetcher in a background thread.
"""

from __future__ import annotations
import time

# ---- Standard library imports ----
from typing import TYPE_CHECKING, Callable

# ---- Package imports ----
from pysft.core import constants as const
from pysft.core.enums import E_FetchType
from pysft.core.structures import indicatorRequest
# from pysft.core import utilities as utils

from pysft.fetchers.fetch_yfinance import fetch_yfinance
from pysft.fetchers.TASE import fetch_TASE

if TYPE_CHECKING:
    from pysft.core.models import _YF_fetchReq_Container


class fetchTask:
    """A single fetch task.

    Notes
    -----
    * `execute()` is synchronous.
    * `execute_async()` is the canonical coroutine entrypoint.
    """

    def __init__(
        self,
        fetch_type: E_FetchType,
        data: indicatorRequest | _YF_fetchReq_Container,
    ):

        self.fetch_type = fetch_type
        self.data: indicatorRequest | _YF_fetchReq_Container = data
        self.fetchFcn: Callable
        self.result: indicatorRequest | list[indicatorRequest] = []

        self.setFetchFcn()

        self.est_mem_req_bytes = const.MAX_TASK_MEMORY_ALLOCATION # estimated memory requirement in bytes
        
        self.created_at = time.time()

    def setFetchFcn(self):
        """This method sets the appropriate fetch function based on the fetch type."""
        if self.fetch_type == E_FetchType.YFINANCE:
            self.fetchFcn = fetch_yfinance
        elif self.fetch_type == E_FetchType.TASE:
            self.fetchFcn = fetch_TASE
        # elif self.fetch_type == E_FetchType.TASE_HISTORICAL:
        #     self.fetchFcn = fetch_TASE
        else:
            raise ValueError(f"Unsupported fetch type encountered: {self.fetch_type}")
        
    def execute(self):
        """Execute the fetch function synchronously."""
        try:
            self.fetchFcn(self.data)
        except Exception as e:
            from pysft.tools.logger import get_logger
            get_logger(__name__).error(f"Unhandled exception in {self.fetch_type} fetch: {e}")
            if isinstance(self.data, indicatorRequest):
                self.data.success = False
                self.data.message = str(e)
            else:
                for req in self.data.requests:
                    req.success = False
                    req.message = str(e)
        finally:
            self.prepare_results()

    # async def execute_async(self) -> indicatorRequest | list[indicatorRequest]:
    #     """Execute the fetch function asynchronously.
        
    #     This is implemented by:
    #     1) a small non-blocking jittered delay (helps reduce stampeding/rate-limit bursts)
    #     2) running the blocking fetch function in a background thread
    #     3) preparing results after completion
    #     """
        
    #     # Rate limit delay with jitter 
    #     rate_limit_nominal_seconds = const.RATELIMIT_PAUSE.seconds()
    #     low = max(0.0, rate_limit_nominal_seconds - 0.5)
    #     high = max(low, rate_limit_nominal_seconds + 0.5)
    #     await asyncio.sleep(random.uniform(low, high))
        
    #     # Run the blocking fetch function in a background thread
    #     await asyncio.to_thread(self.fetchFcn, self.data)

    #     return self.prepare_results()
    
    # async def run(self) -> indicatorRequest | list[indicatorRequest]:
    #     """Alias for `execute_async()` so the scheduler can call a consistent method."""
    #     return await self.execute_async()

    def prepare_results(self):
        """
        Prepare the results after fetching is done.
        """

        if isinstance(self.data, indicatorRequest):
            self.result = self.data
        else:
            self.result = self.data.requests

    def get_results(self) -> indicatorRequest | list[indicatorRequest]:
        """Retrieve results after execution of the fetcher function."""

        return self.result
