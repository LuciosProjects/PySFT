import os
from dotenv import load_dotenv

from typing import Any, Callable, Literal
import re
import time
import numpy as np
from dataclasses import dataclass
from datetime import date
import json

import requests
from bs4 import BeautifulSoup
import pandas as pd
from pandas import Timestamp
import exchange_calendars
import sqlite3

import pysft.core.constants as const
from pysft.core.enums import E_FetchType
from pysft.core.enums import E_TheMarkerPeriods
from pysft.core.structures import indicatorRequest, _indicator_data
import pysft.core.utilities as utils

from pysft.tools.translator import He2En_Translator

from pysft.tools.logger import get_logger

# Load environment variables from .env file
load_dotenv()

TASE_DATAHUB_API_KEY = os.environ.get("TASE_DATAHUB_API_KEY", default="")

TASE_MTF_LISTING: list | None = None
TASE_SECURITY_LISTING: list | None = None
TASE_COMPANIES_LISTING: list | None = None

logger = get_logger(__name__)

TASE_CALENDAR = exchange_calendars.get_calendar("XTAE")

TASE_SECURITY_DB = sqlite3.connect(os.path.join(os.path.dirname(__file__), '../data/tase_security_list.db'))

TASE_DATAHUB_API_HEADERS = {
    'accept': "application/json",
    'accept-language': "en-US",
    'apikey': TASE_DATAHUB_API_KEY
}

TASE_CURRENCY_MAP = {
    "ש\"ח": "ILS",
    "שקל": "ILS",
    "₪": "ILS",
    "$": "USD",
    "דולר": "USD",
    "אגורות": "ILA",
    "יורו": "EUR",
    "אירו": "EUR",
}

# Path field is described with "^", ">", "<", "v" symbols indicating navigation in the HTML tree.:
# "^" - move to parent node
# ">" - move to next sibling
# "<" - move to previous sibling
# "v" - move to first child node

@dataclass
class MAYA_TASE_URLS:
    MTF_LISTING_API                 = f"https://datawise.tase.co.il/v1/fund/fund-list?listingStatusId=1" # 1 for active funds, the only type that is traded on TASE
    TRADED_SECURITIES_LISTING_API   = lambda year, month, day: f"https://datawise.tase.co.il/v1/basic-securities/trade-securities-list/{year}/{month}/{day}"
    SECURITIES_LISTING_API          = "https://datawise.tase.co.il/v1/basic-securities/securities-list"
    COMPANIES_LISTING_API           = "https://datawise.tase.co.il/v1/basic-securities/companies-list"
    CHART                           = "https://api.tase.co.il/api/charts/gethistorydata"
    MTF                             = lambda indicator: f"https://maya.tase.co.il/he/funds/mutual-funds/{indicator}/major_data" # Base URL for TASE MTF
    ETF                             = lambda indicator: f"https://market.tase.co.il/en/market_data/etf/{indicator}/major_data" # Base URL for TASE ETF
    SECURITY                        = lambda indicator: f"https://market.tase.co.il/en/market_data/security/{indicator}/major_data" # Base URL for TASE Security

@dataclass
class TASE_URLS:
    THEMARKER = lambda indicator: f"https://finance.themarker.com/etf/{indicator}" # Base URL for TheMarker
    THEMARKER_GQL = "https://www.themarker.com/gql"
    BIZPORTAL = "https://www.bizportal.co.il/"
    BIZPORTAL_GENERALVIEW = lambda quoteType, indicator:    f"https://www.bizportal.co.il/mutualfunds/quote/generalview/{indicator}" if quoteType == "MTF" else \
                                                            f"https://www.bizportal.co.il/tradedfund/quote/generalview/{indicator}" if quoteType == "ETF" else \
                                                            f"https://www.bizportal.co.il/capitalmarket/quote/generalview/{indicator}"
    BIZPORTAL_DIVIDENDS = lambda quoteType, indicator:      f"https://www.bizportal.co.il/mutualfunds/quote/dividends/{indicator}" if quoteType == "MTF" else \
                                                            f"https://www.bizportal.co.il/tradedfund/quote/dividends/{indicator}" if quoteType == "ETF" else \
                                                            f"https://www.bizportal.co.il/capitalmarket/quote/dividends/{indicator}"
    BIZPORTAL_GRAPHDATA = "https://www.bizportal.co.il/ajax/biz_papers_helper.ashx"

