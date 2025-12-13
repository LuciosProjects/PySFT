"""
    Utilities — small, dependency-free helpers used across the codebase.

    Provides compact, well-documented helpers for:
    - File and path operations (ensure dirs, atomic writes, safe reads)
    - Serialization/parsing (JSON load/dump, tolerant parsers)
    - Collections (merge, chunk, ensure_list)
    - String validators and simple normalization
    - Lightweight resiliency/concurrency (retry, memoize, timer)

    Design: minimal stdlib implementations, clear error semantics, cross-platform I/O.
    Functions raise ValueError/TypeError for invalid input and propagate I/O/OS errors.
    Exported helpers form the module's public API and are intended to be stable.
"""

# ---- Standard library imports ----
from typing import TYPE_CHECKING, Any
import os
import json
import pandas as pd

# ---- Package imports ----
import pysft.core.constants as const
from pysft.core.enums import E_FetchType
from pysft.core.structures import indicatorRequest, outputCls

from pysft.core.fetch_task import fetchTask

from pysft.core.models import _YF_fetchReq_Container

from pysft.tools.logger import get_logger

if TYPE_CHECKING:
    from pysft.core.fetcher_manager import fetcher_manager

logger = get_logger(__name__)

def has_tase_indicators(indicators: list[str]) -> tuple[bool, list[bool]]:
    """
    Check if the list of indicators contains any TASE indicators.
    
    Args:
        indicators (list[str]): List of financial indicators.
        
    Returns:
        bool: True if any indicator is a TASE indicator, False otherwise.
    """

    is_tase_indicators = [indicator.isdigit() or indicator.startswith("126.") 
                          for indicator in indicators]
    return any(is_tase_indicators), is_tase_indicators

def classify_fetch_types(manager: 'fetcher_manager'):
    """
    Classify indicators into their fetch types (YFINANCE, TASE_FAST, or TASE_HISTORICAL).

    Determines the appropriate data source for each indicator based on whether it's
    a TASE security and the requested data length. Updates manager settings and
    populates the requests dictionary with fetch type and indicator metadata.

    Args:
        manager (fetcher_manager): Manager instance containing parsed input, settings, and indicators.

    Returns:
        None. Updates manager.requests with fetch type classifications for all indicators.
    """

    indicators = manager.parsedInput.indicators
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)
    json_path = os.path.join(current_dir, '../data/indicator_international_symbols.json')
    
    with open(json_path, 'r') as f:
        international_vault: dict = json.load(f)

    has_tase, is_tase_indicator = has_tase_indicators(indicators)
    is_historical = has_tase and (manager.settings.data_length > 1)
    
    date_range = [pd.Timestamp(date) for date in pd.date_range(start=manager.settings.start_date, end=manager.settings.end_date)]

    requests: dict[str, dict[str, Any]] = {}

    for i in range(manager.settings.indicators_count):
        requests[indicators[i]] = {const.FETCH_TYPE_FIELD: E_FetchType.NULL, const.REQUEST_FIELD: indicatorRequest(indicators[i], date_range)}

        fetchType = E_FetchType.NULL
        if is_tase_indicator[i]:
            if indicators[i] in international_vault.keys():
                # If the indicator is found in the international vault, use yfinance
                requests[indicators[i]][const.FETCH_TYPE_FIELD] = E_FetchType.YFINANCE

                requests[indicators[i]][const.REQUEST_FIELD].indicator = international_vault[indicators[i]]['symbol']
                requests[indicators[i]][const.REQUEST_FIELD].data.name = international_vault[indicators[i]]['name']

                # Toggle YFinance flag if necessary
                if not manager.settings.NEED_YFINANCE:
                    manager.settings.NEED_YFINANCE = True

                continue

            fetchType = E_FetchType.TASE_HISTORICAL if is_historical else E_FetchType.TASE_FAST

            if not manager.settings.NEED_HISTORICAL and fetchType == E_FetchType.TASE_HISTORICAL:
                manager.settings.NEED_HISTORICAL = True
            elif not manager.settings.NEED_TASE_FAST and fetchType == E_FetchType.TASE_FAST:
                manager.settings.NEED_TASE_FAST = True
        else:
            fetchType = E_FetchType.YFINANCE

            if not manager.settings.NEED_YFINANCE:
                manager.settings.NEED_YFINANCE = True

        requests[indicators[i]][const.FETCH_TYPE_FIELD] = fetchType

    manager.requests = requests

