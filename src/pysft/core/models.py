from typing import TYPE_CHECKING
import pandas as pd
from datetime import date
from dataclasses import dataclass

from pysft.core.io import _normalize_indicators, _parse_attributes, _resolve_range, _validate_interval
from pysft.core.structures import indicatorRequest, outputCls

# if TYPE_CHECKING:

# -----------------------------------------------
# ----------------- Dataclasses -----------------
# -----------------------------------------------
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
class _YF_fetchReq_Container(outputCls):
    requests: list['indicatorRequest']

    start_date: date            = date.today()
    end_date: date              = date.today()

    success: bool               = False
    message: str                = ""

    def __init__(self, requests: list['indicatorRequest'], dates: pd.Timestamp | list[pd.Timestamp] | None = None):
        self.requests = requests

        if dates:
            self.start_date         = dates[0].date() if isinstance(dates, list) else dates.date()
            self.end_date           = dates[-1].date() if isinstance(dates, list) else dates.date()

# -----------------------------------------------
# ------------------- Classes -------------------
# -----------------------------------------------    
class fetcher_settings:
    def __init__(self, request: '_fetchRequest'):
        self.NEED_TASE_FAST:    bool = False
        self.NEED_HISTORICAL:   bool = False
        self.NEED_YFINANCE:     bool = False

        self.data_length:       int = 0
        ''' Length of the fetched data (number of rows), how many datapoints to fetch for each indicator '''

        self.start_date:        date = date.today()
        ''' Start date for the data fetch '''
        self.end_date:          date = date.today()
        ''' End date for the data fetch '''

        self.indicators_count:  int = len(request.indicators)
        ''' Number of indicators to fetch '''

        if request.start_ts and request.end_ts :
            self.start_date = request.start_ts.date()
            self.end_date   = request.end_ts.date()

            delta = request.end_ts - request.start_ts
            self.data_length = delta.days + 1  # inclusive of both start and end
        else:
            # Assume request is for today only
            self.data_length = 1  # point-in-time request