@dataclass
class TASE_DB_HELPERS:
    SECURITY_ALL_FIELDS = 'securityId, securityFullTypeCode, isin, symbol, companySuperSector, companySector, companySubSector, securityIsIncludedInContinuousIndices, corporateId, issuerId, companyName'

TASE_SCALE_UNITS = {
    "אלף": 1e3,
    "אלפי": 1e3,
    "א": 1e3,
    "אלפים": 1e3,
    "מיליון": 1e6,
    "מ": 1e6,
    "מיליונים": 1e6,
    "מיליארד": 1e9,
    "מיליארדים": 1e9,
    "ביליארד": 1e12,
}

def scale_value(value: float, scale: str) -> float:
    """
    Scale the market capitalization value based on the provided scale character.
    
    Args:
        value (float): The raw market capitalization value
        scale (str): The scale character (e.g., 'א', 'מ', 'ב', 'ט')
    Returns:
        float: The scaled market capitalization value
    """

    factor = TASE_SCALE_UNITS.get(scale, 1.0)
    return value * factor

def determine_tase_currency(indicator: str) -> str:
    """
    Determine the currency for a specific TASE indicator.
    """

    if indicator.isdigit():
        return 'ILS'
    elif indicator.startswith("126."):
        return 'USD'

    return 'USD' # Default will be USD

def get_element_by_path(soup: BeautifulSoup, path: str) -> BeautifulSoup | None:
    """
    Navigate the BeautifulSoup HTML tree based on a custom path notation.
    """

    current_element = soup
    for step in path:
        if step == "^":
            current_element = current_element.parent
        elif step == ">":
            current_element = current_element.find_next_sibling()
        elif step == "<":
            current_element = current_element.find_previous_sibling()
        elif step == "v":
            current_element = current_element.findChild()
        else:
            logger.error(f"Invalid path step: {step}")
            return None

        if current_element is None:
            return None
        
    return current_element

