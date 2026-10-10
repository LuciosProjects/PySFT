import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from typing import cast as _cast

import exchange_calendars
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4 import Tag as _Tag

import pysft.core.constants as const
import pysft.core.utilities as utils
from pysft.core.enums import E_FetchType
from pysft.core.structures import _indicator_data
from pysft.tools.logger import get_logger

TASE_DATAHUB_API_KEY_ENV = "TASE_DATAHUB_API_KEY"

TASE_MTF_LISTING: list | None = None
TASE_SECURITY_LISTING: list | None = None
TASE_COMPANIES_LISTING: list | None = None

logger = get_logger(__name__)

TASE_CALENDAR = exchange_calendars.get_calendar("XTAE")

TASE_SECURITY_DB_PATH = os.path.join(os.path.dirname(__file__), '../data/tase_security_list.db')

@contextmanager
def get_tase_security_db_connection():
    """
    Context manager for thread-safe database access.
    Creates a new connection per call and properly closes it.
    """
    conn = None
    try:
        conn = sqlite3.connect(TASE_SECURITY_DB_PATH)
        yield conn
    finally:
        if conn:
            conn.close()

def get_tase_datahub_api_headers(api_key: str | None = None) -> dict[str, str]:
    """Build DataHub headers without storing credentials in module globals.

    Applications embedding PySFT (including via a Git submodule) own secret
    loading. They may either set ``TASE_DATAHUB_API_KEY`` in the process
    environment or pass a key explicitly. PySFT deliberately does not search
    for or load ``.env`` files at import time.
    """
    resolved_key = api_key if api_key is not None else os.environ.get(TASE_DATAHUB_API_KEY_ENV, "")
    return {
        "accept": "application/json",
        "accept-language": "en-US",
        "apikey": resolved_key,
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
    # [Replit Agent] Use a plain listing URL because it contains no interpolation.
    MTF_LISTING_API                 = "https://datawise.tase.co.il/v1/fund/fund-list?listingStatusId=1" # 1 for active funds, the only type that is traded on TASE

    # [Replit Agent] Replace the assigned lambda with a function, keeping its signature and URL.
    # These legacy namespace functions are called on the class. Explicit Any
    # preserves their descriptor behavior without inferring a bound self type.
    def TRADED_SECURITIES_LISTING_API(year: Any, month: int | str, day: int | str) -> str:
        return f"https://datawise.tase.co.il/v1/basic-securities/trade-securities-list/{year}/{month}/{day}"

    SECURITIES_LISTING_API          = "https://datawise.tase.co.il/v1/basic-securities/securities-list"
    COMPANIES_LISTING_API           = "https://datawise.tase.co.il/v1/basic-securities/companies-list"
    CHART                           = "https://api.tase.co.il/api/charts/gethistorydata"

    # [Replit Agent] Replace the assigned lambda without changing the mutual-fund URL.
    def MTF(indicator: Any) -> str:
        return f"https://maya.tase.co.il/he/funds/mutual-funds/{indicator}/major_data" # Base URL for TASE MTF

    # [Replit Agent] Replace the assigned lambda without changing the ETF URL.
    def ETF(indicator: Any) -> str:
        return f"https://market.tase.co.il/en/market_data/etf/{indicator}/major_data" # Base URL for TASE ETF

    # [Replit Agent] Replace the assigned lambda without changing the security URL.
    def SECURITY(indicator: Any) -> str:
        return f"https://market.tase.co.il/en/market_data/security/{indicator}/major_data" # Base URL for TASE Security

@dataclass
class TASE_URLS:
    # [Replit Agent] Replace the assigned lambda without changing the TheMarker URL.
    # Keep the legacy class-callable descriptor; see MAYA_TASE_URLS above.
    def THEMARKER(indicator: Any) -> str:
        return f"https://finance.themarker.com/etf/{indicator}" # Base URL for TheMarker

    THEMARKER_GQL = "https://www.themarker.com/gql"
    BIZPORTAL = "https://www.bizportal.co.il/"

    # [Replit Agent] Replace the assigned lambda while retaining all quote-type URL branches.
    def BIZPORTAL_GENERALVIEW(quoteType: Any, indicator: str) -> str:
        return (
            f"https://www.bizportal.co.il/mutualfunds/quote/generalview/{indicator}" if quoteType == "MTF" else
            f"https://www.bizportal.co.il/tradedfund/quote/generalview/{indicator}" if quoteType == "ETF" else
            f"https://www.bizportal.co.il/capitalmarket/quote/generalview/{indicator}"
        )

    # [Replit Agent] Replace the assigned lambda while retaining all dividend URL branches.
    def BIZPORTAL_DIVIDENDS(quoteType: Any, indicator: str) -> str:
        return (
            f"https://www.bizportal.co.il/mutualfunds/quote/dividends/{indicator}" if quoteType == "MTF" else
            f"https://www.bizportal.co.il/tradedfund/quote/dividends/{indicator}" if quoteType == "ETF" else
            f"https://www.bizportal.co.il/capitalmarket/quote/dividends/{indicator}"
        )

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

    current_element: _Tag = soup
    for step in path:
        if step == "^":
            next_element = current_element.parent
        elif step == ">":
            next_element = current_element.find_next_sibling()
        elif step == "<":
            next_element = current_element.find_previous_sibling()
        elif step == "v":
            next_element = current_element.findChild()
        else:
            logger.error(f"Invalid path step: {step}")
            return None

        if next_element is None:
            return None
        current_element = next_element
    
    return current_element if isinstance(current_element, BeautifulSoup) else None

def get_tase_mtf_listing():
    """
    Fetch MTF listings from TASE DataWise API and stores it in a global variable (json format).
    """

    if const.SKIP_TASE:
        return # Skipping TASE related fetch as per settings

    for attempt in range(const.MAX_ATTEMPTS):
        try:
            response = requests.get(MAYA_TASE_URLS.MTF_LISTING_API,
                                    headers=get_tase_datahub_api_headers(),
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            global TASE_MTF_LISTING
            TASE_MTF_LISTING = response.json().get("funds", {}).get("result", {})
            utils.random_delay(0.2, 0.3)  # polite delay between requests
            break # Successful fetch, exit loop
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch MTF listings from TASE DataWise API: {e!s}",
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
                                    headers=get_tase_datahub_api_headers(),
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            global TASE_SECURITY_LISTING
            TASE_SECURITY_LISTING = response.json().get("companiesList", {}).get("result", {})
            utils.random_delay(0.2, 0.3)  # polite delay between requests
            break # Successful fetch, exit loop
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch security listings from TASE DataWise API: {e!s}",
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
                                    headers=get_tase_datahub_api_headers(),
                                    timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
            response.raise_for_status()

            global TASE_COMPANIES_LISTING
            TASE_COMPANIES_LISTING = response.json().get("companiesList", {}).get("result", {})
            utils.random_delay(0.2, 0.3)  # polite delay between requests
            break # Successful fetch, exit loop
        except Exception as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch company listings from TASE DataWise API: {e!s}",
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return


def find_YF_equivalent(requests: dict[str, dict[str, Any]]) -> bool:
    '''
    For a given TASE indicator request, find its equivalent yfinance ticker using the local TASE security database.
    Thread-safe: creates and closes connection per call.
    '''

    try:
        with get_tase_security_db_connection() as conn:
            for req in requests.values():
                # lookup security info from local TASE security list database
                # [Replit Agent] Use a plain SQL string; parameters are still bound separately.
                dataPt = conn.execute('''
                    SELECT isin, symbol
                    FROM security_list
                    WHERE indicator = ?
                ''', (req[const.REQUEST_FIELD].indicator,))
                    
                row = dataPt.fetchall()
                if row.__len__() > 0:
                    row = row[0]
                    # If found, set request to YFINANCE (prefer yfinance over TASE if possible)
                    req[const.FETCH_TYPE_FIELD] = E_FetchType.YFINANCE
                    req[const.REQUEST_FIELD].data.ISIN = row[0]
                    req[const.REQUEST_FIELD].indicator = req[const.REQUEST_FIELD].data.indicator = row[1].replace('.','-') + ".TA" # add .TA suffix for TASE securities
    except Exception as e:
        logger.warning(f"Failed to lookup TASE security database: {e!s}")

    return any([req[const.FETCH_TYPE_FIELD] == E_FetchType.TASE for req in requests.values()])


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


def infer_tase_quote_type_from_url(
    session: requests.Session,
    url: str,
    timeout: float = 10,
) -> str | None:
    """Infer TASE quote type from a URL by following redirects.

    Returns an uppercase quote type (e.g. ``MTF``, ``ETF``, ``STOCK``)
    when resolution succeeds, otherwise ``None``.
    """

    real_url = url
    for attempt in range(const.MAX_ATTEMPTS):
        try:
            head_response = session.head(url, allow_redirects=True, timeout=timeout)
            head_response.raise_for_status()
            real_url = head_response.url
            break
        except Exception as e:
            if utils.handle_fetch_attempt_failure(
                attempt,
                const.MAX_ATTEMPTS,
                f"Failed to perform HEAD request for {url}: {e!s}",
                utils.random_delay,
                (0.2, 1),
            ):
                continue
            return None

    for segment in real_url.split('/'):
        if segment in const.THEMARKER_QUOTE_TYPES:
            return segment.upper()

    logger.warning(f"Could not determine quote type from URL: {real_url}")
    return None


# def infer_tase_quote_type_for_indicator(indicator: str, timeout: float = 10) -> str | None:
#     """Infer TASE quote type for an indicator using TheMarker redirects."""

#     with requests.Session() as session:
#         return infer_tase_quote_type_from_url(
#             session,
#             TASE_URLS.THEMARKER(indicator),
#             timeout=timeout,
#         )

# def tase_determine_quote_type(data: _indicator_data, session: requests.Session, url: str, timeout: float = 10) -> bool:
#     """
#     Determine the quote type of a TASE indicator by inspecting the final URL after redirects.
#     """

#     quote_type = infer_tase_quote_type_from_url(session, url, timeout=timeout)
#     if not quote_type:
#         return False

#     data.quoteType = quote_type
#     return True

    
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
                                                    f"Failed to fetch Bizportal dividend data for {data.indicator}: {e!s}",
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

                    if date18M_Ago:
                        if payment_idx != -1 and pay_day_idx != -1 and event_date >= date18M_Ago:
                            acc_amount += float(contents[payment_idx].replace(",", ""))
                        elif event_date < date18M_Ago:
                            break  # No need to check older rows

            data.dividendYield = acc_amount/current_price * 100.0

        return True
        
    except Exception as e:
        logger.error(f"Error parsing Bizportal dividend content for {data.indicator}: {e!s}")
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
                                                    f"Failed to fetch Bizportal expense rate data for {data.indicator}: {e!s}",
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
            # Not applicable is not an observed zero.
            data._present_fields.discard("expense_rate")

        # Extract name as well
        paper_top_title = soup.find("div", class_="paper_top_title")
        if paper_top_title:
            temp = paper_top_title.find("h1", class_="paper_h1")
            if temp:
                data.name = temp.get_text(strip=True)

    except Exception as e:
        logger.error(f"Error parsing Bizportal expense rate content for {data.indicator}: {e!s}")
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

    general_view = _get_Bizportal_generalview_data(data, session)
    if general_view is None:
        return False
    soup, pairs = general_view

    try:
        _set_Bizportal_currency(data, pairs["מטבע"])

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
                    temp = paper_top_title.find("h1", class_="paper_h1")
                    if temp:
                        data.name = temp.get_text(strip=True)
        elif data.quoteType != "STOCK":
            # quote type is not MTF or TASE_MTF_LISTING is not available, extract the name from the HTML as a fallback, ISIN won't be available in this case
            paper_top_title = soup.find("div", class_="paper_top_title")
            if paper_top_title:
                temp = paper_top_title.find("h1", class_="paper_h1")
                if temp:
                    data.name = temp.get_text(strip=True)

        # Extract fees and inception date
        if data.quoteType != "STOCK":
            data.expense_rate = (float(pairs["דמי ניהול"].replace("%", "")) + \
                                float(pairs["דמי נאמנות"].replace("%", "")))

            data.inceptionDate = pd.to_datetime(pairs["תאריך הקמה"], format="%d/%m/%Y")

            # Find the key that contains "היקף נכסים"
            asset_key = next((k for k in pairs if "היקף נכסים" in k), None)
        else:
            if "מכפיל רווח(12 חודשים אחרונים)" in pairs:
                data.trailingPE = float(pairs["מכפיל רווח(12 חודשים אחרונים)"])
            asset_key = next((k for k in pairs if "שווי שוק" in k), None)

        # Determine market cap scale
        MC_scale_matches = re.findall(r"\([א-ת]+?'? ₪\)", asset_key) if asset_key else []
        MC_scale = re.sub(r"[\(\) ₪']", "", MC_scale_matches[0]) if MC_scale_matches else ""

        # Apply scaling to market cap value
        data.market_cap = scale_value(float(pairs[_cast(str, asset_key)].replace(",", "")), MC_scale)

    except Exception as e:
        logger.error(f"Error parsing Bizportal content for {data.indicator}: {e!s}")
        return False

    return True


def _get_Bizportal_generalview_data(
    data: _indicator_data, session: requests.Session
) -> tuple[BeautifulSoup, dict[str, str]] | None:
    """Fetch and parse the Bizportal general-view page shared by info and price paths."""
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

        except requests.RequestException as e:
            if utils.handle_fetch_attempt_failure(attempt, const.MAX_ATTEMPTS,
                                                    f"Failed to fetch Bizportal data for {data.indicator}: {e!s}",
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return None
    
    if response is None:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    dt_tags = soup.select("dl dt")
    dd_tags = soup.select("dl dd")
    pairs = {
        dt.get_text(strip=True): dd.get_text(strip=True)
        for dd, dt in zip(dd_tags, dt_tags)
    }
    return soup, pairs


def _set_Bizportal_currency(data: _indicator_data, currency_label: str) -> None:
    """Store the public currency alias and transient source quote-unit label."""
    source_currency = TASE_CURRENCY_MAP[currency_label]
    data.currency = const.CURRENCY_NORMALIZATION[source_currency]["alias"]
    # Keep this source-specific label off the public data model and its cache schema.
    data.__dict__["_bizportal_currency_label"] = currency_label


def get_Bizportal_currency(data: _indicator_data, session: requests.Session) -> bool:
    """Load only Bizportal currency context for price-only MTF fetches."""
    if const.SKIP_BIZPORTAL:
        return False

    general_view = _get_Bizportal_generalview_data(data, session)
    if general_view is None:
        return False

    _, pairs = general_view
    try:
        _set_Bizportal_currency(data, pairs["מטבע"])
    except KeyError as e:
        logger.error(f"Error parsing Bizportal currency for {data.indicator}: {e!s}")
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

    # A cached public currency alias does not preserve the provider's quote unit.
    needs_currency_context = not data.currency or (
        data.quoteType == "MTF"
        and data.currency == "ILS"
        and not getattr(data, "_bizportal_currency_label", "")
    )
    if needs_currency_context and not get_Bizportal_currency(data, session):
        return False

    payload: dict[str, str | int] = {
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
                                                    f"Failed to fetch Bizportal graph data for {data.indicator}: {e!s}",
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return False
            
    source_currency_label = getattr(data, "_bizportal_currency_label", "")
    source_currency = TASE_CURRENCY_MAP.get(source_currency_label, data.currency)
    normalization = const.CURRENCY_NORMALIZATION.get(source_currency)
    if normalization is None:
        logger.error(f"Unknown Bizportal currency {data.currency!r} for {data.indicator}")
        return False

    currency_factor = normalization["factor"]
    if data.quoteType == "MTF" and source_currency_label == "ש\"ח":
        currency_factor *= const.CURRENCY_NORMALIZATION["ILA"]["factor"]
    alias = normalization["alias"]

    data.currency = alias

    if json_data:
        # indices, dates = zip(*[(i, pd.to_datetime(data_pt["D_p"], format="%d/%m/%Y")) for i, data_pt in enumerate(json_data)])
        dates = [pd.to_datetime(data_pt["D_p"], format="%d/%m/%Y") for data_pt in json_data]

        if dates[0] < data.dates[-1]:
            # most recent requested date is after the most recent available date in the data
            data.dates[-1] = dates[0]
        if dates[0] < data.dates[0]:
            # earliest requested date is after the most recent available date in the data
            data.dates[0] = dates[0]

        all_prices  = []
        all_dates   = []
        indices     = set()
        for idx, date in enumerate(dates):
            if data.dates[0] <= date <= data.dates[-1]:
                all_prices.append(json_data[idx]["C_p"]*currency_factor)
                all_dates.append(date)
                indices.add(idx)
            elif date < data.dates[0]:
                break  # No need to check older dates
            
        ordered_indices = list(indices)[::-1] # Reverse to chronological order
        all_dates  = all_dates[::-1]  # Reverse to chronological order
        all_prices = all_prices[::-1]  # Reverse to chronological order

        if not all_prices:
            return False
        data.dates  = all_dates

        data.price  = all_prices
        # This fund graph supplies closing NAVs only, not intraday OHLC.
        for field in ("open", "high", "low"):
            data._present_fields.discard(field)
        data.last   = data.price[-1]
        data.volume = [json_data[i]["V_p"] for i in ordered_indices]

        data.change_pct = [
            (json_data[i]["C_p"]/json_data[i+1]["C_p"] - 1)
            if i + 1 < len(json_data) and json_data[i+1]["C_p"] != 0
            else float("nan") for i in ordered_indices
        ]


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
                                                    f"Failed to fetch MAYA TASE general page for {data.indicator}: {e!s}",
                                                    utils.random_delay, (0.2, 1)):
                continue
            else:
                return False

    payload: dict[str, str | int] = {
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
                                                    f"Failed to fetch Bizportal graph data for {data.indicator}: {e!s}",
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
        
        if len(closes) < 2:
            return False
        # Filter data to match requested dates
        data.dates = dates[1:]
        data.price = list(np.array(closes[1:])/100.0)  # MAYA TASE prices are in agorot (mostly...)
        data.open = list(np.array(opens[1:])/100.0)
        data.high = list(np.array(highs[1:])/100.0)
        data.low = list(np.array(lows[1:])/100.0)
        data.volume = volumes[1:]
        data.last = data.price[-1]

        data.change_pct = [
            (closes[i]/closes[i-1] - 1)*100 if closes[i-1] != 0 else float("nan")
            for i in range(1, len(closes))
        ]
    else:
        # No data fetched
        return False

    return True
