"""Weather response caching implementation."""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import asdict

from golfcal2.services.weather_types import WeatherResponse, WeatherData
from golfcal2.utils.logging_utils import LoggerMixin

class WeatherResponseCache(LoggerMixin):
    """Cache for weather responses."""
    
    def __init__(self, db_path: str):
        """Initialize cache.
        
        Args:
            db_path: Path to SQLite database file
        """
        super().__init__()  # Initialize LoggerMixin
        self.db_path = db_path
        self._init_db()
        self.set_log_context(component="weather_cache")
    
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
    
    def _make_cache_key(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """Create a cache key from the parameters.
        
        Args:
            service_type: Type of weather service
            latitude: Location latitude
            longitude: Location longitude
            start_time: Start time of forecast
            end_time: End time of forecast
            
        Returns:
            Cache key string
        """
        return f"{service_type}:{latitude:.4f}:{longitude:.4f}:{start_time.isoformat()}:{end_time.isoformat()}"
    
    def get_response(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get cached weather response.
        
        Args:
            service_type: Type of weather service
            latitude: Location latitude
            longitude: Location longitude
            start_time: Start time of forecast
            end_time: End time of forecast
            
        Returns:
            Dictionary containing cached response data if found and not expired
        """
        key = self._make_cache_key(service_type, latitude, longitude, start_time, end_time)
        response = self.get(key)
        if response:
            return {'response': response.data}
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
    ) -> None:
        """Store weather response in cache.
        
        Args:
            service_type: Type of weather service
            latitude: Location latitude
            longitude: Location longitude
            response_data: Weather response data to cache
            forecast_start: Start time of forecast
            forecast_end: End time of forecast
            expires: Expiration time for cached data
        """
        key = self._make_cache_key(service_type, latitude, longitude, forecast_start, forecast_end)
        response = WeatherResponse(
            data=response_data,
            expires=expires
        )
        self.set(key, response)
    
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
                        data_dict = json.loads(data)
                        return WeatherResponse(
                            data=data_dict['data'],
                            expires=expires_dt
                        )
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
                data_dict = {
                    'data': response.data,
                    'expires': response.expires.isoformat()
                }
                conn.execute(
                    "INSERT OR REPLACE INTO weather_cache (key, data, expires) VALUES (?, ?, ?)",
                    (
                        key,
                        json.dumps(data_dict),
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