from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable, List, Tuple
import pandas as pd

# -----------------------------
# Input parsing helpers
# -----------------------------

# Canonical attribute names and simple aliases
_ATTR_ALIASES = {
    "name": "name",
    "briefsummary": "briefSummary",
    "brief_summary": "briefSummary",
    "summary": "briefSummary",
    "quotetype": "quoteType",
    "quote_type": "quoteType",
    "type": "quoteType",
    "currency": "currency",
    "price": "price",
    "last": "last",
    "close": "last",
    "open": "open",
    "high": "high",
    "low": "low",
    "volume": "volume",
    "vol": "volume",
    "avgdailyvolume3mnth": "avgDailyVolume3mnth",
    "avg_daily_volume_3mnth": "avgDailyVolume3mnth",
    "avgvolume": "avgDailyVolume3mnth",
    "change%": "change_pct",
    "change_pct": "change_pct",
    "change": "change_pct",
    "marketcap": "market_cap",
    "market_cap": "market_cap",
    "cap": "market_cap",
    "expenserate": "expense_rate",
    "expense_rate": "expense_rate",
    "expense": "expense_rate",
    "dividendyield": "dividendYield",
    "dividend_yield": "dividendYield",
    "dividend": "dividendYield",
    "yield": "dividendYield",
    "trailingpe": "trailingPE",
    "trailing_pe": "trailingPE",
    "pe": "trailingPE",
    "forwardpe": "forwardPE",
    "forward_pe": "forwardPE",
    "beta": "beta",
}
_ALLOWED_INTERVALS = {"1d", "1wk", "1mo", "1y"}

def _normalize_indicators(indicators: str | Iterable[str]) -> List[str]:
    """
    Accepts:
      - single string (supports comma/whitespace separated list: 'AAPL, MSFT, 1183441')
      - list/iterable of strings
    Returns uppercase symbols without surrounding spaces.
    """

    if isinstance(indicators, str):
        parts = [p for p in re.split(r"[,\s]+", indicators) if p]
    else:
        parts = [str(t) for t in indicators]

    return [p.strip().upper() for p in parts if p.strip()]

def _parse_attributes(attributes: str | Iterable[str]) -> List[str]:
    """
    Accepts a comma-separated string or a list; maps to canonical attribute names.
    Unknown attributes raise ValueError to fail fast.
    """
    if isinstance(attributes, str):
        raw = [a for a in re.split(r"[,\s]+", attributes) if a]
    else:
        raw = [str(a) for a in attributes]

    canon: List[str] = []
    for a in raw:
        key = a.strip().lower()
        if key not in _ATTR_ALIASES:
            raise ValueError(
                f"Unsupported attribute '{a}'. Supported: {sorted(set(_ATTR_ALIASES.keys()))}"
            )
        canon.append(_ATTR_ALIASES[key])
    # dedupe while preserving order
    seen = set()
    out = []
    for c in canon:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out

def _parse_period(period: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Parse relative period like '1d', '3w', '2m', '5y' into UTC start/end.
    Months = 30 days, years = 365 days for now.
    """
    m = re.fullmatch(r"\s*(\d+)\s*([dwmy])\s*", period.lower())
    if not m:
        raise ValueError("Invalid period. Use like '1d', '3w', '2m', '5y'.")
    n = int(m.group(1))
    unit = m.group(2)
    end = pd.Timestamp.utcnow().floor("D")
    if unit == "d":
        start = end - pd.Timedelta(days=n)
    elif unit == "w":
        start = end - pd.Timedelta(weeks=n)
    elif unit == "m":
        start = end - pd.Timedelta(days=30 * n)
    else:
        start = end - pd.Timedelta(days=365 * n)
    return start, end

def _parse_date_like(d: date | datetime | str | None) -> pd.Timestamp | None:
    if d is None:
        return None
    ts = pd.to_datetime(d, utc=True)
    # normalize to date precision for consistency
    return pd.Timestamp(ts).floor("D")

def _resolve_range(
    period: str | None, start: date | datetime | str | None, end: date | datetime | str | None
) -> Tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """
    Resolve the requested range. period and start/end are mutually exclusive.
    Returns (start_ts, end_ts) or (None, None) for point-in-time requests.
    """
    if period and (start or end):
        raise ValueError("Provide either 'period' OR 'start'/'end', not both.")
    if period:
        return _parse_period(period)
    s = _parse_date_like(start)
    e = _parse_date_like(end)
    if s and e and s > e:
        raise ValueError("Start date must be <= end date.")
    if s or e:
        if not s:
            # default: end or today if end is not provided
            s = e.floor("D") if e else pd.Timestamp.utcnow().floor("D")
        if not e:
            # default: start or today if start is not provided
            e = s.floor("D") if s else pd.Timestamp.utcnow().floor("D")
        return s, e
    return None, None

def _validate_interval(interval: str) -> str:
    """
    Validate the interval string against allowed intervals.
    """
    iv = interval.strip().lower()
    if iv not in _ALLOWED_INTERVALS:
        raise ValueError(f"Unsupported interval '{interval}'. Allowed: {sorted(_ALLOWED_INTERVALS)}")
    return iv