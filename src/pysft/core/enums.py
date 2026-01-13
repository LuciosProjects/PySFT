"""
    Module: PySFT_Enums
    ----------------------
    This module contains enum definitions used in the PySFT project.
"""

from enum import Enum

class E_FetchMode(Enum):
    NULL        = -1
    METADATA    = 0
    ANALYSIS    = 1

class E_FetchType(Enum):
    NULL            = -1 # Undefined fetch type
    YFINANCE        = 0 # Fetch data from Yahoo Finance
    TASE            = 1 # Fetch data from TASE
    # TASE_FAST       = 2 # Fetch real-time data from TASE
    # TASE_HISTORICAL = 3 # Fetch historical data from TASE
    DATABASE        = 4 # Fetch data from local database

class E_IndicatorType(Enum):
    NULL        = -1
    YFINANCE    = 0
    TASE_MTF    = 1
    TASE_ETF    = 2
    TASE_SEC    = 3
    TASE_THEMARKER = 4

class E_DataSource(Enum):
    NULL            = -1
    YFINANCE        = 0
    TASE            = 1
    THEMARKER       = 2
    INVESTINGCOM    = 3
    DATABASE        = 4

class E_TheMarkerPeriods(Enum):
    WEEK    = "week"
    MONTH   = "month"
    YEAR1   = "year1"
    YEAR3   = "year3"
    YEAR5   = "year5"

class TASEListingStatus(Enum):
    ACTIVE      = 1
    MERGED      = 2
    LIQUIDATED  = 3
    DELISTED    = 4