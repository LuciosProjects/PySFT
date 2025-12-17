from .fetch_yfinance import fetch_yfinance
from .TASE_fast import fetch_TASE_fast
# from .TASE_historical import fetch_TASE_historical

__all__ = [
    "fetch_yfinance",       # yfinance fetcher
    "fetch_TASE_fast",      # TASE fast fetcher
    # "fetch_TASE_historical", # TASE historical fetcher
]