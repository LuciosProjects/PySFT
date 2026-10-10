"""
Database module for caching financial data.

This module provides SQLite-based caching for indicator metadata, metrics,
and historical price data to reduce redundant API calls.

Schema (simplified 2-tier TTL model):
    - indicator_attributes: Per-attribute storage with timestamps
    - price_history: Historical time series data with per-row timestamps

TTL Rules:
    - Immutable fields (indicator, name, ISIN, inceptionDate, quoteType): never expire
    - All other fields: 15-minute TTL
    - Historical timeseries: immutable except today's data (15-min TTL)
"""

import json
import sqlite3
import threading
import types
from datetime import datetime, timedelta

# Retain legacy typing names as module exports while modernizing annotations.
from typing import (  # noqa: UP035 (preserve legacy typing exports)
    Any,
    List,  # noqa: F401 (legacy module export)
    Optional,  # noqa: F401 (legacy module export)
    Set,  # noqa: F401 (legacy module export)
    Tuple,  # noqa: F401 (legacy module export)
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

import numpy as np
import pandas as pd

from pysft.core.cache_contract import HISTORY_COLUMNS, valid_value
from pysft.core.constants import (
    DB_ENABLED,
    DB_PATH,
    IMMUTABLE_FIELD_NAMES,
    TTL_MINUTES,
)
from pysft.core.price_normalization import (
    PRICE_FIELDS,
    required_price_normalization_version,
)
from pysft.core.structures import _indicator_data

# -----------------------------------------------------------------------------
# Dynamic field categorization from _indicator_data structure
# -----------------------------------------------------------------------------

def _get_timeseries_fields() -> set[str]:
    """
    Dynamically detect timeseries fields by inspecting _indicator_data type hints.
    
    Returns fields whose type includes list[...] (e.g., list[float], list[int], 
    float | list[float], etc.)
    """
    timeseries = set()
    
    try:
        hints = get_type_hints(_indicator_data)
    except Exception:
        # Fallback if type hints can't be resolved
        hints = {f.name: f.type for f in _indicator_data.__dataclass_fields__.values()}
    
    for field_name, field_type in hints.items():
        if _is_list_type(field_type):
            timeseries.add(field_name)
    
    return timeseries


def _is_list_type(field_type) -> bool:
    """Check if a type is or contains list[...]."""
    origin = get_origin(field_type)
    
    # Direct list type: list[X]
    if origin is list:
        return True
    
    # Union type: X | list[X] or Optional[list[X]]
    if origin in [Union, types.UnionType]:
        args = get_args(field_type)
        return any(_is_list_type(arg) for arg in args)
    
    # Check string representation as fallback for forward refs
    type_str = str(field_type)
    return 'list[' in type_str.lower()


def _get_scalar_fields() -> set[str]:
    """Get all non-timeseries fields from _indicator_data."""
    all_fields = set(_indicator_data.__dataclass_fields__.keys())
    timeseries = _get_timeseries_fields()
    return all_fields - timeseries


def _get_all_fields() -> set[str]:
    """Get all fields from _indicator_data."""
    return set(_indicator_data.__dataclass_fields__.keys())


# -----------------------------------------------------------------------------
# Database Manager
# -----------------------------------------------------------------------------

class DatabaseManager:
    """Manages SQLite database for indicator data caching."""
    
    def __init__(self, db_path: str | None = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. If None, uses DB_PATH constant.
        """
        self.db_path = db_path or DB_PATH
        self.connection: sqlite3.Connection | None = None
        self._timeseries_fields = _get_timeseries_fields()
        self._scalar_fields = _get_scalar_fields()
        
        self._initialize_db()
    
    def _initialize_db(self):
        """Create tables and migrate cache validity metadata without deleting data."""
        self.connection = sqlite3.connect(
            self.db_path, 
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        
        cursor = self.connection.cursor()
        # Serialize additive migrations across thread-local connections.
        cursor.execute("BEGIN IMMEDIATE")
        
        # New attribute-based table for scalar fields
        # Each attribute stored as separate row for per-attribute TTL tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indicator_attributes (
                indicator TEXT NOT NULL,
                attribute TEXT NOT NULL,
                value_json TEXT NOT NULL,
                fetched_at TIMESTAMP NOT NULL,
                PRIMARY KEY (indicator, attribute)
            )
        """)
        
        # Price history table for timeseries data
        # Added fetched_at for per-row TTL (today's data expires after 15 min)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                indicator TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                change_pct REAL,
                fetched_at TIMESTAMP NOT NULL,
                PRIMARY KEY (indicator, date)
            )
        """)

        # NULL identifies legacy rows with no trustworthy unit provenance.
        # Migrate only the fetch cache; the security lookup DB is independent.
        for table in ("indicator_attributes", "price_history"):
            columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
            if "normalization_version" not in columns:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN normalization_version INTEGER"
                )
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(indicator_attributes)")}
        if "availability_version" not in columns:
            cursor.execute("ALTER TABLE indicator_attributes ADD COLUMN availability_version INTEGER")
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(price_history)")}
        if "field_fetched_at" not in columns:
            cursor.execute("ALTER TABLE price_history ADD COLUMN field_fetched_at TEXT")
        
        # Create indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_indicator_attributes_indicator 
            ON indicator_attributes(indicator)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_indicator 
            ON price_history(indicator)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_date 
            ON price_history(date)
        """)
        
        self.connection.commit()
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def clear_cache(self) -> dict[str, int]:
        """Delete fetched attributes and history atomically, keeping the schema."""
        if self.connection is None:
            raise RuntimeError("The fetch cache connection is closed.")
        with self.connection:
            counts = {
                "indicator_attributes": self.connection.execute(
                    "SELECT COUNT(*) FROM indicator_attributes"
                ).fetchone()[0],
                "price_history": self.connection.execute(
                    "SELECT COUNT(*) FROM price_history"
                ).fetchone()[0],
            }
            self.connection.execute("DELETE FROM indicator_attributes")
            self.connection.execute("DELETE FROM price_history")
        return counts
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def get_cached_data(
        self, 
        indicator: str, 
        requested_attributes: list[str]
    ) -> tuple[_indicator_data | None, bool]:
        """
        Retrieve cached data for an indicator and check freshness.
        
        Only checks freshness for the requested attributes. Timeseries
        attributes are handled separately via get_cached_dates/get_historical_data.
        
        Args:
            indicator: Indicator symbol/ID
            requested_attributes: List of attributes user requested
            
        Returns:
            Tuple of (cached_data, is_fresh):
                - cached_data: _indicator_data with cached values, None if not found
                - is_fresh: True if all requested scalar attributes are fresh
        """
        if not DB_ENABLED or not self.connection:
            return None, False
        
        cursor = self.connection.cursor()
        
        # Get all cached attributes for this indicator
        cursor.execute("""
            SELECT attribute, value_json, fetched_at, normalization_version, availability_version
            FROM indicator_attributes
            WHERE indicator = ?
        """, (indicator,))
        
        rows = cursor.fetchall()
        if not rows:
            return None, False
        
        # Build attribute -> (value, fetched_at) mapping
        cached_attrs = {}
        invalid_price_attrs = set()
        required_version = self._required_price_version(indicator)
        for attr, value_json, fetched_at, version, availability in rows:
            if attr in PRICE_FIELDS and required_version is not None and version != required_version:
                invalid_price_attrs.add(attr)
                continue
            try:
                value = json.loads(value_json)
                if not valid_value(value):
                    continue
                # Old writers persisted dataclass default zeroes without proof.
                if availability is None and value == 0:
                    continue
                cached_attrs[attr] = (value, fetched_at)
            except json.JSONDecodeError:
                continue
        
        if not cached_attrs:
            return None, False
        
        # Check freshness only for requested scalar attributes
        # (timeseries fields are checked via get_cached_dates)
        now = datetime.now()
        is_fresh = True
        
        for attr in requested_attributes:
            if attr in invalid_price_attrs:
                is_fresh = False
                continue
            # Skip timeseries fields - they're handled separately
            if attr in self._timeseries_fields:
                continue
            
            if attr not in cached_attrs:
                is_fresh = False
                continue
            
            _, fetched_at = cached_attrs[attr]
            if not self._is_attribute_fresh(attr, fetched_at, now):
                is_fresh = False
        
        # Reconstruct _indicator_data from cached values
        data_dict: dict[str, Any] = {"indicator": indicator}
        for attr, (value, _) in cached_attrs.items():
            if not self._is_attribute_fresh(attr, cached_attrs[attr][1], now):
                continue
            # Convert ISO strings back to Timestamps where needed
            if attr == "inceptionDate" and value is not None:
                value = pd.Timestamp(value)
            data_dict[attr] = value
        
        try:
            cached_data = _indicator_data(**data_dict)
        except TypeError:
            # Missing required fields - return partial data
            cached_data = self._build_partial_indicator_data(indicator, data_dict)
        
        return cached_data, is_fresh

    def _required_price_version(self, indicator: str) -> int | None:
        """Determine validity from cached quote type, never the currency alias."""
        quote_type = ""
        if self.connection:
            row = self.connection.execute(
                "SELECT value_json FROM indicator_attributes "
                "WHERE indicator = ? AND attribute = 'quoteType'",
                (indicator,),
            ).fetchone()
            if row:
                try:
                    value = json.loads(row[0])
                    quote_type = value if isinstance(value, str) else ""
                except json.JSONDecodeError:
                    pass
        return required_price_normalization_version(indicator, quote_type)

    def has_outdated_price_history(
        self, indicator: str, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> bool:
        """Detect obsolete interior rows that a date-span check could overlook."""
        if not DB_ENABLED or not self.connection:
            return False
        version = self._required_price_version(indicator)
        if version is None:
            return False
        return self.connection.execute(
            "SELECT 1 FROM price_history WHERE indicator = ? AND date >= ? AND date <= ? "
            "AND (normalization_version IS NULL OR normalization_version != ?) LIMIT 1",
            (indicator, start_date.date(), end_date.date(), version),
        ).fetchone() is not None
    
    def _is_attribute_fresh(
        self, 
        attribute: str, 
        fetched_at: datetime, 
        now: datetime
    ) -> bool:
        """
        Check if an attribute is fresh based on TTL rules.
        
        Args:
            attribute: Field name
            fetched_at: When the attribute was cached
            now: Current time
            
        Returns:
            True if attribute is still fresh
        """
        # Immutable fields never expire
        if attribute in IMMUTABLE_FIELD_NAMES:
            return True
        
        # All other fields: 15-minute TTL
        age = now - fetched_at
        return age <= timedelta(minutes=TTL_MINUTES)
    
    def _build_partial_indicator_data(
        self, 
        indicator: str, 
        data_dict: dict
    ) -> _indicator_data:
        """Build _indicator_data with available fields, using defaults for missing."""
        # Start with defaults
        result = _indicator_data(indicator=indicator)
        
        # Override with cached values
        for field in _indicator_data.__dataclass_fields__:
            if field in data_dict:
                try:
                    setattr(result, field, data_dict[field])
                except (AttributeError, TypeError):
                    pass
        
        return result
    
    def get_cached_dates(self, indicator: str) -> pd.DatetimeIndex:
        """
        Get all cached dates for an indicator's historical data.
        
        Excludes today's date if its cache entry has expired (>15 min old).
        
        Args:
            indicator: Indicator symbol/ID
            
        Returns:
            Set of pd.Timestamp dates available in cache (fresh only)
        """
        if not DB_ENABLED or not self.connection:
            return pd.DatetimeIndex([])
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT date, fetched_at, normalization_version, close, field_fetched_at FROM price_history
            WHERE indicator = ?
            ORDER BY date
        """, (indicator,))
        
        rows = cursor.fetchall()
        if not rows:
            return pd.DatetimeIndex([])
        
        now = datetime.now()
        today = pd.Timestamp.now().floor("D")
        fresh_dates = []
        required_version = self._required_price_version(indicator)
        
        for row_date, fetched_at, version, close, stamps_json in rows:
            if required_version is not None and version != required_version:
                continue
            if not valid_value(close):
                continue
            ts = pd.Timestamp(row_date)
            
            # Today's data: check 15-min TTL
            if ts.floor("D") == today:
                stamps = json.loads(stamps_json) if stamps_json else {}
                stamp = datetime.fromisoformat(stamps["close"]) if "close" in stamps else fetched_at
                age = now - min(stamp, fetched_at)
                if age <= timedelta(minutes=TTL_MINUTES):
                    fresh_dates.append(ts)
            else:
                # Historical data: always fresh (immutable)
                fresh_dates.append(ts)
        
        return pd.DatetimeIndex(fresh_dates)
    
    def cache_indicator_data(
        self, 
        indicator: str, 
        data: _indicator_data,
        fetched_fields: list[str]
    ):
        """
        Cache indicator metadata and metrics.
        
        Immutable fields are only inserted if not already present.
        Volatile fields are always updated with new fetched_at timestamp.
        
        Args:
            indicator: Indicator symbol/ID
            data: Complete indicator data
            fetched_fields: List of fields that were actually fetched
        """
        if not DB_ENABLED or not self.connection:
            return
        
        cursor = self.connection.cursor()
        now = datetime.now()
        
        for field in fetched_fields:
            # Skip timeseries fields - they go to price_history
            if field in self._timeseries_fields:
                continue
            
            value = getattr(data, field, None)
            if not valid_value(value):
                continue
            
            # Serialize value to JSON
            value_json = self._serialize_value(value)
            
            # Check if immutable field already exists
            if field in IMMUTABLE_FIELD_NAMES:
                cursor.execute("""
                    SELECT value_json FROM indicator_attributes 
                    WHERE indicator = ? AND attribute = ?
                """, (indicator, field))
                
                existing = cursor.fetchone()
                if existing and valid_value(json.loads(existing[0])):
                    # Immutable field already cached - skip
                    continue
            
            # Upsert the attribute
            cursor.execute("""
                INSERT OR REPLACE INTO indicator_attributes 
                (indicator, attribute, value_json, fetched_at, normalization_version, availability_version)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (
                indicator, field, value_json, now,
                required_price_normalization_version(indicator, data.quoteType)
                if field in PRICE_FIELDS else None,
            ))
        
        self.connection.commit()
    
    def _serialize_value(self, value) -> str:
        """Serialize a value to JSON string."""
        if isinstance(value, pd.Timestamp):
            return json.dumps(value.isoformat())
        elif isinstance(value, list) and value and isinstance(value[0], pd.Timestamp):
            return json.dumps([v.isoformat() for v in value])
        else:
            return json.dumps(value)
    
    def cache_historical_data(
        self, 
        indicator: str, 
        dates: list[pd.Timestamp],
        open_prices: float | list[float] | None,
        high_prices: float | list[float] | None,
        low_prices: float | list[float] | None,
        close_prices: float | list[float] | None,
        volumes: int | list[int] | None,
        change_pcts: float | list[float] | None = None,
        *,
        normalization_version: int | None = None,
        # market_caps: Optional[List[float]] = None
    ):
        """
        Cache historical price data for an indicator.
        
        Each row stores its own fetched_at timestamp for TTL tracking.
        Today's rows will be refetched when TTL expires.
        
        Args:
            indicator: Indicator symbol/ID
            dates: List of timestamps
            open_prices: Opening prices
            high_prices: High prices
            low_prices: Low prices
            close_prices: Closing prices
            volumes: Trading volumes
            change_pcts: Optional percentage changes
            market_caps: Optional market capitalizations
        """
        if not DB_ENABLED or not self.connection:
            return
        
        cursor = self.connection.cursor()
        now = datetime.now()
        
        # Prepare data for insertion
        rows = []
        def cell(values, index):
            if isinstance(values, (list, np.ndarray)):
                value = values[index] if index < len(values) else None
            else:
                value = values
            return value if valid_value(value) else None

        for i, date in enumerate(dates):
            row_date = date.date() if hasattr(date, "date") else date
            values = [cell(value, i) for value in (
                open_prices, high_prices, low_prices, close_prices, volumes, change_pcts
            )]
            if not any(value is not None for value in values):
                continue
            timestamps: dict[str, str] = {}
            old = cursor.execute(
                "SELECT open, high, low, close, volume, change_pct, fetched_at, "
                "normalization_version, field_fetched_at FROM price_history "
                "WHERE indicator = ? AND date = ?", (indicator, row_date),
            ).fetchone()
            if old and old[7] == normalization_version:
                timestamps = json.loads(old[8]) if old[8] else {
                    column: old[6].isoformat() for column in HISTORY_COLUMNS.values()
                }
                old_values = list(old[:6])
                if not old[8] and self._required_price_version(indicator) is not None:
                    # Legacy fund writers copied close into unsupported OHLC.
                    # Do not certify those cells during a close-only refresh.
                    old_values[:3] = [None, None, None]
                    for column in ("open", "high", "low"):
                        timestamps.pop(column, None)
                values = [
                    value if value is not None else old_values[index]
                    for index, value in enumerate(values)
                ]
            for column, value in zip(HISTORY_COLUMNS.values(), (
                open_prices, high_prices, low_prices, close_prices, volumes, change_pcts
            )):
                if cell(value, i) is not None:
                    timestamps[column] = now.isoformat()
            rows.append((
                indicator,
                row_date,
                *values,
                now,
                normalization_version,
                json.dumps(timestamps),
            ))
        
        # Merge partial provider rows, but never certify old price units with a
        # new normalization version. On version change, replace the entire row.
        cursor.executemany("""
            INSERT OR REPLACE INTO price_history (
                indicator, date, open, high, low, close, 
                volume, change_pct, fetched_at, normalization_version, field_fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        
        self.connection.commit()
    
    def get_historical_data(
        self,
        indicator: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp
    ) -> _indicator_data | None:
        """
        Retrieve historical data for a date range.
        
        Args:
            indicator: Indicator symbol/ID
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            _indicator_data with historical data or None if not found
        """
        if not DB_ENABLED or not self.connection:
            return None
        
        cursor = self.connection.cursor()
        required_version = self._required_price_version(indicator)
        cursor.execute("""
            SELECT date, open, high, low, close, volume, change_pct, fetched_at, field_fetched_at
            FROM price_history
            WHERE indicator = ? AND date >= ? AND date <= ?
            AND (? IS NULL OR normalization_version = ?)
            ORDER BY date
        """, (
            indicator, start_date.date(), end_date.date(),
            required_version, required_version,
        ))
        
        rows = []
        now = datetime.now()
        for date, *values in cursor.fetchall():
            fetched_at, stamps_json = values[-2:]
            values = values[:-2]
            if not stamps_json and required_version is not None:
                values[:3] = [None, None, None]
            if date == now.date():
                stamps = json.loads(stamps_json) if stamps_json else {}
                for index, column in enumerate(HISTORY_COLUMNS.values()):
                    stamp = datetime.fromisoformat(stamps[column]) if column in stamps else fetched_at
                    if now - min(stamp, fetched_at) > timedelta(minutes=TTL_MINUTES):
                        values[index] = None
            if any(value is not None for value in values):
                rows.append((date, *values))
        if not rows:
            # No historical data found for the requested date range
            return None
        
        # Convert to lists for _indicator_data
        date_values, open_values, high_values, low_values, close_values, volume_values, change_pct_values = zip(*rows)
        dates = [pd.Timestamp(d) for d in date_values]
        # dates = pd.DatetimeIndex(dates)
        opens, highs, lows, closes, volumes, change_pcts = [list(x) for x in (open_values, high_values, low_values, close_values, volume_values, change_pct_values)]
        
        # Create indicator data with historical prices
        data = _indicator_data(
            indicator=indicator,
            dates=dates,
            open=opens,
            high=highs,
            low=lows,
            price=closes,
            volume=volumes,
            change_pct=change_pcts,
            # market_cap=market_caps
        )
        
        # Assign last price as today's price if present in close price
        data.last = closes[-1]

        return data

    def missing_history_dates(self, indicator, attributes, dates):
        """Coverage is per requested cell, not merely the outer date span."""
        columns = [HISTORY_COLUMNS.get(field, "close" if field == "last" else None)
                   for field in attributes]
        columns = [column for column in columns if column is not None]
        if not columns or dates.empty:
            return pd.DatetimeIndex([])
        data = self.get_historical_data(indicator, dates[0], dates[-1])
        if data is None:
            return dates
        rows = {
            date: index for index, date in enumerate(data.dates)
        }
        fields = {column: field for field, column in HISTORY_COLUMNS.items()}
        return pd.DatetimeIndex([
            date for date in dates
            if date not in rows or any(
                not valid_value(getattr(data, fields[column])[rows[date]])
                for column in columns
            )
        ])


_thread_local = threading.local()

# Global database manager instance
_db_manager: DatabaseManager | None = None

def get_db_manager() -> DatabaseManager:
    """Get or create a thread-local database manager instance."""
    manager = getattr(_thread_local, "db_manager", None)
    if manager is None:
        manager = DatabaseManager()
        _thread_local.db_manager = manager
    return manager

def close_db():
    """Close global database connection."""
    """Close the current thread's database connection."""
    manager = getattr(_thread_local, "db_manager", None)
    if manager:
        manager.close()
        _thread_local.db_manager = None

def resetDatabase():
    """Reset the database by closing and re-initializing."""
    global _db_manager
    _db_manager = DatabaseManager()

    if _db_manager and _db_manager.connection:
        cursor = _db_manager.connection.cursor()

        # Drop old tables if they exist (fresh schema migration)
        cursor.execute("DROP TABLE IF EXISTS indicators")
        cursor.execute("DROP TABLE IF EXISTS indicator_attributes")
        cursor.execute("DROP TABLE IF EXISTS price_history")

        _db_manager.close()
