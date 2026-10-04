"""Regression checks for behavior-neutral typing corrections."""

from types import FunctionType

import pytest

from pysft.core.tase_specific_utils import MAYA_TASE_URLS, TASE_URLS


@pytest.mark.parametrize(
    ("namespace", "name", "args", "expected"),
    [
        (
            MAYA_TASE_URLS,
            "TRADED_SECURITIES_LISTING_API",
            (2026, 10, 3),
            "https://datawise.tase.co.il/v1/basic-securities/trade-securities-list/2026/10/3",
        ),
        (
            MAYA_TASE_URLS,
            "MTF",
            ("5111422",),
            "https://maya.tase.co.il/he/funds/mutual-funds/5111422/major_data",
        ),
        (
            MAYA_TASE_URLS,
            "ETF",
            ("1183441",),
            "https://market.tase.co.il/en/market_data/etf/1183441/major_data",
        ),
        (
            MAYA_TASE_URLS,
            "SECURITY",
            ("1183441",),
            "https://market.tase.co.il/en/market_data/security/1183441/major_data",
        ),
        (
            TASE_URLS,
            "THEMARKER",
            ("1183441",),
            "https://finance.themarker.com/etf/1183441",
        ),
    ],
)
def test_url_helpers_preserve_class_calls_and_descriptors(namespace, name, args, expected):
    assert isinstance(vars(namespace)[name], FunctionType)
    assert getattr(namespace, name)(*args) == expected


@pytest.mark.parametrize(
    ("quote_type", "segment"),
    [("MTF", "mutualfunds"), ("ETF", "tradedfund"), ("EQUITY", "capitalmarket")],
)
@pytest.mark.parametrize(
    ("name", "page"),
    [("BIZPORTAL_GENERALVIEW", "generalview"), ("BIZPORTAL_DIVIDENDS", "dividends")],
)
def test_bizportal_url_branches_remain_unchanged(quote_type, segment, name, page):
    assert isinstance(vars(TASE_URLS)[name], FunctionType)
    assert getattr(TASE_URLS, name)(quote_type, "1183441") == (
        f"https://www.bizportal.co.il/{segment}/quote/{page}/1183441"
    )