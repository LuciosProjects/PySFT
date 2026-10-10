"""Availability and date-aligned merging shared by cache reads and fresh results."""

import copy
from typing import Any

import numpy as np
import pandas as pd

from pysft.core.structures import _indicator_data

HISTORY_COLUMNS = {
    "open": "open", "high": "high", "low": "low", "price": "close",
    "volume": "volume", "change_pct": "change_pct",
}
HISTORY_FIELDS = set(HISTORY_COLUMNS) | {"last"}


def available_fields(data: _indicator_data) -> set[str]:
    """Only explicit, usable values count; zero is valid, sentinels are not."""
    result = set()
    for field in data._present_fields:
        value = getattr(data, field)
        values = value if isinstance(value, (list, np.ndarray)) else [value]
        if len(values) and any(valid_value(item) for item in values):
            result.add(field)
    return result


def valid_value(value: Any) -> bool:
    if value is None or isinstance(value, str) and value.strip().upper() in {
        "", "N/A", "NA", "NONE", "NULL", "UNKNOWN",
    }:
        return False
    return not bool(pd.isna(value))


def merge_data(
    cached: _indicator_data | None, fresh: _indicator_data | None,
    start: pd.Timestamp | None = None, end: pd.Timestamp | None = None,
) -> _indicator_data:
    """Merge by field and date, preserving valid cached cells on partial refresh."""
    merged = copy.deepcopy(cached) if cached is not None else _indicator_data()
    if fresh is not None:
        fields = available_fields(fresh)
        for field in fields - HISTORY_FIELDS - {"dates"}:
            setattr(merged, field, getattr(fresh, field))
    else:
        fields = set()
    rows: dict[pd.Timestamp, dict[str, Any]] = {}
    for data, supplied in (
        (cached, available_fields(cached) if cached is not None else set()),
        (fresh, fields),
    ):
        if data is None:
            continue
        dates = data.dates if isinstance(data.dates, (list, np.ndarray)) else [data.dates]
        for index, date in enumerate(dates or []):
            ts = pd.Timestamp(date).tz_localize(None).normalize()
            if start is not None and end is not None and not start <= ts <= end:
                continue
            row = rows.setdefault(ts, {})
            for field in supplied & set(HISTORY_COLUMNS):
                value = getattr(data, field)
                if isinstance(value, (list, np.ndarray)):
                    value = value[index] if index < len(value) else None
                if valid_value(value):
                    row[field] = value
    rows = {date: row for date, row in rows.items() if row}
    if rows:
        merged.dates = sorted(rows)
        for field in HISTORY_COLUMNS:
            if any(field in row for row in rows.values()):
                setattr(merged, field, [rows[date].get(field) for date in merged.dates])
        if "price" in rows[merged.dates[-1]]:
            merged.last = rows[merged.dates[-1]]["price"]
    elif fresh is not None:
        dates = fresh.dates if isinstance(fresh.dates, list) else [fresh.dates]
        merged.dates = sorted({
            pd.Timestamp(date).tz_localize(None).normalize() for date in dates or []
            if start is None or end is None or start <= pd.Timestamp(date).tz_localize(None) <= end
        })
    return merged
