from typing import cast as _cast

import numpy as np
import pandas as pd

# [Replit Agent] Removed the unused Any typing import.
import yfinance as yf
from pandas.core.series import Series

# ---- Package imports ----
import pysft.core.constants as const
import pysft.core.tase_specific_utils as tase_utils
import pysft.core.utilities as utils
from pysft.core.enums import E_FetchMode
from pysft.core.structures import indicatorRequest
from pysft.tools.logger import get_logger

logger = get_logger(__name__)


def extract_ticker_surface_metadata(ticker: yf.Ticker) -> dict[str, str]:
    """Extract normalized, surface-level metadata from a yfinance ticker."""

    info = ticker.info or {}
    if not isinstance(info, dict):
        info = {}

    return {
        "isin": str(getattr(ticker, "isin", "") or "").strip().upper(),
        "quote_type": str(info.get("quoteType", "") or "").strip().upper(),
        "exchange": str(info.get("exchange", "") or "").strip().upper(),
        "currency": str(info.get("financialCurrency", "") or info.get("currency", "") or "").strip().upper(),
        "name": str(info.get("longName", "") or info.get("shortName", "") or "").strip(),
        "cusip": str(info.get("cusip", "") or "").strip().upper(),
    }


def resolve_ticker_surface_metadata(indicator: str) -> dict[str, str] | None:
    """Resolve normalized ticker metadata by symbol, returning None when empty."""

    metadata = extract_ticker_surface_metadata(yf.Ticker(indicator))
    if not any(metadata.values()):
        return None
    return metadata

def find_closest_date(data_frame: Series, target_dates: pd.DatetimeIndex) -> pd.DatetimeIndex | None:
    """
    Find the closest available date in the dataframe to the target date.
    
    Args:
        data_frame (pd.DataFrame): DataFrame with date index
        target_dates (pd.DatetimeIndex): Target dates to find closest matches for
        
    Returns:
        pd.DatetimeIndex or None: Closest available dates or None if no valid data
    """

    if data_frame.empty:
        return None
    
    # Filter out rows with all NaN values
    valid_data = data_frame.dropna(how='all')
    
    if valid_data.empty:
        return None
    
    # Find the closest date for each symbol
    # First try to find exact match
    dates = valid_data.index

    closest_dates = []
    for td in target_dates:
        closest_idx = np.argmin(np.abs(dates.values - td.to_datetime64()))
        closest_dates.append(dates.values[closest_idx])

    unique_dates, _ = utils.unique(closest_dates)

    return pd.DatetimeIndex(unique_dates)

def safe_extract_value_float(data: pd.DataFrame | Series) -> float | list[float]:
    """Safely extract value from pandas data, handling various formats"""

    try:
        values = np.asarray(data.to_numpy(), dtype=np.float64).reshape(-1)

        if values.size == 0:
            return []

        # Check if value is NaN
        if np.isnan(values).any():
            # No need to dig out the NaN values since they were already dealt with in the "find_closest_date" subroutine
            return []

        # Return the extracted value cast to appropriate type
        return [float(v) for v in values] if values.size > 1 else float(values.item())
    except (TypeError, ValueError):
        return []
    
def safe_extract_value_int(data: pd.DataFrame | Series) -> int | list[int]:
    """Safely extract value from pandas data, handling various formats"""

    try:
        values = np.asarray(data.to_numpy(), dtype=np.float64).reshape(-1)
        if not values.size or not np.isfinite(values).all():
            return []
        return [int(value) for value in values] if values.size > 1 else int(values.item())
    except (TypeError, ValueError, OverflowError):
        return []
    
