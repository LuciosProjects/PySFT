
# ---- Standard library imports ----
from typing import Optional
from datetime import datetime
import time

# ---- Third-party imports ----
import requests
from bs4 import BeautifulSoup
import pandas as pd

# ---- Package imports ----
import pysft.core.constants as const
from pysft.core.structures import indicatorRequest
from pysft.core.tase_specific_utils import TASE_SEC_URLs, determine_tase_currency
from pysft.tools.logger import get_logger

logger = get_logger(__name__)


def _fetch_from_url(url: str, timeout: int = 10) -> Optional[str]:
    """
    Fetch HTML content from a URL with retries.
    
    Args:
        url (str): The URL to fetch
        timeout (int): Request timeout in seconds
    
    Returns:
        Optional[str]: HTML content if successful, None otherwise
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{const.MAX_ATTEMPTS} failed for {url}: {str(e)}")
            if attempt < const.MAX_ATTEMPTS - 1:
                time.sleep(1)  # Brief pause before retry
            continue
    
    return None


def _parse_themarker_data(html_content: str) -> Optional[dict]:
    """
    Parse TheMarker HTML content to extract financial data.
    
    Args:
        html_content (str): HTML content from TheMarker website (finance.themarker.com)
    
    Returns:
        Optional[dict]: Dictionary containing parsed financial data, or None if parsing fails
        
    Note:
        This is a placeholder implementation. The actual HTML parsing logic needs to be
        implemented based on the specific structure of TheMarker website.
        
        TheMarker URLs work for all TASE indicator types (MTF, ETF, Securities), making
        indicator type identification unnecessary.
        
        Implementation steps:
            1. Inspect actual HTML from finance.themarker.com/etf/{indicator} URLs
            2. Identify CSS classes, IDs, or XPath selectors for data elements
            3. Use BeautifulSoup methods (find, find_all, select) to extract data
            4. Extract fields like:
               - Name/title of the security
               - Current price/last price
               - Open, High, Low prices
               - Trading volume
               - Date of the data
               - Previous close (for change calculation)
            5. Handle variations in HTML structure (missing data, different layouts)
            6. Convert extracted strings to appropriate types (float, int, datetime)
    """
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        data = {}
        
        # TODO: Implement actual HTML parsing based on TheMarker website structure
        # Example structure (to be adjusted based on actual HTML):
        #
        # data['name'] = soup.find('h1', class_='security-name').text.strip()
        # price_elem = soup.find('span', class_='last-price')
        # data['price'] = float(price_elem.text.strip()) if price_elem else 0.0
        # data['date'] = pd.to_datetime(soup.find('span', class_='date').text.strip())
        # data['volume'] = int(soup.find('td', class_='volume').text.strip().replace(',', ''))
        # # ... extract other fields
        
        # For now, return None to indicate parsing needs implementation
        logger.warning("TheMarker HTML parsing not yet implemented for website structure")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing TheMarker HTML content: {str(e)}")
        return None


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
    logger.info(f"Starting TASE fast fetch for indicator: {indicator}")
    
    # Initialize request status
    request.success = False
    request.message = f"{indicator} - Starting TASE fast fetch"
    
    # Build TheMarker URL - works for all TASE indicator types
    url = TASE_SEC_URLs.THEMARKER(indicator)
    
    logger.info(f"Fetching data from TheMarker URL: {url}")
    
    # Fetch HTML content
    html_content = _fetch_from_url(url)
    
    if html_content is None:
        request.message = f"{indicator} - Failed to fetch data from TheMarker after {const.MAX_ATTEMPTS} attempts"
        logger.error(request.message)
        return
    
    # Parse the HTML content from TheMarker
    parsed_data = _parse_themarker_data(html_content)
    
    if parsed_data is None:
        request.message = f"{indicator} - Failed to parse data from TheMarker"
        logger.error(request.message)
        return
    
    # Populate the request data structure
    try:
        # Set currency based on indicator
        request.data.currency = determine_tase_currency(indicator)
        
        # Populate data fields from parsed data
        # For fast fetch, we expect single-point data (not time series)
        if 'date' in parsed_data:
            # Ensure date is converted to pd.Timestamp
            try:
                date_value = parsed_data['date']
                if isinstance(date_value, pd.Timestamp):
                    request.data.dates = date_value
                elif isinstance(date_value, str):
                    request.data.dates = pd.to_datetime(date_value)
                elif isinstance(date_value, list):
                    request.data.dates = [pd.to_datetime(d) for d in date_value]
            except Exception as e:
                logger.warning(f"Failed to convert date value: {e}. Using default date.")
            # If no valid date or conversion failed, keep the default from indicatorRequest initialization
        
        request.data.price = parsed_data.get('price', 0.0)
        # For single-point fast fetch, last price equals current price
        request.data.last = request.data.price
        request.data.open = parsed_data.get('open', 0.0)
        request.data.high = parsed_data.get('high', 0.0)
        request.data.low = parsed_data.get('low', 0.0)
        request.data.volume = parsed_data.get('volume', 0)
        request.data.name = parsed_data.get('name', '')
        
        # Calculate change percentage if we have both current and previous prices
        # Use the last field which should be scalar for single-point fast fetch
        prev_close = parsed_data.get('previous_close')
        if (prev_close is not None and 
            prev_close != 0 and  # Allow negative prices, just not zero
            request.data.last is not None and 
            request.data.last != 0 and
            not isinstance(request.data.last, list)):  # Ensure scalar value
            change_pct = ((request.data.last / prev_close) - 1.0) * 100.0
            request.data.change_pct = change_pct
        
        request.success = True
        request.message = f"{indicator} - Successfully fetched data from TASE"
        logger.info(request.message)
        
    except Exception as e:
        request.message = f"{indicator} - Error populating data structure: {str(e)}"
        logger.error(request.message)
        request.success = False