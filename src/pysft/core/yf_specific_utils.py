import numpy as np
import pandas as pd
from pandas.core.series import Series

import yfinance as yf

# ---- Package imports ----
import pysft.core.constants as const
from pysft.core.structures import indicatorRequest

import pysft.core.tase_specific_utils as tase_utils
import pysft.core.utilities as utils

from pysft.tools.logger import get_logger

logger = get_logger(__name__)

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
        if hasattr(data, 'values'):
            values = data.values
        else:
            return 0.0
        
        # Check if value is NaN
        if pd.isna(values).any():
            # No need to dig out the NaN values since they were already dealt with in the "find_closest_date" subroutine
            # Return zero of appropriate type
            return 0.0
        
        # Return the extracted value cast to appropriate type
        return values.tolist() if len(values) > 1 else float(values[0])
    except:
        # In case of any error, return zero of appropriate type
        return 0.0
    
def safe_extract_value_int(data: pd.DataFrame | Series) -> int | list[int]:
    """Safely extract value from pandas data, handling various formats"""

    dtype = data.values.dtype
    try:
        if hasattr(data, 'values'):
            values = data.values
        else:
            return dtype.type(0)
        
        # Check if value is NaN
        if pd.isna(values).any():
            # No need to dig out the NaN values since they were already dealt with in the "find_closest_date" subroutine
            # Return zero of appropriate type
            return dtype.type(0)
        
        # Return the extracted value cast to appropriate type
        return dtype.type(values)
    except:
        # In case of any error, return zero of appropriate type
        return dtype.type(0)
    
def extract_info_data(request: indicatorRequest, ticker: yf.Ticker):
    """
    Extract additional info data from yfinance Ticker object and populate request data fields.
    """

    request.data.ISIN = ((ticker.isin if ticker.isin else "") if not request.is_tase_indicator else request.data.ISIN) if request.data.ISIN == "" else request.data.ISIN
    try:
        info = ticker.info

        request.data.quoteType = info.get("quoteType", "N/A")

        # request.data.briefSummary = info.get("longBusinessSummary", "")
        history = ticker.history(period="max", auto_adjust=True)
        if history is not None and not history.empty:
            request.data.inceptionDate = history.index[0].tz_localize(None)

        if request.data.name == "": # Only update name if not already set
            request.data.name = info.get("longName", str(request.indicator))
        request.data.currency = info.get("currency", info.get("financialCurrency", "USD"))

        if request.data.currency == "ILA" or request.data.currency == "ILS":
            request.data.indicator = request.original_indicator # Keep original indicator for ILS securities (TASE)
            if not tase_utils.get_Bizportal_expense_rate(request.data):
                request.data.expense_rate = 0.0 # If failed to get expense rate from TASE Bizportal, set to 0.0
            
            # Revert indicator to its YF format
            request.data.indicator = request.indicator

        else:
            request.data.expense_rate = info.get("netExpenseRatio", 0.0)

        request.data.avgDailyVolume3mnth    = info.get("averageDailyVolume3Month", 0)

        if request.data.quoteType in ["ETF", "MTF"]:
            request.data.market_cap = info.get("totalAssets", 0.0)
        elif request.data.quoteType in ["EQUITY"]:
            request.data.market_cap = info.get("marketCap", 0.0)
                
        request.data.dividendYield  = info.get("yield", info.get("dividendYield", 0.0)*0.01)*100 # Convert to percentage
        request.data.trailingPE     = info.get("trailingPE", 0.0)
        request.data.forwardPE      = info.get("forwardPE", 0.0)
        request.data.beta           = info.get("beta", info.get('beta3Year', 0.0))

    except Exception as e:
        request.message = f"Failed to extract additional info data: {str(e)}."
        request.success = False

        logger.error(request.message)

    # Factor price and other values according to currency
    if request.data.price is not None:
        # Convert price according to currency factor (this is not currency conversion! just adjustment)

        try:
            # Closing price
            if isinstance(request.data.price, float):
                request.data.price *= const.CURRENCY_NORMALIZATION[request.data.currency]["factor"]
            elif isinstance(request.data.price, list) or isinstance(request.data.price, np.ndarray):
                request.data.price = [p * const.CURRENCY_NORMALIZATION[request.data.currency]["factor"] for p in request.data.price]
            
            # Last price
            request.data.last *= const.CURRENCY_NORMALIZATION[request.data.currency]["factor"]

            # Open price
            if isinstance(request.data.open, float):
                request.data.open *= const.CURRENCY_NORMALIZATION[request.data.currency]["factor"]
            elif isinstance(request.data.open, list) or isinstance(request.data.open, np.ndarray):
                request.data.open  = [o * const.CURRENCY_NORMALIZATION[request.data.currency]["factor"] for o in request.data.open]

            # High price
            if isinstance(request.data.high, float):
                request.data.high *= const.CURRENCY_NORMALIZATION[request.data.currency]["factor"]
            elif isinstance(request.data.high, list) or isinstance(request.data.high, np.ndarray):
                request.data.high  = [h * const.CURRENCY_NORMALIZATION[request.data.currency]["factor"] for h in request.data.high]
            
            # Low price
            if isinstance(request.data.low, float):
                request.data.low  *= const.CURRENCY_NORMALIZATION[request.data.currency]["factor"]
            elif isinstance(request.data.low, list) or isinstance(request.data.low, np.ndarray):
                request.data.low   = [l * const.CURRENCY_NORMALIZATION[request.data.currency]["factor"] for l in request.data.low]

            # Put currency alias
            request.data.currency = const.CURRENCY_NORMALIZATION[request.data.currency]["alias"]
        except KeyError:
            # If currency not found in aliases, keep original
            request.message += f"Unknown currency '{request.data.currency}', keeping original."
            request.success = False

            logger.warning(request.message)
    
    if request.data.quoteType == "EQUITY":
        # Set quote type to STOCK for consistency
        request.data.quoteType = "STOCK"

    if request.message == '':
        request.message = f"{request.indicator} - Data fetch from yfinance successful."
        request.success = True

        logger.info(request.message)