def create_task_list(manager: 'fetcher_manager') -> list[fetchTask]:
    """
    Create a mapping of fetch types to their corresponding indicator requests.

    Organizes the indicator requests based on their classified fetch types,
    facilitating efficient data retrieval from the appropriate sources.

    Args:
        manager (fetcher_manager): Manager instance containing classified requests.
    Returns:
        list[tuple[E_FetchType, indicatorRequest | list[indicatorRequest]]]
            A list of tuples, each containing a fetch type and its associated
            indicator request or list of requests.
    """

    tasks: list[fetchTask] = []
    YF_BatchList: list[indicatorRequest] = []
    date_range = [pd.Timestamp(date) for date in pd.date_range(start=manager.settings.start_date, end=manager.settings.end_date)]

    for request in manager.requests.items():
        fetchType = request[1][const.FETCH_TYPE_FIELD]

        if fetchType == E_FetchType.YFINANCE and  len(YF_BatchList) < const.YF_BATCH_SIZE:
            # fetch type is for yfinance, append to YF batch list
            YF_BatchList.append(request[1][const.REQUEST_FIELD])
        elif fetchType == E_FetchType.YFINANCE:
            # YF batch is full, add to tasks and reset YF batch list
            tasks.append(fetchTask(E_FetchType.YFINANCE, _YF_fetchReq_Container(YF_BatchList, date_range)))
            YF_BatchList = []

        elif fetchType == E_FetchType.TASE_FAST:
            tasks.append(fetchTask(E_FetchType.TASE_FAST, request[1][const.REQUEST_FIELD]))
        
        elif fetchType == E_FetchType.TASE_HISTORICAL:
            tasks.append(fetchTask(E_FetchType.TASE_HISTORICAL, request[1][const.REQUEST_FIELD]))

    if YF_BatchList:
        tasks.append(fetchTask(E_FetchType.YFINANCE, _YF_fetchReq_Container(YF_BatchList, date_range)))

    return tasks

# Array manipulation utilities
def unique(arr: list[Any]) -> tuple[list[Any], dict[Any, int]]:
    """
        Return a list of unique elements while preserving order.
    """

    seen = set()
    unique_list = []
    itemRepetitions = {}

    for item in arr:
        if item not in seen:
            seen.add(item)
            unique_list.append(item)
            itemRepetitions[item] = 1
        else:
            itemRepetitions[item] += 1

    return unique_list, itemRepetitions

# String manipulation utilities
def add_attempt2msg(msg: str, attempt: int )-> str:
    """
    Add attempt information to the request message.
    
    Args:
        msg (str): The message string to update.
        attempt (int): The current attempt number.
    Returns:
        str: The updated message with attempt information.
    """

    if attempt < const.MAX_ATTEMPTS - 1:
        msg += f" - Retrying ({attempt + 1}/{const.MAX_ATTEMPTS})"
    else:
        msg += f" - Giving up after {const.MAX_ATTEMPTS} attempts"

    return msg

def safe_extract_date_ts(dates: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """
    Safely extract date strings from a Pandas DatetimeIndex.

    Args:
        dates (pd.DatetimeIndex): The DatetimeIndex to extract date strings from.
    Returns:
        list[str]: A list of date strings in 'YYYY-MM-DD' format.
    """

    date_ts = []
    for date in dates:
        try:
            date_ts.append(pd.Timestamp(date))
        except Exception:
            logger.error(f"Failed to convert dates to ts array.")

    return date_ts