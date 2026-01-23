from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from pandas.core.series import Series

import yfinance as yf

# from datetime import date
from datetime import timedelta

# ---- Package imports ----
import pysft.core.constants as const
import pysft.core.utilities as utils
import pysft.core.yf_specific_utils as yf_utils
from pysft.core.structures import indicatorRequest

from pysft.tools.logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from pysft.core.models import _YF_fetchReq_Container

def fetch_yfinance(container: '_YF_fetchReq_Container'):
    """
    Fetch data for the given indicator using yfinance.

    Args:
        request (indicatorRequest): The request object containing indicator details.
    Returns:
        None: The function updates the request object in place.
    """

    # Parse the target dates
    try:
        target_dates = pd.to_datetime([pd.Timestamp(d) for d in pd.date_range(start=container.start_date, end=container.end_date)],format=const.YFINANCE_DATE_FORMAT)
    except Exception as e:
        message = f"Could not parse date range: {str(e)}"
        container.message = message
        container.success = False

        logger.error(container.message)
        return

    for request in container.requests:
        request.success = False  # Placeholder for actual success status

    remaining_requests = [req for req in container.requests if not req.success]

    for attempt in range(const.MAX_YF_ATTEMPTS):
        if not remaining_requests:
            break  # All requests have been processed

        # Get tickers for remaining requests
        remaining_tickers = [req.indicator for req in remaining_requests]
        N_tckrs = len(remaining_tickers)

        try:
            # Create Tickers object for remaining tickers
            tckrs = yf.Tickers(remaining_tickers).tickers
        except Exception as e:
            # Handle exception for Tickers creation
            message = f"Failed to create Ticker objects: {str(e)}"
            container.message = message
            container.message = utils.add_attempt2msg(message, attempt)
            container.success = False

            logger.warning(container.message)
            continue

        try:
            # Try to get data around the target date (look back and forward)
            # Note: the date spans for all requests are assumed to be the same
            start_date = container.start_date - timedelta(days=const.INITIAL_DAYS_HALF_SPAN + attempt*const.HALF_SPAN_INCREMENT)
            end_date = container.end_date + timedelta(days=const.INITIAL_DAYS_HALF_SPAN + attempt*const.HALF_SPAN_INCREMENT)

            response = yf.download(
                remaining_tickers, 
                start=start_date.strftime(const.YFINANCE_DATE_FORMAT), 
                end=end_date.strftime(const.YFINANCE_DATE_FORMAT),
                ignore_tz=True,
                progress=False,  # Suppress progress bar
                timeout=int(const.YF_API_CALL_TIMEOUT.seconds()) * N_tckrs,
                auto_adjust=True,  # Explicitly set to avoid warnings
                threads=True  # Enable multithreading for better performance
            )

            if response is None or response.empty:
                container.message = utils.add_attempt2msg("No data returned from yfinance", attempt)
                container.success = False

                logger.warning(container.message)
                continue  # Try next attempt

            if not all(col in response for col in const.YF_REQUIRED_DATAFRAME_COLUMNS):
                container.message = utils.add_attempt2msg("Incomplete data returned from yfinance", attempt)
                container.success = False

                logger.warning(container.message)
                continue  # Try next attempt
            
            # Get all indicators names from response
            allSymbols = response["Close"].columns.tolist()

            for symbol in allSymbols:
                data = response.xs(symbol, level=1, axis=1)

                if isinstance(data, Series):
                    data = data.to_frame()
                
                matched_request = None
                for req in remaining_requests:
                    if req.indicator == symbol:
                        matched_request = req
                        break

                if matched_request is None:
                    continue

                # Try to find data for target dates
                closest_dates = yf_utils.find_closest_date(data["Close"], target_dates)

                if closest_dates is not None:
                    # Successfully found data for target dates (TEMPORARILY COMMENTED OUT IN ORDER TO TEST INCEPTION DATE ONLY)
                    process_successful_request(matched_request, data, closest_dates, tckrs[symbol])
                else:
                    # No data for target dates - try inception date approach
                    try_inception_date(matched_request, tckrs[symbol])

            remaining_requests = [req for req in container.requests if not req.success]

        except Exception as e:
            # Log the error and continue to next attempt
            container.message = utils.add_attempt2msg(f"Error during data fetch: {str(e)}", attempt)
            container.success = False

            logger.warning(container.message)
            continue

    if remaining_requests:
        container.message = "YFinance fetch completed with some failures."
        container.success = False
    else:
        container.message = "YFinance fetch completed successfully."
        container.success = True
        
    logger.info(container.message)
    # print("breakpoint")
        
def process_successful_request(request: indicatorRequest, data: pd.DataFrame, closest_dates: pd.DatetimeIndex, tckr: yf.Ticker):
    """Process a request that has valid data."""

    valid_data = data.dropna(how='any') # Drop rows where data is NaN

    dates = utils.safe_extract_date_ts(closest_dates)
    request.data.dates = dates

    request.data.price  = yf_utils.safe_extract_value_float(valid_data["Close"][closest_dates])
    request.data.open   = yf_utils.safe_extract_value_float(valid_data["Open"][closest_dates])
    request.data.high   = yf_utils.safe_extract_value_float(valid_data["High"][closest_dates])
    request.data.low    = yf_utils.safe_extract_value_float(valid_data["Low"][closest_dates])
    request.data.volume = yf_utils.safe_extract_value_int(valid_data["Volume"][closest_dates])

    request.data.last = request.data.price[-1] if isinstance(request.data.price, list) else request.data.price # Most recent closing price
    i_start = np.argmin(np.abs(valid_data.index.to_numpy() - closest_dates[0].to_numpy()))
    i_end   = np.argmin(np.abs(valid_data.index.to_numpy() - closest_dates[-1].to_numpy()))

    if request.data.dates.__len__() > 1:
        request.data.change_pct = [((valid_data["Close"][valid_data.index[i_ts]] / valid_data["Close"][valid_data.index[i_ts-1]]) - 1.0)*100.0 for i_ts in range(i_start, i_end+1)]
    else:
        # Try to aquire change_pct from close/open of the same day
        request.data.change_pct = (request.data.price/request.data.open - 1.0) * 100.0

    # Extract additional info data
    yf_utils.extract_info_data(request, tckr)


def try_inception_date(request: indicatorRequest, tckr: yf.Ticker):
    """ Try to get the inception date (first available data) for a symbol.
        inception data returns a single date data point.
    """

    try:
        history = tckr.history(period="max", auto_adjust=True)

        if history is None or history.empty:
            request.message = "No historical data available from inception date."
            request.success = False
            return
        else:
            inception_date = history.index[0]

            request.data.dates = history.index[0]
            request.data.price = float(history['Close'].iloc[0])
            request.data.open  = float(history['Open'].iloc[0])
            request.data.high  = float(history['High'].iloc[0])
            request.data.low   = float(history['Low'].iloc[0])
            request.data.volume= int(history['Volume'].iloc[0])

            request.data.last = request.data.price

            # Extract additional info data
            yf_utils.extract_info_data(request, tckr)

            temp = request.message
            request.message = f"{request.indicator} - Data fetched from inception date {inception_date.date()}, {temp.replace(request.indicator + ' - ', '')} (yfinance)."

            request.fromInception   = True
            request.success         = True

    except Exception as e:
        request.message = f"Failed to extract data from inception date: {str(e)}."

        logger.error(request.message)