def get_tase_mtf_listing():
    """
    Fetch MTF listings from TASE DataWise API and stores it in a global variable (json format).
    """

    if const.SKIP_TASE:
        return # Skipping TASE related fetch as per settings

    for attempt in range(const.MAX_ATTEMPTS):
        try:
            response = requests.get(MAYA_TASE_URLS.MTF_LISTING_API,
                                    headers=TASE_DATAHUB_API_HEADERS, 
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            global TASE_MTF_LISTING
            TASE_MTF_LISTING = response.json().get("funds", {}).get("result", {})
            utils.random_delay(0.2, 0.3)  # polite delay between requests
            break # Successful fetch, exit loop
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch MTF listings from TASE DataWise API: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return


def get_tase_security_listings(target_date: date):
    """
    Fetch security listings from TASE DataWise API for a specific date and stores it in a global variable (json format).
    """

    if const.SKIP_TASE:
        return # Skipping TASE related fetch as per settings

    for attempt in range(const.MAX_ATTEMPTS):
        try:
            # url = MAYA_TASE_URLS.TRADED_SECURITIES_LISTING_API(target_date.year, target_date.month, target_date.day)
            response = requests.get(MAYA_TASE_URLS.SECURITIES_LISTING_API,
                                    headers=TASE_DATAHUB_API_HEADERS, 
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            global TASE_SECURITY_LISTING
            TASE_SECURITY_LISTING = response.json().get("companiesList", {}).get("result", {})
            utils.random_delay(0.2, 0.3)  # polite delay between requests
            break # Successful fetch, exit loop
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch security listings from TASE DataWise API: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return

def get_tase_company_listings():
    """
    Fetch company listings from TASE DataWise API for a specific date and stores it in a global variable (json format).
    """

    if const.SKIP_TASE:
        return # Skipping TASE related fetch as per settings

    for attempt in range(const.MAX_ATTEMPTS):
        try:
            # url = MAYA_TASE_URLS.TRADED_SECURITIES_LISTING_API(target_date.year, target_date.month, target_date.day)
            response = requests.get(MAYA_TASE_URLS.COMPANIES_LISTING_API,
                                    headers=TASE_DATAHUB_API_HEADERS, 
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            global TASE_COMPANIES_LISTING
            TASE_COMPANIES_LISTING = response.json().get("companiesList", {}).get("result", {})
            utils.random_delay(0.2, 0.3)  # polite delay between requests
            break # Successful fetch, exit loop
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch company listings from TASE DataWise API: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return


def find_YF_equivalent(requests: dict[str, dict[str, Any]]) -> bool:
    '''
    For a given TASE indicator request, find its equivalent yfinance ticker using the local TASE security database.
    '''

    if TASE_SECURITY_DB is not None:
        for request in requests.values():
            # lookup security info from local TASE security list database
            dataPt = TASE_SECURITY_DB.execute(f'''
                SELECT isin, symbol
                FROM security_list
                WHERE indicator = ?
            ''', (request[const.REQUEST_FIELD].indicator,))
                
            row = dataPt.fetchall()
            if row.__len__() > 0:
                row = row[0]
                # If found, set request to YFINANCE (prefer yfinance over TASE if possible)
                request[const.FETCH_TYPE_FIELD] = E_FetchType.YFINANCE
                request[const.REQUEST_FIELD].data.ISIN = row[0]
                request[const.REQUEST_FIELD].indicator = request[const.REQUEST_FIELD].data.indicator = row[1].replace('.','-') + ".TA" # add .TA suffix for TASE securities

    return not any([req[const.FETCH_TYPE_FIELD] == E_FetchType.TASE for req in requests.values()])


def get_TASE_globals(type: Literal["MTF", "SECURITY", "COMPANY"]) -> list | None:
    """
    Fetch and set global TASE data such as MTF listings or Security listings.
    
    Args:
        type (Literal["MTF", "SECURITY", "COMPANY"]): The type of global data to fetch
    """

    if type == "MTF":
        return TASE_MTF_LISTING
    elif type == "SECURITY":
        return TASE_SECURITY_LISTING
    elif type == "COMPANY":
        return TASE_COMPANIES_LISTING
    else:
        return None

def tase_determine_quote_type(data: _indicator_data, session: requests.Session, url: str, timeout: float = 10) -> bool:
    """
    Determine the quote type of a TASE indicator by inspecting the final URL after redirects.
    """

    real_url = url
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            head_response = session.head(url, allow_redirects=True, timeout=timeout)
            head_response.raise_for_status()
            real_url = head_response.url
            break # Successful HEAD request, exit loop
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to perform HEAD request for {url}: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return False

    final_url = real_url
    url_segments = final_url.split('/')

    for segment in url_segments:
        if segment in const.THEMARKER_QUOTE_TYPES:
            data.quoteType = segment.upper()
            return True
    logger.warning(f"Could not determine quote type from URL: {final_url}")
    return False

    
# Bizportal routines
def get_Bizportal_dividend_data(data: _indicator_data, session: requests.Session) -> bool:
    """
    Fetch dividend data from Bizportal for a given TASE indicator.
    Args:
        data (_indicator_data): Indicator data object to populate with extracted information
    """

    if const.SKIP_BIZPORTAL:
        return False # Skipping Bizportal related fetch as per settings

    session.headers.pop("Accept-Encoding", None)
    session.headers["user-agent"] = const.TASE_CONTENT_REQUEST_HEADERS["user-agent"]

    response = None
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            response = session.get( TASE_URLS.BIZPORTAL_DIVIDENDS(data.quoteType, data.indicator), 
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            if response is None:
                continue
            elif response.status_code == 200:
                break  # Successful fetch

        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch Bizportal dividend data for {data.indicator}: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return False
    utils.random_delay(0.2, 0.3)  # polite delay between requests
    
    if response is None:
        return False
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        dividend_table_wrapper = soup.find("div", class_="biz_tbl_wrap")
        tbl_head = dividend_table_wrapper.find("thead") if dividend_table_wrapper else None
        tbl_body = dividend_table_wrapper.find("tbody") if dividend_table_wrapper else None

        if tbl_body is None:
            # logger.info(f"No dividend data found for {data.indicator} on Bizportal.")
            return True  # No dividend data available is not an error
        else:
            # Get current price for yield calculation
            current_price_element = soup.find('div', class_='paper_rate')
            current_price = 0.0
            if current_price_element:
                current_price = float(current_price_element.get_text(strip=True).replace(",", "")) # price in agorot
            else:
                return False # Cannot find current price, cannot proceed

            # Parse table headers to find relevant columns
            header_elements = tbl_head.find_all("th") if tbl_head else []
            headers = [he.get_text(strip=True) for he in header_elements]

            event_idx   = headers.index("אירוע") if "אירוע" in headers else -1
            payment_idx = headers.index("תשלום") if "תשלום" in headers else -1
            pay_day_idx = headers.index("תאריך תשלום") if "תאריך תשלום" in headers else -1

            rows = tbl_body.find_all("tr")
            # Calculate trailing 18 months dividend yield
            mostRecentDate, date18M_Ago, acc_amount = None, None, 0.0
            for row in rows:
                # Stop at the first row that has a dividend (דיבידנד) event on it
                content_elements = row.find_all("td")
                contents = [ce.get_text(strip=True) for ce in content_elements]

                if event_idx != -1 and contents[event_idx] == "דיבידנד":
                    event_date = pd.to_datetime(contents[pay_day_idx], format="%d/%m/%Y")

                    if mostRecentDate is None:
                        mostRecentDate = event_date
                        date18M_Ago = mostRecentDate - pd.DateOffset(months=19) # use 19 months to be safe

                    if payment_idx != -1 and pay_day_idx != -1 and event_date >= date18M_Ago:
                        acc_amount += float(contents[payment_idx].replace(",", ""))
                    elif event_date < date18M_Ago:
                        break  # No need to check older rows

            data.dividendYield = acc_amount/current_price * 100.0

        return True
        
    except Exception as e:
        logger.error(f"Error parsing Bizportal dividend content for {data.indicator}: {str(e)}")
        return False

def get_Bizportal_expense_rate(data: _indicator_data, session: requests.Session | None = None) -> bool:
    '''
    Fetch expense rate data from Bizportal for a given TASE indicator.
    '''

    if not session:
        session = requests.Session()
    
    if const.SKIP_BIZPORTAL:
        return False # Skipping Bizportal related fetch as per settings
    
    session.headers.pop("Accept-Encoding", None)
    session.headers["user-agent"] = const.TASE_CONTENT_REQUEST_HEADERS["user-agent"]

    response = None
    utils.random_delay(0, 0.5)  # polite delay between requests
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            response = session.get( TASE_URLS.BIZPORTAL_GENERALVIEW(data.quoteType, data.indicator), 
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            if response is None:
                continue
            elif response.status_code == 200:
                break  # Successful fetch

        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch Bizportal expense rate data for {data.indicator}: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return False
            
    if response is None:
        return False
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        dt_tags = soup.select("dl dt")
        dd_tags = soup.select("dl dd")

        pairs = {}
        for dd, dt in zip(dd_tags, dt_tags):
            key = dt.get_text(strip=True)
            value = dd.get_text(strip=True)
            pairs[key] = value

        if data.quoteType not in ["STOCK", "EQUITY"]:
            data.expense_rate = (float(pairs["דמי ניהול"].replace("%", "")) + \
                                float(pairs["דמי נאמנות"].replace("%", "")))
        else:
            data.expense_rate = 0.0 # No expense rate for stocks
    except Exception as e:
        logger.error(f"Error parsing Bizportal expense rate content for {data.indicator}: {str(e)}")
        return False

    return True

def get_Bizportal_general_indicator_data(data: _indicator_data, session: requests.Session) -> bool:
    """
    Fetch general indicator data from Bizportal for a given TASE indicator.
    Args:
        data (_indicator_data): Indicator data object to populate with extracted information
    """

    if const.SKIP_BIZPORTAL:
        return False # Skipping Bizportal related fetch as per settings

    session.headers.pop("Accept-Encoding", None)
    session.headers["user-agent"] = const.TASE_CONTENT_REQUEST_HEADERS["user-agent"]

    response = None
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            response = session.get( TASE_URLS.BIZPORTAL_GENERALVIEW(data.quoteType, data.indicator), 
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            if response is None:
                continue
            elif response.status_code == 200:
                break  # Successful fetch

        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch Bizportal data for {data.indicator}: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return False
    
    if response is None:
        return False
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        dt_tags = soup.select("dl dt")
        dd_tags = soup.select("dl dd")

        pairs = {}
        for dd, dt in zip(dd_tags, dt_tags):
            key = dt.get_text(strip=True)
            value = dd.get_text(strip=True)
            pairs[key] = value

        data.currency = "ILA" # Default currency, most if not all TASE funds are traded in ILA

        if data.quoteType == "MTF" and TASE_MTF_LISTING is not None:
            fund = [res for res in TASE_MTF_LISTING if str(res.get("fundId", "")) == data.indicator]

            # in case of an empty list
            if fund:
                fund = fund[0]
                data.ISIN = fund.get("isin", "")
                data.name = fund.get("fundLongName", data.name)
            else:
                # fund not found in listing - fallback to HTML extraction, ISIN won't be available in this case
                paper_top_title = soup.find("div", class_="paper_top_title")
                if paper_top_title:
                    data.name = paper_top_title.find("h1", class_="paper_h1").get_text(strip=True)
        elif data.quoteType != "STOCK":
            # quote type is not MTF or TASE_MTF_LISTING is not available, extract the name from the HTML as a fallback, ISIN won't be available in this case
            paper_top_title = soup.find("div", class_="paper_top_title")
            if paper_top_title:
                data.name = paper_top_title.find("h1", class_="paper_h1").get_text(strip=True)

        # Extract fees and inception date
        if data.quoteType != "STOCK":
            data.expense_rate = (float(pairs["דמי ניהול"].replace("%", "")) + \
                                float(pairs["דמי נאמנות"].replace("%", "")))
        
            data.inceptionDate = pd.to_datetime(pairs["תאריך הקמה"], format="%d/%m/%Y")

            # Find the key that contains "היקף נכסים"
            asset_key = next((k for k in pairs.keys() if "היקף נכסים" in k), None)
        else:
            data.trailingPE = float(pairs["מכפיל רווח(12 חודשים אחרונים)"]) if "מכפיל רווח(12 חודשים אחרונים)" in pairs else 0.0
            asset_key = next((k for k in pairs.keys() if "שווי שוק" in k), None)

        # Determine market cap scale
        MC_scale = re.findall(r"\([א-ת]+?'? ₪\)", asset_key) if asset_key else []
        MC_scale = re.sub(r"[\(\) ₪']", "", MC_scale[0]) if MC_scale else ""

        # Apply scaling to market cap value
        data.market_cap = scale_value(float(pairs[asset_key].replace(",", "")), MC_scale)

    except Exception as e:
        logger.error(f"Error parsing Bizportal content for {data.indicator}: {str(e)}")
        return False

    return True

def get_Bizportal_graph_data(data: _indicator_data, session: requests.Session) -> bool:
    """
    Fetch historical price data from Bizportal for a given TASE indicator.
    Args:
        data (_indicator_data): Indicator data object to populate with extracted information
        session (requests.Session): HTTP session for making requests
    """

    if const.SKIP_BIZPORTAL:
        return False # Skipping Bizportal related fetch as per settings

    payload = {
        "action": "get_paper_yearly_graph",
        "request_type": 1,
        "paper_id": int(data.indicator),
        "dd": int(time.time() * 1000)
    }

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,he;q=0.8",
        "user-agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        "x-requested-with": "XMLHttpRequest",
        "referer": TASE_URLS.BIZPORTAL
    }

    response = None
    json_data = None
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            response = session.get( TASE_URLS.BIZPORTAL_GRAPHDATA, 
                                    params=payload,
                                    headers=headers,
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds(),
)
            response.raise_for_status()

            text = response.content.decode('utf-8')

            if text.startswith('~'):
                json_data = json.loads(text[1:])
            else:
                json_data = json.loads(text)

            break  # Successful fetch
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch Bizportal graph data for {data.indicator}: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return False
            
    currency_factor = const.CURRENCY_NORMALIZATION[data.currency]['factor']
    alias           = const.CURRENCY_NORMALIZATION[data.currency]['alias']

    data.currency = alias

    if json_data is not None:
        indices, dates = zip(*[(i, pd.to_datetime(data_pt["D_p"], format="%d/%m/%Y")) for i, data_pt in enumerate(json_data) if \
                                    pd.to_datetime(data_pt["D_p"], format="%d/%m/%Y") >= data.dates[0] and \
                                    pd.to_datetime(data_pt["D_p"], format="%d/%m/%Y") <= data.dates[-1]])
        indices     = list(indices)[::-1] # Reverse to chronological order
        data.dates  = list(dates)[::-1]  # Reverse to chronological order

        all_prices = [data_pt["C_p"]*currency_factor for data_pt in json_data][::-1]

        data.price  = [all_prices[i] for i in indices]
        data.open   = data.price
        data.high   = data.price
        data.low    = data.price
        data.last   = data.price[-1] if data.price else 0.0 # Last price is the most recent price
        data.volume = [json_data[i]["V_p"] for i in indices]

        data.change_pct = [(json_data[i]["C_p"]/json_data[i+1]["C_p"] - 1) if (i+1) < len(json_data) else 0.0 for i in indices]


    else:
        return False

    return True

# MAYA TASE routines
def get_MAYA_TASE_general_url(data: _indicator_data) -> str:
   
    if not data.ISIN.startswith("IL"):
        return MAYA_TASE_URLS.SECURITY(data.indicator)

    if data.quoteType == "MTF":
        return MAYA_TASE_URLS.MTF(data.indicator)
    elif data.quoteType == "ETF":
        return MAYA_TASE_URLS.ETF(data.indicator)
    elif data.quoteType == "STOCK":
        return MAYA_TASE_URLS.SECURITY(data.indicator)
    else:
        return MAYA_TASE_URLS.SECURITY(data.indicator)
    


def get_MAYA_TASE_graph_data(data: _indicator_data, session: requests.Session) -> bool:
    """
    Fetch historical price data from MAYA TASE for a given TASE indicator.
    Args:
        data (_indicator_data): Indicator data object to populate with extracted information
        session (requests.Session): HTTP session for making requests
    """

    if const.SKIP_TASE:
        return False # Skipping TASE related fetch as per settings

    # "Contaminate" sesseion headers to mimic a browser request from market.tase.co.il
    general_data_url = get_MAYA_TASE_general_url(data)
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            get_response = session.get(general_data_url, timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            get_response.raise_for_status()
            break  # Successful fetch
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch MAYA TASE general page for {data.indicator}: {str(e)}", 
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return False

    payload = {
        "ct": 3,     # 3 is for candle chart data
        "ot": 1,
        "lang": 1,
        "cf": 0,
        "cp": 8,     # custom date range (set by dFrom and dTo)
        "cv": 0,
        "cl": 0,
        "cgt": 1,
        "oId": int(data.indicator),
        "dFrom": (data.dates[0] - pd.Timedelta(days=1)).strftime("%d/%m/%Y"), # Take one day before the required initial date for percentage change calculation
        "dTo": data.dates[-1].strftime("%d/%m/%Y"),
    }

    headers = {
        "accept": "application/json, text/plain, */*",
        # "accept-language": "en-US,en;q=0.9,he;q=0.8",
        "accept-language": "he-IL",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://market.tase.co.il",
        "referer": "https://market.tase.co.il/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    }

    response = None
    json_data = None
    utils.random_delay(0.5, 3) # polite delay between requests
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            response = session.get( MAYA_TASE_URLS.CHART, 
                                    params=payload,
                                    headers=headers,
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds(),
                                    )
            response.raise_for_status()

            json_data = response.json().get("history", [])

            break  # Successful fetch
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch Bizportal graph data for {data.indicator}: {str(e)}", 
                                                    utils.random_delay, (0.5, 3)):
                continue
            else:
                return False
    
    dates = []
    opens = []
    closes = []
    highs = []
    lows = []
    volumes = []
    if json_data is not None:
        for dataPt in json_data:
            dates.append(pd.to_datetime(dataPt["tdt"], format="%d/%m/%Y"))
            opens.append(dataPt["ort"])
            closes.append(dataPt["crt"])
            highs.append(dataPt["hrt"])
            lows.append(dataPt["lrt"])
            approx_volume = np.round(dataPt["trov"]/((dataPt["crt"] + dataPt["lrt"] + dataPt["hrt"])/3), 2) # approximate volume based on turnover value
                                                                                                            # over average price between high, low and close
            volumes.append(approx_volume)
        
        # Filter data to match requested dates
        data.dates = dates[1:]
        data.price = list(np.array(closes[1:])/100.0)  # MAYA TASE prices are in agorot
        data.open = list(np.array(opens[1:])/100.0)
        data.high = list(np.array(highs[1:])/100.0)
        data.low = list(np.array(lows[1:])/100.0)
        data.volume = volumes[1:]
        data.last = data.price[-1] if data.price else 0.0 # Last price is the most recent price

        data.change_pct = [(closes[i]/closes[i-1] - 1)*100 if i > 0 else 0.0 for i in range(1, len(closes))]
    else:
        # No data fetched
        return False

    return True