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
    NULL            = -1
    YFINANCE        = 0
    TASE_FAST       = 1
    TASE_HISTORICAL = 2


class E_IndicatorType(Enum):
    NULL        = -1
    YFINANCE    = 0
    TASE_MTF    = 1
    TASE_ETF    = 2
    TASE_SEC    = 3
    TASE_THEMARKER = 4