def extract_info_data(request: indicatorRequest, ticker: yf.Ticker, fetch_inception_history: bool = True):
    """
    Extract additional info data from yfinance Ticker object and populate request data fields.
    """

    metadata = extract_ticker_surface_metadata(ticker)
    request.data.ISIN = (metadata["isin"] if not request.is_tase_indicator else request.data.ISIN) if request.data.ISIN == "" else request.data.ISIN
    try:
        info = ticker.info

        request.data.quoteType = metadata["quote_type"] or info.get("quoteType", "")

        # request.data.briefSummary = info.get("longBusinessSummary", "")
        if fetch_inception_history:
            history = ticker.history(period="max", auto_adjust=True)
            if history is not None and not history.empty:
                request.data.inceptionDate = history.index[0].tz_localize(None)

        if request.data.name == "": # Only update name if not already set
            request.data.name = metadata["name"] or info.get("longName", "")
        request.data.currency = metadata["currency"] or info.get("currency", info.get("financialCurrency", ""))

        request.data.exchange = metadata["exchange"] or info.get("exchange", "")
    

        if request.data.currency == "ILA" or request.data.currency == "ILS":
            request.data.indicator = request.original_indicator # Keep original indicator for ILS securities (TASE)
            if not tase_utils.get_Bizportal_expense_rate(request.data):
                request.data._present_fields.discard("expense_rate")
            
            # Revert indicator to its YF format
            request.data.indicator = request.indicator

        else:
            if info.get("netExpenseRatio") is not None:
                request.data.expense_rate = info["netExpenseRatio"]

        if info.get("averageDailyVolume3Month") is not None:
            request.data.avgDailyVolume3mnth = info["averageDailyVolume3Month"]

        if request.data.quoteType in ["ETF", "MTF"]:
            if info.get("totalAssets") is not None:
                request.data.market_cap = info["totalAssets"]
        elif request.data.quoteType in ["EQUITY"]:
            if info.get("marketCap") is not None:
                request.data.market_cap = info["marketCap"]
                
        if info.get("yield") is not None:
            request.data.dividendYield = info["yield"] * 100
        elif info.get("dividendYield") is not None:
            request.data.dividendYield = info["dividendYield"]
        for field in ("trailingPE", "forwardPE", "beta"):
            value = info.get(field, info.get("beta3Year") if field == "beta" else None)
            if value is not None:
                setattr(request.data, field, value)

    except Exception as e:
        request.message = f"Failed to extract additional info data: {e!s}."
        request.success = False

        logger.error(request.message)

    # Factor price and other values according to currency
    if request.mode != E_FetchMode.INFO and request.data.price is not None:
        # Convert price according to currency factor (this is not currency conversion! just adjustment)

        # try:
            currency_normalization = const.CURRENCY_NORMALIZATION.get(request.data.currency, {"factor": 1, "alias": request.data.currency})

            # Closing price
            if isinstance(request.data.price, float):
                request.data.price *= currency_normalization["factor"]
            elif isinstance(request.data.price, (list, np.ndarray)):
                request.data.price = [p * currency_normalization["factor"] for p in request.data.price]
            
            # Last price
            # Preserve the existing in-place operation; the provider supplies
            # a scalar last price, although the shared model also permits lists.
            last_price = _cast(float, request.data.last)
            last_price *= currency_normalization["factor"]
            request.data.last = last_price

            # Open price
            if isinstance(request.data.open, float):
                request.data.open *= currency_normalization["factor"]
            elif isinstance(request.data.open, (list, np.ndarray)):
                request.data.open  = [o * currency_normalization["factor"] for o in request.data.open]

            # High price
            if isinstance(request.data.high, float):
                request.data.high *= currency_normalization["factor"]
            elif isinstance(request.data.high, (list, np.ndarray)):
                request.data.high  = [h * currency_normalization["factor"] for h in request.data.high]
            
            # Low price
            if isinstance(request.data.low, float):
                request.data.low  *= currency_normalization["factor"]
            elif isinstance(request.data.low, (list, np.ndarray)):
                # [Replit Agent] Rename the ambiguous loop variable; scaling is unchanged.
                request.data.low   = [low * currency_normalization["factor"] for low in request.data.low]

            # Put currency alias
            request.data.currency = currency_normalization["alias"]
        # except KeyError:
        #     # If currency not found in aliases, keep original
        #     request.message += f"Unknown currency '{request.data.currency}', keeping original."
        #     request.success = False

        #     logger.warning(request.message)
    
    if request.data.quoteType == "EQUITY":
        # Set quote type to STOCK for consistency
        request.data.quoteType = "STOCK"

    if request.message == '':
        request.message = f"{request.indicator} - Data fetch from yfinance successful."
        request.success = True

        logger.info(request.message)
