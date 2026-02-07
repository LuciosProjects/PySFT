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

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Set, get_type_hints, get_origin, get_args, Union
import types
import pandas as pd
import numpy as np
 
from pysft.core.structures import _indicator_data
from pysft.core.constants import (
    DB_PATH,
    DB_ENABLED,
    TTL_MINUTES,
    IMMUTABLE_FIELD_NAMES,
)

import pysft.core.utilities as utils

# -----------------------------------------------------------------------------
# Dynamic field categorization from _indicator_data structure
# -----------------------------------------------------------------------------

def _get_timeseries_fields() -> Set[str]:
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
    if 'list[' in type_str.lower():
        return True
    
    return False


def _get_scalar_fields() -> Set[str]:
    """Get all non-timeseries fields from _indicator_data."""
    all_fields = set(_indicator_data.__dataclass_fields__.keys())
    timeseries = _get_timeseries_fields()
    return all_fields - timeseries


def _get_all_fields() -> Set[str]:
    """Get all fields from _indicator_data."""
    return set(_indicator_data.__dataclass_fields__.keys())


# -----------------------------------------------------------------------------
# Database Manager
# -----------------------------------------------------------------------------

class DatabaseManager:
    """Manages SQLite database for indicator data caching."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. If None, uses DB_PATH constant.
        """
        self.db_path = db_path or DB_PATH
        self.connection: Optional[sqlite3.Connection] = None
        self._timeseries_fields = _get_timeseries_fields()
        self._scalar_fields = _get_scalar_fields()
        
        self._initialize_db()
    
    def _initialize_db(self):
        """Create database tables (drops old tables for fresh schema)."""
        self.connection = sqlite3.connect(
            self.db_path, 
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        
        cursor = self.connection.cursor()
        
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
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def get_cached_data(
        self, 
        indicator: str, 
        requested_attributes: List[str]
    ) -> Tuple[Optional[_indicator_data], bool]:
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
            SELECT attribute, value_json, fetched_at
            FROM indicator_attributes
            WHERE indicator = ?
        """, (indicator,))
        
        rows = cursor.fetchall()
        if not rows:
            return None, False
        
        # Build attribute -> (value, fetched_at) mapping
        cached_attrs = {}
        for attr, value_json, fetched_at in rows:
            try:
                value = json.loads(value_json)
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
        data_dict = {"indicator": indicator}
        for attr, (value, _) in cached_attrs.items():
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
            SELECT date, fetched_at FROM price_history
            WHERE indicator = ?
            ORDER BY date
        """, (indicator,))
        
        rows = cursor.fetchall()
        if not rows:
            return pd.DatetimeIndex([])
        
        now = datetime.now()
        today = pd.Timestamp.now().floor("D")
        fresh_dates = []
        
        for row_date, fetched_at in rows:
            ts = pd.Timestamp(row_date)
            
            # Today's data: check 15-min TTL
            if ts.floor("D") == today:
                age = now - fetched_at
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
        fetched_fields: List[str]
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
            if value is None and field not in IMMUTABLE_FIELD_NAMES:
                continue  # Don't cache None for volatile fields
            
            # Serialize value to JSON
            value_json = self._serialize_value(value)
            
            # Check if immutable field already exists
            if field in IMMUTABLE_FIELD_NAMES:
                cursor.execute("""
                    SELECT 1 FROM indicator_attributes 
                    WHERE indicator = ? AND attribute = ?
                """, (indicator, field))
                
                if cursor.fetchone():
                    # Immutable field already cached - skip
                    continue
            
            # Upsert the attribute
            cursor.execute("""
                INSERT OR REPLACE INTO indicator_attributes 
                (indicator, attribute, value_json, fetched_at)
                VALUES (?, ?, ?, ?)
            """, (indicator, field, value_json, now))
        
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
        dates: List[pd.Timestamp],
        open_prices: List[float],
        high_prices: List[float],
        low_prices: List[float],
        close_prices: List[float],
        volumes: List[int],
        change_pcts: Optional[List[float]] = None
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
        for i, date in enumerate(dates):
            rows.append((
                indicator,
                date.date() if hasattr(date, 'date') else date,
                utils._to_float(open_prices[i]) if (type(open_prices) in [list, np.ndarray]) and i < len(open_prices) else utils._to_float(open_prices),
                utils._to_float(high_prices[i]) if (type(high_prices) in [list, np.ndarray]) and i < len(high_prices) else utils._to_float(high_prices),
                utils._to_float(low_prices[i]) if (type(low_prices) in [list, np.ndarray]) and i < len(low_prices) else utils._to_float(low_prices),
                utils._to_float(close_prices[i]) if (type(close_prices) in [list, np.ndarray]) and i < len(close_prices) else utils._to_float(close_prices),
                utils._to_int(volumes[i]) if (type(volumes) in [list, np.ndarray]) and i < len(volumes) else utils._to_int(volumes),
                utils._to_float(change_pcts[i]) if change_pcts and (type(change_pcts) in [list, np.ndarray]) and i < len(change_pcts) else utils._to_float(change_pcts),
                # market_caps[i] if market_caps and i < len(market_caps) else None,
                now  # fetched_at timestamp
            ))
        
        # Use INSERT OR REPLACE to handle duplicates (including today's refresh)
        cursor.executemany("""
            INSERT OR REPLACE INTO price_history (
                indicator, date, open, high, low, close, 
                volume, change_pct, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        
        self.connection.commit()
    
    def get_historical_data(
        self,
        indicator: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp
    ) -> Optional[_indicator_data]:
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
        cursor.execute("""
            SELECT date, open, high, low, close, volume, change_pct
            FROM price_history
            WHERE indicator = ? AND date >= ? AND date <= ?
            ORDER BY date
        """, (indicator, start_date.date(), end_date.date()))
        
        rows = cursor.fetchall()
        if not rows:
            # No historical data found for the requested date range
            return None
        
        # Convert to lists for _indicator_data
        dates, opens, highs, lows, closes, volumes, change_pcts = zip(*rows)
        dates = [pd.Timestamp(d) for d in dates]
        # dates = pd.DatetimeIndex(dates)
        opens, highs, lows, closes, volumes, change_pcts = [list(x) for x in (opens, highs, lows, closes, volumes, change_pcts)]
        
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
        data.last = closes[-1] if dates[-1] == pd.Timestamp(datetime.now().date()) else 0.0

        return data


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get or create global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def close_db():
    """Close global database connection."""
    global _db_manager
    if _db_manager:
        _db_manager.close()
        _db_manager = None

def resetDatabase():
    """Reset the database by closing and re-initializing."""
    _db_manager = DatabaseManager()

    if _db_manager:
        cursor = _db_manager.connection.cursor()

        # Drop old tables if they exist (fresh schema migration)
        cursor.execute("DROP TABLE IF EXISTS indicators")
        cursor.execute("DROP TABLE IF EXISTS indicator_attributes")
        cursor.execute("DROP TABLE IF EXISTS price_history")

        _db_manager.close()
