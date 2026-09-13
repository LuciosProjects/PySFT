# ---- Standard library imports ----

# ---- Third party imports ----
import requests

# ---- Package imports ----
import pysft.core.constants as const
from pysft.core.enums import E_FetchMode
from pysft.core.structures import indicatorRequest
import pysft.core.utilities as utils
import pysft.core.tase_specific_utils as tase_utils

from pysft.tools.logger import get_logger

logger = get_logger(__name__)

def fetch_TASE(request: indicatorRequest):
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
    
    # spiders = {"TheMarker": TheMarkerSpider(indicator)}

    # Initialize request status
    request.success = False

    session = requests.session()

    for attempt in range(const.MAX_ATTEMPTS):
        # Determine quote type if not already set

        quote_type = tase_utils.infer_tase_quote_type_from_url( session,
                                                                tase_utils.TASE_URLS.THEMARKER(request.indicator),
                                                                timeout=const.TASE_HEAD_REQUEST_TIMEOUT.seconds())
        if request.data.quoteType == "" and quote_type is not None:
            request.data.quoteType = quote_type
            message = f"{request.indicator} - Inferred quote type '{quote_type}' from TheMarker URL on attempt {attempt + 1}"
            logger.info(message)
        else:
            request.message = f"{request.indicator} - Quote type determination failed on attempt {attempt + 1}"
            request.message = utils.add_attempt2msg(request.message, attempt)
            logger.warning(request.message)
            continue

        # if request.data.quoteType == "" and not tase_utils.tase_determine_quote_type(request.data, 
        #                                                                              session,
        #                                             tase_utils.TASE_URLS.THEMARKER(request.indicator),
        #                                             timeout=const.TASE_HEAD_REQUEST_TIMEOUT.seconds()):
        #     request.message = f"{request.indicator} - Quote type determination failed before fetch attempt {attempt + 1}"
        #     request.message = utils.add_attempt2msg(request.message, attempt)
        #     logger.warning(request.message)
        #     continue
        
        # Check for any dividend data before fetching main data (INFO only)
        if request.mode != E_FetchMode.PRICE and not tase_utils.get_Bizportal_dividend_data(request.data, session):
            request.message = f"{request.indicator} - Failed to fetch dividend data from Bizportal on attempt {attempt + 1}"
            request.message = utils.add_attempt2msg(request.message, attempt)
            logger.warning(request.message)
            continue

        # Route the fetch based on quote type
        if request.data.quoteType == "MTF":
            # Fetch MTF data
            info_ok = True
            price_ok = True

            if request.mode != E_FetchMode.PRICE:
                info_ok = tase_utils.get_Bizportal_general_indicator_data(request.data, session)
                if not info_ok:
                    request.message = f"{request.indicator} - Failed to fetch MTF general data from Bizportal on attempt {attempt + 1}"
                    request.message = utils.add_attempt2msg(request.message, attempt)
                    logger.warning(request.message)
                    continue

            if request.mode != E_FetchMode.INFO:
                price_ok = tase_utils.get_Bizportal_graph_data(request.data, session)
                if not price_ok:
                    request.message = f"{request.indicator} - Failed to fetch MTF graph data from Bizportal on attempt {attempt + 1}"
                    request.message = utils.add_attempt2msg(request.message, attempt)
                    logger.warning(request.message)
                    continue

            if info_ok and price_ok:
                request.success = True
                request.message = f"{request.indicator} - Successfully fetched MTF data from Bizportal"
            else:
                request.message = f"{request.indicator} - Failed to fetch MTF data from Bizportal on attempt {attempt + 1}"
                request.message = utils.add_attempt2msg(request.message, attempt)
                logger.warning(request.message)

        elif request.data.quoteType in ["ETF", "STOCK"]:

            isForeign = False
            with tase_utils.get_tase_security_db_connection() as db:
            # db = tase_utils.get_tase_security_db()
            # lookup security info from local TASE security list database
                dataPt = db.execute(f'''
                    SELECT securityId, isin, companyName, symbol
                    FROM security_list
                    WHERE indicator = ?
                ''', (request.indicator,))

                row = dataPt.fetchall()
                if row.__len__() > 0:
                    row = row[0]
                    if row is not None:
                        isForeign = row[1].startswith("IL") == False
                        # Populate request with database info
                        request.indicator = request.data.indicator = '0' + str(row[0]) if isForeign else str(row[0]) # TASE uses leading '0' for foreign securities
                        request.data.ISIN = row[1] # ISIN
                        request.data.name = row[-1] # Company or security Name

            # Get general data from Bizportal and graph data from MAYA TASE
            info_ok = True
            price_ok = True

            if request.mode != E_FetchMode.PRICE:
                info_ok = tase_utils.get_Bizportal_general_indicator_data(request.data, session)
                if not info_ok:
                    request.message = f"{request.indicator} - Failed to fetch general data from Bizportal on attempt {attempt + 1}"
                    request.message = utils.add_attempt2msg(request.message, attempt)
                    logger.warning(request.message)
                    continue

            if request.mode != E_FetchMode.INFO:
                price_ok = tase_utils.get_MAYA_TASE_graph_data(request.data, session)
                if not price_ok:
                    request.message = f"{request.indicator} - Failed to fetch graph data from TASE Maya on attempt {attempt + 1}"
                    request.message = utils.add_attempt2msg(request.message, attempt)
                    logger.warning(request.message)
                    continue

            if info_ok and price_ok:
                request.success = True
                request.message = f"{request.original_indicator} - Successfully fetched data"
            else:
                request.message = f"{request.indicator} - Failed to fetch data on attempt {attempt + 1}"
                request.message = utils.add_attempt2msg(request.message, attempt)
                logger.warning(request.message)

        # request.data.currency = "ILS" # After converting all prices from agorot to shekels, set currency to ILS

        # TASE fetcher is authoritative for Tel Aviv securities, so expose the
        request.data.exchange = "TASE"

        logger.info(request.message)
        break