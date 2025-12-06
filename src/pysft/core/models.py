import pandas as pd
from datetime import date
from dataclasses import dataclass

from pysft.core.io import _normalize_indicators, _parse_attributes, _resolve_range, _validate_interval

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
    ''' Number of indicators to fetch '''

    start_date: date = date.today()
    ''' Start date for the data fetch '''
    end_date: date = date.today()
    ''' End date for the data fetch '''

    def __init__(self, request: '_fetchRequest'):
        self.indicators_count = len(request.indicators)

        if request.start_ts and request.end_ts :
            self.start_date = request.start_ts.date()
            self.end_date   = request.end_ts.date()

            delta = request.end_ts - request.start_ts
            self.data_length = delta.days + 1  # inclusive of both start and end
        else:
            # Assume request is for today only
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