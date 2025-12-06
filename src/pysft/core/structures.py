from dataclasses import dataclass
import pandas as pd

@dataclass
class _indicator_data:
    """
        Dataclass to hold fetched indicator data.
    """
    indicator: str = ""
    name: str = ""
    date: pd.Timestamp | list[pd.Timestamp] = pd.Timestamp(0)
    currency: str = ""
    price: float | list[float] = 0.0
    last: float | list[float] = 0.0
    open: float | list[float] = 0.0
    high: float | list[float] = 0.0
    low: float | list[float] = 0.0
    volume: float | list[float] = 0
    change_pct: float | list[float] = 0.0 
    market_cap: float | list[float] = 0.0

@dataclass
class indicatorRequest:
    """
        Dataclass to represent a request for a specific indicator's data.
    """
    
    data: _indicator_data
    indicator: str = ""
    original_indicator: str = ""
    success: bool = False
    message: str = ""

    def __init__(self, indicator: str):
        self.indicator          = indicator
        self.original_indicator = indicator
        self.data               = _indicator_data(indicator=indicator)