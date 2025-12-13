from dataclasses import dataclass

from pysft.core.enums import E_IndicatorType

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