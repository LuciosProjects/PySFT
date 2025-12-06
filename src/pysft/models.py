import pandas as pd

from dataclasses import dataclass

from pysft.data.io import _normalize_indicators, _parse_attributes, _resolve_range, _validate_interval

# -----------------------------------------------
# ----------------- Dataclasses -----------------
# -----------------------------------------------
@dataclass
class fetcher_settings:
    NEED_TASE_FAST: bool = False
    NEED_HISTORICAL: bool = False
    NEED_YFINANCE: bool = False

    data_length: int = 0
    ''' Length of the fetched data (number of rows), how many datapoints to fetch for each indicator '''
    indicators_count: int = 0

    def __init__(self, request: '_fetchRequest'):
        self.indicators_count = len(request.indicators)

        if request.start_ts and request.end_ts :
            delta = request.end_ts - request.start_ts
            self.data_length = delta.days + 1  # inclusive of both start and end
        else:
            self.data_length = 1  # point-in-time request

@dataclass
class _fetchRequest:
    indicators: list[str]
    attributes: list[str]
    start_ts: pd.Timestamp | None
    end_ts: pd.Timestamp | None
    interval: str

    def __init__(self,
                 indicators: str | list[str],
                 attributes: str | list[str],
                 period: str | None,
                 start_ts: str | None,
                 end_ts: str | None,
                 interval: str):
        
        self.indicators             = _normalize_indicators(indicators)
        self.attributes             = _parse_attributes(attributes)
        self.start_ts, self.end_ts  = _resolve_range(period, start_ts, end_ts)
        self.interval               = _validate_interval(interval)

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
class TASE_SEC_URLs:
    MTF = lambda indicator: f"https://maya.tase.co.il/en/funds/mutual-funds/{indicator}/historical-data?period=3" # Base URL for TASE MTF historical data page (5 years)
    ETF = lambda indicator: f"https://market.tase.co.il/en/market_data/etf/{indicator}/historical_data/eod?pType=7&oId={indicator}" # Base URL for TASE ETF historical data page (5 years)
    SECURITY = lambda indicator: f"https://market.tase.co.il/en/market_data/security/{indicator}/historical_data/eod?pType=7&oId=0{indicator}" # Base URL for TASE Security historical data page (5 years)
    THEMARKER = lambda indicator: f"https://finance.themarker.com/etf/{indicator}" # Base URL for TheMarker


# -----------------------------------------------
# ------------------- Classes -------------------
# -----------------------------------------------
class CTimeout:
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