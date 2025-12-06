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

from pysft.enums import E_IndicatorType
from pysft.models import TASE_SEC_URLs

# def classify_fetch_types(fetcher_data: dict) -> tuple[list[E_FetchType], list[fetchRequest]]:
#     """
#         Classify a list of indicators into their fetch types.

#         Args:
#             fetcher_data (dict): Dictionary containing indicators and other data.
#             target_date (date): Target date for the indicators.

#         Returns:
#             tuple[bool, list[E_FetchType]]: A tuple containing a success flag and a list of fetch types.
#     """

#     international_vault = json.load(open('Data/indicator_international_symbols.json', 'r'))
#     N_indicators = len(fetcher_data["data"]["indicators"])

#     has_tase, is_tase_indicator = has_tase_indicators(fetcher_data["data"]["indicators"])
#     is_historical = has_tase and fetcher_data["data"]["date"] != date.today().strftime(Constants.GENERAL_DATE_FORMAT)

#     requests = [fetchRequest(indicator=ind, date=fetcher_data["data"]["date"]) for ind in fetcher_data["data"]["indicators"]]

#     fetch_types = [E_FetchType.NULL]*N_indicators
#     for i in range(N_indicators):
#         if is_tase_indicator[i]:
#             if requests[i].indicator in international_vault.keys():
#                 # If the indicator is found in the international vault, use yfinance
#                 fetch_types[i] = E_FetchType.YFINANCE
#                 original_indicator = requests[i].indicator

#                 requests[i].original_indicator  = original_indicator
#                 requests[i].indicator           = international_vault[original_indicator]['symbol']
#                 requests[i].name                = international_vault[original_indicator]['name']

#                 # Toggle YFinance flag if necessary
#                 if not FLAGS.NEED_YFINANCE:
#                     FLAGS.NEED_YFINANCE = True

#                 continue

#             fetch_types[i] = E_FetchType.TASE_HISTORICAL if is_historical else E_FetchType.TASE_FAST

#             if not FLAGS.NEED_HISTORICAL and fetch_types[i] == E_FetchType.TASE_HISTORICAL:
#                 FLAGS.NEED_HISTORICAL = True
#             elif not FLAGS.NEED_TASE_FAST and fetch_types[i] == E_FetchType.TASE_FAST:
#                 FLAGS.NEED_TASE_FAST = True
#         else:
#             fetch_types[i] = E_FetchType.YFINANCE

#             if not FLAGS.NEED_YFINANCE:
#                 FLAGS.NEED_YFINANCE = True

def get_TASE_url(indicator_type: E_IndicatorType, indicator: str) -> str | None:
    """
        Get the URL for a specific TASE indicator type.
    """

    if indicator_type == E_IndicatorType.TASE_MTF:
        return TASE_SEC_URLs.MTF(indicator)
    elif indicator_type == E_IndicatorType.TASE_ETF:
        return TASE_SEC_URLs.ETF(indicator)
    elif indicator_type == E_IndicatorType.TASE_SEC:
        return TASE_SEC_URLs.SECURITY(indicator)
    else:
        return None
