import json
from typing import Any, Literal

import pandas as pd

# ---- Package imports ----
from pysft.core.enums import E_FetchMode
from pysft.core.models import _fetchRequest
from pysft.core.fetcher_manager import fetcher_manager


def _resolve_mode(mode: Literal["all", "price", "info"]) -> E_FetchMode:
    """Map public mode literal to the internal enum representation."""

    try:
        return E_FetchMode(mode)
    except ValueError as exc:
        raise ValueError("Unsupported mode. Allowed values: 'all', 'price', 'info'.") from exc


def _mode_to_attributes(mode: E_FetchMode) -> list[str]:
    if mode == E_FetchMode.ALL:
        return ["all"]
    if mode == E_FetchMode.INFO:
        return ["info"]
    if mode == E_FetchMode.PRICE:
        # 'close' is represented by the canonical 'last' field in this package.
        return [ "price", "last", "open", "high", "low", "volume", "change_pct", "dates"]
    
    raise ValueError("Unsupported fetch mode.")

def fetchData(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        # interval: str = "1d"
        mode: Literal["all", "price", "info"] = "all",
        ) -> dict:
    """
        Fetch financial data.
        Args:
            indicators (str | list[str]): Financial indicators to fetch.
            attributes (str | list[str], optional): Attributes of the fetched data. Defaults to "price".
            period (str | None, optional): Time period for the data. Defaults to None.
            start (str | None, optional): Start date for the data. Defaults to None.
            end (str | None, optional): End date for the data. Defaults to None.
            mode (str, optional): Fetch mode — 'all', 'price', or 'info'. Defaults to 'all'.
        Returns:
            dict: Nested dict {indicator: {"dates": [...], attr: [...], ...}}.
    """

    fetch_mode = _resolve_mode(mode)
    attributes = _mode_to_attributes(fetch_mode)

    # request = _fetchRequest(indicators, attributes, period, start, end, interval)
    request = _fetchRequest(indicators, attributes, period, start, end, mode=fetch_mode)
    
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
    mode: Literal["all", "price", "info"] = "all",
        ) -> dict:
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
        mode=mode,
    )

def fetch_data_as_dict(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        # interval: str = "1d"
        mode: Literal["all", "price", "info"] = "all",
        ) -> dict:
    """
        Alias for fetchData returning a dictionary (fetchData now returns dict natively).
    """
    return fetchData(
        indicators=indicators,
        attributes=attributes,
        period=period,
        start=start,
        end=end,
        mode=mode,
    )

def fetch_data_as_json(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        # interval: str = "1d"
        mode: Literal["all", "price", "info"] = "all",
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
        mode=mode,
    )
    return json.dumps(data)


def fetchData_as_df(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        mode: Literal["all", "price", "info"] = "all",
        ) -> pd.DataFrame:
    """Fetch financial data and return as a MultiIndex (Indicator, Attribute) DataFrame."""
    return _dict_to_dataframe(fetchData(
        indicators=indicators,
        attributes=attributes,
        period=period,
        start=start,
        end=end,
        mode=mode,
    ))


def fetch_data_as_df(
        indicators: str | list[str],
        attributes: str | list[str] = "price",
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        mode: Literal["all", "price", "info"] = "all",
        ) -> pd.DataFrame:
    """PEP 8 alias for fetchData_as_df."""
    return fetchData_as_df(
        indicators=indicators,
        attributes=attributes,
        period=period,
        start=start,
        end=end,
        mode=mode,
    )


def _dict_to_dataframe(data: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Reconstruct a MultiIndex (Indicator, Attribute) DataFrame from a fetchData result dict."""
    if not data:
        return pd.DataFrame()

    frames = []
    for symbol, symbol_data in data.items():
        dates = pd.DatetimeIndex([pd.Timestamp(d) for d in (symbol_data.get("dates") or [])])
        attrs = {k: v for k, v in symbol_data.items() if k != "dates"}
        if dates.empty:
            dates = pd.DatetimeIndex([pd.Timestamp.today().normalize()])
        df = pd.DataFrame(attrs, index=dates)
        df.columns = pd.MultiIndex.from_product([[symbol], df.columns], names=["Indicator", "Attribute"])
        frames.append(df)

    return pd.concat(frames, axis=1) if frames else pd.DataFrame()