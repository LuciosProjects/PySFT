import json
from typing import Any

import pandas as pd

# ---- Package imports ----
from pysft.core.models import _fetchRequest
from pysft.core.fetcher_manager import fetcher_manager

def fetchData(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        # interval: str = "1d"
        ) -> pd.DataFrame:
    """
        Fetch financial data.
        Args:
            indicators (str | list[str]): Financial indicators to fetch.
            attributes (str | list[str], optional): Attributes of the fetched data. Defaults to "price".
            period (str | None, optional): Time period for the data. Defaults to None.
            start (str | None, optional): Start date for the data. Defaults to None.
            end (str | None, optional): End date for the data. Defaults to None.
            interval (str, optional): Data interval. Defaults to "1d".
        Returns:
            pd.DataFrame: DataFrame containing the fetched financial data.
    """

    # request = _fetchRequest(indicators, attributes, period, start, end, interval)
    request = _fetchRequest(indicators, attributes, period, start, end)
    
    manager = fetcher_manager(request)
    manager.managerRoutine()
    financial_data = manager.getResults()

    return financial_data

def fetch_data(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        # interval: str = "1d"
        ) -> pd.DataFrame:
    """
        PEP 8 alias for fetchData.
    """
    return fetchData(
        indicators=indicators,
        attributes=attributes,
        period=period,
        start=start,
        end=end,
        # interval=interval,
    )

def fetch_data_as_dict(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        # interval: str = "1d"
        ) -> dict:
    """
        PEP 8 alias for fetchData returning a dictionary.
    """
    data = fetchData(
        indicators=indicators,
        attributes=attributes,
        period=period,
        start=start,
        end=end,
        # interval=interval,
    )
    return _normalize_fetch_data(data)

def fetch_data_as_json(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        # interval: str = "1d"
        ) -> str:
    """
        PEP 8 alias for fetchData returning a JSON string.
    """
    data = fetch_data_as_dict(
        indicators=indicators,
        attributes=attributes,
        period=period,
        start=start,
        end=end,
        # interval=interval,
    )
    return json.dumps(data)


def _normalize_fetch_data(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Convert a DataFrame with (symbol, attribute) columns into a nested dict."""
    if not hasattr(frame, "columns"):
        raise TypeError("Expected a DataFrame-like object with columns")

    nested: dict[str, dict[str, Any]] = {}
    for column in frame.columns:
        if not isinstance(column, tuple) or len(column) != 2:
            raise ValueError("Expected DataFrame columns as (symbol, attribute)")
        symbol, attribute = column
        nested.setdefault(str(symbol), {})[str(attribute)] = frame[column].tolist()
    return nested