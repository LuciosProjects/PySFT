"""
Database module for caching financial data.

This module provides SQLite-based caching for indicator metadata, metrics,
and historical price data to reduce redundant API calls.

Schema:
    - indicators: Stores metadata and metrics with timestamps
    - price_history: Stores historical time series data
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Set
from pathlib import Path
import pandas as pd

from pysft.core.structures import _indicator_data
from pysft.core.constants import (
    DB_PATH, 
    DB_ENABLED,
    IMMUTABLE_FIELDS,
    LONGTERM_TTL_FIELDS,
    MEDIUM_TTL_FIELDS,
    SHORT_TTL_FIELDS,
    LONGTERM_TTL_DAYS,
    MEDIUM_TTL_DAYS,
    SHORT_TTL_DAYS,
)


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
        
        if DB_ENABLED:
            self._initialize_db()
    
    def _initialize_db(self):
        """Create database tables if they don't exist."""
        self.connection = sqlite3.connect(
            self.db_path, 
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        
        cursor = self.connection.cursor()
        
        # Indicators table for metadata and metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indicators (
                indicator TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                immutable_fetched_at TIMESTAMP,
                longterm_fetched_at TIMESTAMP,
                medium_fetched_at TIMESTAMP,
                short_fetched_at TIMESTAMP,
                last_fetched_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Price history table for time series
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
                market_cap REAL,
                PRIMARY KEY (indicator, date)
            )
        """)
        
        # Create indexes for efficient queries
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
        
        Args:
            indicator: Indicator symbol/ID
            requested_attributes: List of attributes user requested
            
        Returns:
            Tuple of (cached_data, is_fresh):
                - cached_data: _indicator_data if found, None otherwise
                - is_fresh: True if all requested attributes are fresh
        """
        if not DB_ENABLED or not self.connection:
            return None, False
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT data_json, immutable_fetched_at, longterm_fetched_at,
                   medium_fetched_at, short_fetched_at, last_fetched_at
            FROM indicators
            WHERE indicator = ?
        """, (indicator,))
        
        row = cursor.fetchone()
        if not row:
            return None, False
        
        data_json, immutable_ts, longterm_ts, medium_ts, short_ts, last_ts = row
        
        # Deserialize cached data
        data_dict = json.loads(data_json)
        cached_data = self._dict_to_indicator_data(data_dict)
        
        # Check freshness for requested attributes
        now = datetime.now()
        is_fresh = self._check_freshness(
            requested_attributes,
            immutable_ts,
            longterm_ts,
            medium_ts,
            short_ts,
            now
        )
        
        return cached_data, is_fresh
    
    def _check_freshness(
        self,
        requested_attributes: List[str],
        immutable_ts: Optional[datetime],
        longterm_ts: Optional[datetime],
        medium_ts: Optional[datetime],
        short_ts: Optional[datetime],
        now: datetime
    ) -> bool:
        """
        Check if requested attributes are within TTL limits.
        
        Returns:
            True if all requested attributes are fresh
        """
        for attr in requested_attributes:
            # Immutable fields - no expiry if ever fetched
            if attr in IMMUTABLE_FIELDS:
                if immutable_ts is None:
                    return False
                # Immutable = always fresh once fetched
                continue
            
            # Long-term fields - 1 year TTL
            if attr in LONGTERM_TTL_FIELDS:
                if longterm_ts is None:
                    return False
                age = now - longterm_ts
                if age > timedelta(days=LONGTERM_TTL_DAYS):
                    return False
                continue
            
            # Medium-term fields - 90 days TTL
            if attr in MEDIUM_TTL_FIELDS:
                if medium_ts is None:
                    return False
                age = now - medium_ts
                if age > timedelta(days=MEDIUM_TTL_DAYS):
                    return False
                continue
            
            # Short-term fields - 7 days TTL
            if attr in SHORT_TTL_FIELDS:
                if short_ts is None:
                    return False
                age = now - short_ts
                if age > timedelta(days=SHORT_TTL_DAYS):
                    return False
                continue
            
            # Price fields (current) - always stale, need fresh fetch
            # Historical price fields checked separately via get_cached_dates
            return False
        
        return True
    
    def get_cached_dates(self, indicator: str) -> Set[pd.Timestamp]:
        """
        Get all cached dates for an indicator's historical data.
        
        Args:
            indicator: Indicator symbol/ID
            
        Returns:
            Set of pd.Timestamp dates available in cache
        """
        if not DB_ENABLED or not self.connection:
            return set()
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT date FROM price_history
            WHERE indicator = ?
            ORDER BY date
        """, (indicator,))
        
        rows = cursor.fetchall()
        return {pd.Timestamp(row[0]) for row in rows}
    
    def cache_indicator_data(
        self, 
        indicator: str, 
        data: _indicator_data,
        fetched_fields: List[str]
    ):
        """
        Cache indicator metadata and metrics.
        
        Args:
            indicator: Indicator symbol/ID
            data: Complete indicator data
            fetched_fields: List of fields that were actually fetched (to update timestamps)
        """
        if not DB_ENABLED or not self.connection:
            return
        
        # Serialize data to JSON
        data_dict = self._indicator_data_to_dict(data)
        data_json = json.dumps(data_dict)
        
        now = datetime.now()
        
        # Determine which timestamp columns to update based on fetched fields
        update_immutable = any(f in IMMUTABLE_FIELDS for f in fetched_fields)
        update_longterm = any(f in LONGTERM_TTL_FIELDS for f in fetched_fields)
        update_medium = any(f in MEDIUM_TTL_FIELDS for f in fetched_fields)
        update_short = any(f in SHORT_TTL_FIELDS for f in fetched_fields)
        
        cursor = self.connection.cursor()
        
        # Check if record exists
        cursor.execute("SELECT indicator FROM indicators WHERE indicator = ?", (indicator,))
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update existing record
            updates = ["data_json = ?", "last_fetched_at = ?"]
            params = [data_json, now]
            
            if update_immutable:
                updates.append("immutable_fetched_at = ?")
                params.append(now)
            if update_longterm:
                updates.append("longterm_fetched_at = ?")
                params.append(now)
            if update_medium:
                updates.append("medium_fetched_at = ?")
                params.append(now)
            if update_short:
                updates.append("short_fetched_at = ?")
                params.append(now)
            
            params.append(indicator)
            
            cursor.execute(f"""
                UPDATE indicators 
                SET {', '.join(updates)}
                WHERE indicator = ?
            """, params)
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO indicators (
                    indicator, data_json, 
                    immutable_fetched_at, longterm_fetched_at,
                    medium_fetched_at, short_fetched_at,
                    last_fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                indicator, 
                data_json,
                now if update_immutable else None,
                now if update_longterm else None,
                now if update_medium else None,
                now if update_short else None,
                now
            ))
        
        self.connection.commit()
    
    def cache_historical_data(
        self, 
        indicator: str, 
        dates: List[pd.Timestamp],
        open_prices: List[float],
        high_prices: List[float],
        low_prices: List[float],
        close_prices: List[float],
        volumes: List[int],
        change_pcts: Optional[List[float]] = None,
        market_caps: Optional[List[float]] = None
    ):
        """
        Cache historical price data for an indicator.
        
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
        
        # Prepare data for insertion
        rows = []
        for i, date in enumerate(dates):
            rows.append((
                indicator,
                date.date(),
                open_prices[i] if i < len(open_prices) else None,
                high_prices[i] if i < len(high_prices) else None,
                low_prices[i] if i < len(low_prices) else None,
                close_prices[i] if i < len(close_prices) else None,
                volumes[i] if i < len(volumes) else None,
                change_pcts[i] if change_pcts and i < len(change_pcts) else None,
                market_caps[i] if market_caps and i < len(market_caps) else None
            ))
        
        # Use INSERT OR REPLACE to handle duplicates
        cursor.executemany("""
            INSERT OR REPLACE INTO price_history (
                indicator, date, open, high, low, close, 
                volume, change_pct, market_cap
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
            _indicator_data with historical data or None if incomplete
        """
        if not DB_ENABLED or not self.connection:
            return None
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT date, open, high, low, close, volume, change_pct, market_cap
            FROM price_history
            WHERE indicator = ? AND date >= ? AND date <= ?
            ORDER BY date
        """, (indicator, start_date.date(), end_date.date()))
        
        rows = cursor.fetchall()
        if not rows:
            return None
        
        # Convert to lists for _indicator_data
        dates = [pd.Timestamp(row[0]) for row in rows]
        opens = [row[1] for row in rows]
        highs = [row[2] for row in rows]
        lows = [row[3] for row in rows]
        closes = [row[4] for row in rows]
        volumes = [row[5] for row in rows]
        change_pcts = [row[6] for row in rows]
        market_caps = [row[7] for row in rows]
        
        # Create indicator data with historical prices
        data = _indicator_data(
            indicator=indicator,
            dates=dates,
            open=opens,
            high=highs,
            low=lows,
            last=closes[-1],  # last traded prices
            volume=volumes,
            change_pct=change_pcts,
            market_cap=market_caps
        )
        
        return data
    
    def _indicator_data_to_dict(self, data: _indicator_data) -> dict:
        """Convert _indicator_data to JSON-serializable dict."""
        result = {}
        for field in data.__dataclass_fields__:
            value = getattr(data, field)
            
            # Handle special types
            if isinstance(value, pd.Timestamp):
                result[field] = value.isoformat()
            elif isinstance(value, list) and value and isinstance(value[0], pd.Timestamp):
                result[field] = [v.isoformat() for v in value]
            elif isinstance(value, (list, tuple)):
                result[field] = list(value)
            else:
                result[field] = value
        
        return result
    
    def _dict_to_indicator_data(self, data_dict: dict) -> _indicator_data:
        """Convert dict back to _indicator_data."""
        # Convert ISO strings back to Timestamps
        if 'dates' in data_dict and isinstance(data_dict['dates'], list):
            data_dict['dates'] = [pd.Timestamp(d) for d in data_dict['dates']]
        
        return _indicator_data(**data_dict)


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
