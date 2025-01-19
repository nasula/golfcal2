"""Weather response caching implementation."""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any

from golfcal2.services.weather_types import WeatherResponse
from golfcal2.utils.logging_utils import LoggerMixin

class WeatherResponseCache(LoggerMixin):
    """Cache for weather responses."""
    
    def __init__(self, db_path: str):
        """Initialize cache.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weather_cache (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    expires TIMESTAMP NOT NULL
                )
            """)
            conn.commit()
    
    def get(self, key: str) -> Optional[WeatherResponse]:
        """Get cached response.
        
        Args:
            key: Cache key
            
        Returns:
            Cached response if found and not expired, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT data, expires FROM weather_cache WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                
                if row:
                    data, expires = row
                    expires_dt = datetime.fromisoformat(expires)
                    
                    if expires_dt > datetime.now():
                        return WeatherResponse(**json.loads(data))
                    else:
                        # Clean up expired entry
                        conn.execute("DELETE FROM weather_cache WHERE key = ?", (key,))
                        conn.commit()
                
                return None
                
        except Exception as e:
            self.error(f"Error getting cached weather: {str(e)}")
            return None
    
    def set(self, key: str, response: WeatherResponse) -> None:
        """Cache weather response.
        
        Args:
            key: Cache key
            response: Weather response to cache
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO weather_cache (key, data, expires) VALUES (?, ?, ?)",
                    (
                        key,
                        json.dumps(response.dict()),
                        response.expires.isoformat()
                    )
                )
                conn.commit()
                
        except Exception as e:
            self.error(f"Error caching weather: {str(e)}")
    
    def clear(self) -> None:
        """Clear all cached responses."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM weather_cache")
                conn.commit()
                
        except Exception as e:
            self.error(f"Error clearing weather cache: {str(e)}")
    
    def cleanup(self) -> None:
        """Remove expired entries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM weather_cache WHERE expires < ?",
                    (datetime.now().isoformat(),)
                )
                conn.commit()
                
        except Exception as e:
            self.error(f"Error cleaning up weather cache: {str(e)}") 