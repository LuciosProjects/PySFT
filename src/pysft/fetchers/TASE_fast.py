
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
from pysft.core.enums import E_IndicatorType
from pysft.core.tase_specific_utils import get_TASE_url, determine_tase_currency
from pysft.tools.logger import get_logger

logger = get_logger(__name__)


def _determine_indicator_type(indicator: str) -> E_IndicatorType:
    """
    Determine the TASE indicator type based on the indicator format.
    
    Args:
        indicator (str): The indicator string (e.g., '126.1234' or '1234567')
    
    Returns:
        E_IndicatorType: The determined indicator type
        
    Note:
        Pure numeric indicators are assumed to be securities (TASE_SEC).
        Indicators starting with "126." are mutual funds (MTF).
        Other formats default to TASE_SEC to attempt fetching.
        The distinction between ETF and other securities cannot be determined
        from the indicator format alone and would require additional data sources
        or metadata lookup.
    """
    if not indicator or not isinstance(indicator, str):
        return E_IndicatorType.NULL
        
    if indicator.startswith("126."):
        # TASE mutual funds (MTF) typically start with 126.
        return E_IndicatorType.TASE_MTF
    elif indicator.isdigit():
        # Pure numeric indicators are assumed to be securities
        return E_IndicatorType.TASE_SEC
    else:
        # Default to TASE_SEC for other formats to attempt fetching
        # This handles mixed alphanumeric or other valid TASE formats
        return E_IndicatorType.TASE_SEC


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


def _parse_tase_data(html_content: str, indicator_type: E_IndicatorType) -> Optional[dict]:
    """
    Parse TASE HTML content to extract financial data.
    
    Args:
        html_content (str): HTML content from TASE website
        indicator_type (E_IndicatorType): Type of TASE indicator
    
    Returns:
        Optional[dict]: Dictionary containing parsed financial data, or None if parsing fails
        
    Note:
        This is a placeholder implementation. The actual HTML parsing logic needs to be
        implemented based on the specific structure of TASE websites:
        
        For TASE_MTF (maya.tase.co.il):
            - Locate mutual fund price data (usually in specific div/span elements)
            - Extract fund name from page header or title
            - Parse date from page or data table
            - Extract NAV (Net Asset Value) as the primary price
            
        For TASE_ETF (market.tase.co.il/etf):
            - Find ETF price in the market data section
            - Extract trading volume from the data table
            - Parse open/high/low/close prices
            - Get ETF name and description
            
        For TASE_SEC (market.tase.co.il/security):
            - Similar to ETF but for stocks/securities
            - Extract additional fields like market cap if available
            
        Implementation steps:
            1. Inspect actual HTML from target URLs
            2. Identify CSS classes, IDs, or XPath selectors for data elements
            3. Use BeautifulSoup methods (find, find_all, select) to extract data
            4. Handle variations in HTML structure (missing data, different layouts)
            5. Convert extracted strings to appropriate types (float, int, datetime)
    """
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        data = {}
        
        # TODO: Implement actual HTML parsing based on TASE website structure
        # The following is a template showing expected data structure:
        #
        # if indicator_type == E_IndicatorType.TASE_MTF:
        #     # Parse Maya TASE mutual fund page
        #     data['name'] = soup.find('h1', class_='fund-name').text.strip()
        #     data['price'] = float(soup.find('span', class_='nav-value').text.strip())
        #     data['date'] = pd.to_datetime(soup.find('span', class_='date').text.strip())
        #     # ... extract other fields
        #
        # elif indicator_type == E_IndicatorType.TASE_ETF:
        #     # Parse TASE ETF page
        #     data['name'] = soup.find('h2', class_='etf-title').text.strip()
        #     price_elem = soup.find('td', {'data-field': 'lastPrice'})
        #     data['price'] = float(price_elem.text.strip()) if price_elem else 0.0
        #     # ... extract other fields
        #
        # elif indicator_type == E_IndicatorType.TASE_SEC:
        #     # Parse TASE security page
        #     # Similar structure to ETF
        #     pass
        
        # For now, return None to indicate parsing needs implementation
        logger.warning("TASE HTML parsing not yet implemented for website structure")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing TASE HTML content: {str(e)}")
        return None


def fetch_TASE_fast(request: indicatorRequest):
    """
    Fetch data for the given indicator using TASE fast fetcher.
    
    This function performs a fast, single-point data fetch from TASE (Tel Aviv Stock Exchange)
    by scraping the relevant TASE website. It's designed for current/recent data points
    rather than historical time series.

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
    
    # Determine the indicator type
    indicator_type = _determine_indicator_type(indicator)
    
    if indicator_type == E_IndicatorType.NULL:
        request.message = f"{indicator} - Unable to determine TASE indicator type"
        logger.error(request.message)
        return
    
    # Get the appropriate URL for this indicator type
    url = get_TASE_url(indicator_type, indicator)
    
    if url is None:
        request.message = f"{indicator} - Could not generate URL for indicator type {indicator_type}"
        logger.error(request.message)
        return
    
    logger.info(f"Fetching data from URL: {url}")
    
    # Fetch HTML content
    html_content = _fetch_from_url(url)
    
    if html_content is None:
        request.message = f"{indicator} - Failed to fetch data from TASE website after {const.MAX_ATTEMPTS} attempts"
        logger.error(request.message)
        return
    
    # Parse the HTML content
    parsed_data = _parse_tase_data(html_content, indicator_type)
    
    if parsed_data is None:
        request.message = f"{indicator} - Failed to parse data from TASE website"
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
            date_value = parsed_data['date']
            if isinstance(date_value, pd.Timestamp):
                request.data.dates = date_value
            elif isinstance(date_value, str):
                request.data.dates = pd.to_datetime(date_value)
            elif isinstance(date_value, list):
                request.data.dates = [pd.to_datetime(d) for d in date_value]
            # If no valid date, keep the default from indicatorRequest initialization
        
        request.data.price = parsed_data.get('price', 0.0)
        request.data.last = request.data.price
        request.data.open = parsed_data.get('open', 0.0)
        request.data.high = parsed_data.get('high', 0.0)
        request.data.low = parsed_data.get('low', 0.0)
        request.data.volume = parsed_data.get('volume', 0)
        request.data.name = parsed_data.get('name', '')
        
        # Calculate change percentage if we have both current and previous prices
        # Use the last field which should be scalar for single-point fast fetch
        if ('previous_close' in parsed_data and 
            parsed_data['previous_close'] > 0 and 
            request.data.last is not None and 
            request.data.last != 0 and
            not isinstance(request.data.last, list)):  # Ensure scalar value
            change_pct = ((request.data.last / parsed_data['previous_close']) - 1.0) * 100.0
            request.data.change_pct = change_pct
        
        request.success = True
        request.message = f"{indicator} - Successfully fetched data from TASE"
        logger.info(request.message)
        
    except Exception as e:
        request.message = f"{indicator} - Error populating data structure: {str(e)}"
        logger.error(request.message)
        request.success = False