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

# ---- Package imports ----
import pysft.core.constants as const
from pysft.core.enums import E_FetchType
import pysft.core.tase_specific_utils as tase_utils
from pysft.core.structures import indicatorRequest

if TYPE_CHECKING:
    from pysft.core.fetcher_manager import fetcher_manager

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

    has_tase, is_tase_indicator = tase_utils.has_tase_indicators(indicators)
    is_historical = has_tase and (manager.settings.data_length > 1)

    requests: dict[str, dict[str, Any]] = {}

    for i in range(manager.settings.indicators_count):
        requests[indicators[i]] = {const.FETCH_TYPE_FIELD: E_FetchType.NULL, const.REQUEST_FIELD: indicatorRequest(indicators[i])}

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