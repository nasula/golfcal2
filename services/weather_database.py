"""Weather database implementation."""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import logging

class WeatherResponseCache:
    """Cache for weather service responses."""
    
    def __init__(self, db_path: str):
        """Initialize cache with database path."""
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS weather_responses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        service_type TEXT NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        response_data TEXT NOT NULL,
                        forecast_start TEXT NOT NULL,
                        forecast_end TEXT NOT NULL,
                        expires TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(service_type, latitude, longitude, forecast_start, forecast_end)
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            self.logger.error("Failed to initialize database: %s", str(e))
            raise
    
    def get_response(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT response_data, expires
                    FROM weather_responses
                    WHERE service_type = ? 
                    AND latitude = ?
                    AND longitude = ?
                    AND forecast_start <= ?
                    AND forecast_end >= ?
                    AND expires > ?
                """, (
                    service_type,
                    latitude,
                    longitude,
                    start_time.isoformat(),
                    end_time.isoformat(),
                    datetime.now().isoformat()
                ))
                row = cursor.fetchone()
                
                if row:
                    response_data = json.loads(row[0])
                    expires = datetime.fromisoformat(row[1])
                    
                    # Return response with metadata
                    return {
                        'response': response_data,
                        'location': f"{latitude},{longitude}",
                        'expires': expires
                    }
                
                return None
                
        except sqlite3.Error as e:
            self.logger.error("Database error while getting response: %s", str(e))
            return None
        except Exception as e:
            self.logger.error("Error getting response: %s", str(e))
            return None
    
    def store_response(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        response_data: Dict[str, Any],
        forecast_start: datetime,
        forecast_end: datetime,
        expires: datetime
    ) -> bool:
        """Store response in cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO weather_responses (
                        service_type,
                        latitude,
                        longitude,
                        response_data,
                        forecast_start,
                        forecast_end,
                        expires
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    service_type,
                    latitude,
                    longitude,
                    json.dumps(response_data),
                    forecast_start.isoformat(),
                    forecast_end.isoformat(),
                    expires.isoformat()
                ))
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            self.logger.error("Database error while storing response: %s", str(e))
            return False
        except Exception as e:
            self.logger.error("Error storing response: %s", str(e))
            return False
    
    def cleanup_expired(self) -> int:
        """Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM weather_responses
                    WHERE expires < ?
                """, (datetime.now().isoformat(),))
                deleted = cursor.rowcount
                conn.commit()
                return deleted
                
        except sqlite3.Error as e:
            self.logger.error("Database error while cleaning up: %s", str(e))
            return 0
        except Exception as e:
            self.logger.error("Error cleaning up cache: %s", str(e))
            return 0
    
    def list_entries(self) -> List[Dict[str, Any]]:
        """List all cache entries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
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
                        'location': f"{row[1]},{row[2]}",
                        'start_time': row[3],
                        'end_time': row[4],
                        'expires': row[5],
                        'created_at': row[6]
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