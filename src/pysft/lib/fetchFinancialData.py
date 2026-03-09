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
    """Convert a DataFrame with (symbol, attribute) columns into a nested dict with cleaned dates.
    
    Each symbol gets its own date vector containing only dates with valid data for that symbol.
    NaN values are removed from both dates and value arrays.
    """
    if not hasattr(frame, "columns"):
        raise TypeError("Expected a DataFrame-like object with columns")

    nested: dict[str, dict[str, Any]] = {}
    
    # Group columns by symbol
    symbols = set()
    attributes = set() # multiple symbols contain the same attributes per fetching session, so we can extract them from any symbol's columns, for a single symbol it's trivial
    for column in frame.columns:
        if not isinstance(column, tuple) or len(column) != 2:
            raise ValueError("Expected DataFrame columns as (symbol, attribute)")
        symbol, attr = column
        symbols.add(symbol)
        attributes.add(attr)
    
    # Convert sets to lists for consistent ordering (optional)
    symbols = list(symbols)
    attributes = list(attributes)

    # Process each symbol independently
    for symbol in symbols:
        symbol_df = frame[symbol]
        
        # Find dates with at least one valid value for this symbol
        valid_mask = symbol_df.notna().any(axis=1)
        valid_dates = frame.index[valid_mask]
        
        # Build date strings (format as YYYY-MM-DD)
        date_strings = []
        for ts in valid_dates:
            if hasattr(ts, 'date'):
                date_strings.append(str(ts.date()))
            else:
                date_strings.append(str(ts))
        
        nested[str(symbol)] = {"dates": date_strings}
        
        # Add attribute values aligned to valid dates
        for attr in attributes:
            # Extract values for valid dates only (preserves order and index alignment)
            values = symbol_df[attr].loc[valid_dates].tolist()
            nested[str(symbol)][str(attr)] = values if values else None
    
    return nested