from typing import Optional
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

import pysft.core.constants as const
from pysft.core.enums import E_IndicatorType

from pysft.tools.logger import get_logger

logger = get_logger(__name__)

@dataclass
class TASE_SEC_URLs:
    MTF = lambda indicator: f"https://maya.tase.co.il/en/funds/mutual-funds/{indicator}/historical-data?period=3" # Base URL for TASE MTF historical data page (5 years)
    ETF = lambda indicator: f"https://market.tase.co.il/en/market_data/etf/{indicator}/historical_data/eod?pType=7&oId={indicator}" # Base URL for TASE ETF historical data page (5 years)
    SECURITY = lambda indicator: f"https://market.tase.co.il/en/market_data/security/{indicator}/historical_data/eod?pType=7&oId=0{indicator}" # Base URL for TASE Security historical data page (5 years)
    THEMARKER = lambda indicator: f"https://finance.themarker.com/etf/{indicator}" # Base URL for TheMarker

def determine_tase_currency(indicator: str) -> str:
    """
    Determine the currency for a specific TASE indicator.
    """

    if indicator.isdigit():
        return 'ILS'
    elif indicator.startswith("126."):
        return 'USD'

    return 'USD' # Default will be USD

def get_TASE_url(indicator_type: E_IndicatorType, indicator: str) -> str | None:
    """
        Get the URL for a specific TASE indicator type.
    """

    if indicator_type == E_IndicatorType.TASE_MTF:
        return TASE_SEC_URLs.MTF(indicator)
    elif indicator_type == E_IndicatorType.TASE_ETF:
        return TASE_SEC_URLs.ETF(indicator)
    elif indicator_type == E_IndicatorType.TASE_SEC:
        return TASE_SEC_URLs.SECURITY(indicator)
    else:
        return None
    
def _fetch_from_url(url: str, timeout: int = 10) -> Optional[str]:
    """
    Fetch HTML content from a URL with retries.
    
    Args:
        url (str): The URL to fetch
        timeout (int): Request timeout in seconds
    
    Returns:
        Optional[str]: HTML content if successful, None otherwise
    """
    
    try:
        response = requests.get(url, headers=const.TASE_REQUEST_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {str(e)}")
    
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
