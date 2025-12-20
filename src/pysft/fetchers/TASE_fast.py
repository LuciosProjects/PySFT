# ---- Standard library imports ----

# ---- Package imports ----
import pysft.core.constants as const
from pysft.core.structures import indicatorRequest
import pysft.core.utilities as utils
import pysft.core.tase_specific_utils as tase_utils
from pysft.tools.logger import get_logger


logger = get_logger(__name__)

def fetch_TASE_fast(request: indicatorRequest):
    """
    Fetch data for the given indicator using TASE fast fetcher.
    
    This function performs a fast, single-point data fetch from TASE (Tel Aviv Stock Exchange)
    by scraping TheMarker website (finance.themarker.com). TheMarker URLs work for all TASE
    indicator types (MTF, ETF, Securities), making this a unified approach.

    Args:
        request (indicatorRequest): The request object containing indicator details.
    
    Returns:
        None: The function updates the request object in place with fetched data.
        
    Side Effects:
        - Updates request.data with fetched financial information
        - Sets request.success to True on successful fetch, False otherwise
        - Sets request.message with status/error information
    """
    
    indicator = request.indicator
    
    # Initialize request status
    request.success = False
    
    # Build TheMarker URL - works for all TASE indicator types
    url = tase_utils.TASE_SEC_URLs.THEMARKER(indicator)

    for attempt in range(const.MAX_ATTEMPTS):
        try: 
            # Fetch HTML content
            html_content = tase_utils._fetch_from_url(url)
    
            if html_content is None:
                request.message = f"{indicator} - Failed to fetch data from TheMarker after {const.MAX_ATTEMPTS} attempts"
                logger.error(request.message)
                
                request.message = utils.add_attempt2msg(request.message, attempt)
                continue
    
            # Parse the HTML content from TheMarker
            parsed_data = tase_utils._parse_themarker_data(html_content)
    
            if parsed_data is None:
                request.message = f"{indicator} - Failed to parse data from TheMarker"
                logger.error(request.message)

                request.message = utils.add_attempt2msg(request.message, attempt)
                continue
        except Exception as e:
            request.message = f"{indicator} - Exception during fetch/parse: {str(e)}"
            logger.error(request.message)

            request.message = utils.add_attempt2msg(request.message, attempt)
            continue
    
    # # Populate the request data structure
    # try:
    #     # Set currency based on indicator
    #     request.data.currency = tase_utils.determine_tase_currency(indicator)
        
    #     # Populate data fields from parsed data
    #     # For fast fetch, we expect single-point data (not time series)
    #     if 'date' in parsed_data:
    #         # Ensure date is converted to pd.Timestamp
    #         try:
    #             date_value = parsed_data['date']
    #             if isinstance(date_value, pd.Timestamp):
    #                 request.data.dates = date_value
    #             elif isinstance(date_value, str):
    #                 request.data.dates = pd.to_datetime(date_value)
    #             elif isinstance(date_value, list):
    #                 request.data.dates = [pd.to_datetime(d) for d in date_value]
    #         except Exception as e:
    #             logger.warning(f"Failed to convert date value: {e}. Using default date.")
    #         # If no valid date or conversion failed, keep the default from indicatorRequest initialization
        
    #     request.data.price = parsed_data.get('price', 0.0)
    #     # For single-point fast fetch, last price equals current price
    #     request.data.last = request.data.price
    #     request.data.open = parsed_data.get('open', 0.0)
    #     request.data.high = parsed_data.get('high', 0.0)
    #     request.data.low = parsed_data.get('low', 0.0)
    #     request.data.volume = parsed_data.get('volume', 0)
    #     request.data.name = parsed_data.get('name', '')
        
    #     # Calculate change percentage if we have both current and previous prices
    #     # Use the last field which should be scalar for single-point fast fetch
    #     prev_close = parsed_data.get('previous_close')
    #     if (prev_close is not None and 
    #         prev_close != 0 and  # Allow negative prices, just not zero
    #         request.data.last is not None and 
    #         request.data.last != 0 and
    #         not isinstance(request.data.last, list)):  # Ensure scalar value
    #         change_pct = ((request.data.last / prev_close) - 1.0) * 100.0
    #         request.data.change_pct = change_pct
        
    #     request.success = True
    #     request.message = f"{indicator} - Successfully fetched data from TASE"
    #     logger.info(request.message)
        
    # except Exception as e:
    #     request.message = f"{indicator} - Error populating data structure: {str(e)}"
    #     logger.error(request.message)
    #     request.success = False