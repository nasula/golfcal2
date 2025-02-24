"""Weather database implementation."""

import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any


class WeatherResponseCache:
    """Cache for weather service responses."""
    
    def __init__(self, db_path: str) -> None:
        """Initialize cache with database path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weather_responses (
                    service_type TEXT,
                    latitude REAL,
                    longitude REAL,
                    forecast_start TEXT,
                    forecast_end TEXT,
                    response TEXT,
                    expires TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (service_type, latitude, longitude, forecast_start, forecast_end)
                )
            """)
    
    def get_response(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime
    ) -> dict[str, Any] | None:
        """Get cached response if available and not expired.
        
        Args:
            service_type: Type of weather service
            latitude: Location latitude
            longitude: Location longitude
            start_time: Forecast start time
            end_time: Forecast end time
            
        Returns:
            Cached response data or None if not found/expired
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT response, expires FROM weather_responses
                    WHERE service_type = ? 
                    AND latitude = ?
                    AND longitude = ?
                    AND forecast_start = ?
                    AND forecast_end = ?
                    """,
                    (
                        service_type,
                        latitude,
                        longitude,
                        start_time.isoformat(),
                        end_time.isoformat()
                    )
                )
                row = cursor.fetchone()
                if not row:
                    return None
                    
                response_str, expires_str = row
                expires = datetime.fromisoformat(expires_str)
                
                # Convert current time to UTC for comparison
                now = datetime.now(expires.tzinfo if expires.tzinfo else UTC)
                
                # Check if expired
                if expires < now:
                    self.logger.debug("Cached response expired")
                    return None
                    
                # Parse the response string directly into a dictionary
                response_data = json.loads(response_str)
                if not isinstance(response_data, dict):
                    self.logger.error("Invalid response data format")
                    return None
                    
                return response_data
                
        except Exception as e:
            self.logger.error("Failed to get cached response: %s", str(e))
            return None
    
    def store_response(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        forecast_start: datetime,
        forecast_end: datetime,
        response_data: dict[str, Any],
        expires: datetime
    ) -> None:
        """Store response in cache.
        
        Args:
            service_type: Type of weather service
            latitude: Location latitude
            longitude: Location longitude
            forecast_start: Forecast start time
            forecast_end: Forecast end time
            response_data: Response data to cache
            expires: When the cached data expires
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO weather_responses
                    (service_type, latitude, longitude, forecast_start, forecast_end, response, expires)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        service_type,
                        latitude,
                        longitude,
                        forecast_start.isoformat(),
                        forecast_end.isoformat(),
                        json.dumps(response_data),
                        expires.isoformat()
                    )
                )
        except Exception as e:
            self.logger.error("Failed to store response in cache: %s", str(e))
    
    def clear_expired(self) -> None:
        """Remove expired entries from cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM weather_responses WHERE expires < ?",
                    (datetime.now().isoformat(),)
                )
        except Exception as e:
            self.logger.error("Failed to clear expired entries: %s", str(e))
    
    def clear_all(self) -> None:
        """Clear all entries from cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM weather_responses")
        except Exception as e:
            self.logger.error("Failed to clear cache: %s", str(e))
    
    def list_entries(self) -> list[dict[str, Any]]:
        """List all cache entries.
        
        Returns:
            List of dictionaries containing cache entry details
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        service_type,
                        latitude,
                        longitude,
                        forecast_start,
                        forecast_end,
                        expires,
                        created_at
                    FROM weather_responses
                    ORDER BY created_at DESC
                """)
                
                entries = []
                for row in cursor.fetchall():
                    entries.append({
                        'service': row[0],
                        'location': f"{row[1]:.4f},{row[2]:.4f}",
                        'forecast_period': f"{row[3]} to {row[4]}",
                        'expires': row[5],
                        'created': row[6]
                    })
                
                return entries
                
        except sqlite3.Error as e:
            self.logger.error("Database error while listing entries: %s", str(e))
            return []
        except Exception as e:
            self.logger.error("Error listing cache entries: %s", str(e))
            return []
    
    def clear(self) -> None:
        """Clear all cached responses."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM weather_responses")
                conn.commit()
                self.logger.debug("Weather cache cleared")
        except sqlite3.Error as e:
            self.logger.error("Failed to clear weather cache: %s", str(e))
            raise 
    
    def list_all(self) -> list[dict[str, Any]]:
        """List all cached entries.
        
        Returns:
            List of dictionaries containing cache entry details
        """
        return self.list_entries() 