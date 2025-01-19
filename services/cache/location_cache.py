"""Location caching implementation."""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from golfcal2.utils.logging_utils import LoggerMixin

class WeatherLocationCache(LoggerMixin):
    """Cache for weather location data."""
    
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
                CREATE TABLE IF NOT EXISTS location_cache (
                    address TEXT PRIMARY KEY,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    expires TIMESTAMP NOT NULL,
                    metadata TEXT
                )
            """)
            conn.commit()
    
    def get(self, address: str) -> Optional[Tuple[float, float]]:
        """Get cached location coordinates.
        
        Args:
            address: Location address or identifier
            
        Returns:
            Tuple of (latitude, longitude) if found and not expired, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT lat, lon, expires FROM location_cache WHERE address = ?",
                    (address,)
                )
                row = cursor.fetchone()
                
                if row:
                    lat, lon, expires = row
                    expires_dt = datetime.fromisoformat(expires)
                    
                    if expires_dt > datetime.now():
                        return (lat, lon)
                    else:
                        # Clean up expired entry
                        conn.execute("DELETE FROM location_cache WHERE address = ?", (address,))
                        conn.commit()
                
                return None
                
        except Exception as e:
            self.error(f"Error getting cached location: {str(e)}")
            return None
    
    def set(self, address: str, lat: float, lon: float, expires: datetime, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Cache location coordinates.
        
        Args:
            address: Location address or identifier
            lat: Latitude
            lon: Longitude
            expires: Expiration timestamp
            metadata: Optional metadata about the location
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO location_cache (address, lat, lon, expires, metadata) VALUES (?, ?, ?, ?, ?)",
                    (
                        address,
                        lat,
                        lon,
                        expires.isoformat(),
                        json.dumps(metadata) if metadata else None
                    )
                )
                conn.commit()
                
        except Exception as e:
            self.error(f"Error caching location: {str(e)}")
    
    def clear(self) -> None:
        """Clear all cached locations."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM location_cache")
                conn.commit()
                
        except Exception as e:
            self.error(f"Error clearing location cache: {str(e)}")
    
    def cleanup(self) -> None:
        """Remove expired entries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM location_cache WHERE expires < ?",
                    (datetime.now().isoformat(),)
                )
                conn.commit()
                
        except Exception as e:
            self.error(f"Error cleaning up location cache: {str(e)}") 