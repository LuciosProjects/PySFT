"""
    Core data structures used in PySFT.
    This module defines the primary data structures utilized throughout the PySFT that don't rely on other project's modules.    
"""

from dataclasses import dataclass, field
import pandas as pd
from datetime import date as Date

class outputCls:
    """
    This class is a base for all output representations.
    """

    def __init__(self):
        pass

@dataclass
class _indicator_data:
    """
        Dataclass to hold fetched indicator data.
    """
    indicator: str = ""
    name: str = "" 
    ''' Full name of the indicator (company/security/fund/etc.)'''
    ISIN: str = ""
    ''' International Securities Identification Number'''
    # briefSummary: str = ""
    # ''' Brief information or description about the indicator'''
    inceptionDate: pd.Timestamp | None = None
    ''' Date when the indicator was first issued or became available'''
    quoteType: str = ""
    ''' Type of quote (e.g., equity, mutual fund, exchange traded fund, etc.)'''
    dates: list[pd.Timestamp] = field(default_factory=lambda: [pd.Timestamp(Date.today())])
    ''' Dates corresponding to the fetched data points.'''
    currency: str = ""
    ''' Currency code (e.g., 'USD', 'EUR', 'ILS')'''
    price: float | list[float] = 0.0 
    ''' fetched price data'''
    expense_rate: float = 0.0 
    ''' Annual expense rate as a percentage (range is 0.0 to 1.0)'''
    last: float | list[float] = 0.0
    ''' Last traded price per timestamp'''
    open: float | list[float] = 0.0
    ''' Opening price per timestamp'''
    high: float | list[float] = 0.0
    ''' Highest price per timestamp'''
    low: float | list[float] = 0.0
    ''' Lowest price per timestamp'''
    volume: int | list[int] = 0
    ''' Trading volume per timestamp'''
    avgDailyVolume3mnth: int = 0
    ''' Average daily volume over the past 3 months'''
    change_pct: float | list[float] = 0.0 
    ''' Percentage change in price per timestamp'''
    market_cap: float | list[float] = 0.0
    ''' Market capitalization per timestamp'''
    # ebitda: float = 0.0
    # ''' Earnings Before Interest, Taxes, Depreciation, and Amortization'''
    dividendYield: float = 0.0
    ''' Dividend yield as a percentage'''
    trailingPE: float = 0.0
    ''' Trailing Price-to-Earnings ratio'''
    forwardPE: float = 0.0
    ''' Forward Price-to-Earnings ratio (if available)'''
    beta: float = 0.0
    ''' Beta value indicating volatility compared to the market'''
    # sharpeRatio: float = 0.0
    # ''' Sharpe Ratio indicating risk-adjusted return'''

@dataclass
class indicatorRequest(outputCls):
    """
        Dataclass to represent a request for a specific indicator's data.
    """
    
    data: _indicator_data

    indicator: str              = ""
    original_indicator: str     = ""

    start_date: Date            = Date.today()
    end_date: Date              = Date.today()

    success: bool               = False
    fromInception: bool         = False
    message: str                = ""

    is_tase_indicator: bool     = False

    def __init__(self, indicator: str, dates: list[pd.Timestamp] | None = None):
        self.indicator          = indicator
        self.original_indicator = indicator
        self.data               = _indicator_data(indicator=indicator, dates=dates) if dates else _indicator_data(indicator=indicator)

        if dates:
            self.start_date         = dates[0].date() if isinstance(dates, list) else dates.date()
            self.end_date           = dates[-1].date() if isinstance(dates, list) else dates.date()

class CTimeRepr:
    def __init__(self, timeout: float):
        """
        Class to handle browser timeout settings.
        
        Args:
            timeout (float): Timeout duration in seconds.
        """
        self.timeout: float = timeout
    
    def seconds(self) -> float:
        return self.timeout
    def milliseconds(self) -> float:
        return self.timeout * 1e3