"""Centralized cache for weather service location data."""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo
import math

from golfcal2.utils.logging_utils import EnhancedLoggerMixin

class WeatherLocationCache(EnhancedLoggerMixin):
    """Cache for weather service location data (municipalities, grid points, city IDs, etc.)."""
    
    def __init__(self, db_path: str = 'weather_locations.db'):
        """Initialize the cache."""
        super().__init__()
        self.db_path = db_path
        self.set_log_context(service="weather_location_cache")
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS location_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_type TEXT NOT NULL,      -- e.g., 'aemet', 'met', 'openweather'
                    set_type TEXT NOT NULL,          -- e.g., 'municipalities', 'grid_points', 'cities'
                    data TEXT NOT NULL,              -- JSON string of location data
                    expires TEXT NOT NULL,           -- ISO format UTC
                    last_modified TEXT NOT NULL,     -- ISO format UTC
                    UNIQUE(service_type, set_type)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS location_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_type TEXT NOT NULL,
                    location_id TEXT NOT NULL,       -- Service-specific ID
                    location_name TEXT,              -- Human readable name
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    metadata TEXT,                   -- JSON string for additional data
                    last_modified TEXT NOT NULL,     -- ISO format UTC
                    UNIQUE(service_type, latitude, longitude)
                )
            """)
            
            # Create indices for efficient lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_location_coords ON location_mappings(latitude, longitude)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_location_service ON location_mappings(service_type, location_id)")
    
    def store_location_set(
        self,
        service_type: str,
        set_type: str,
        data: List[Dict[str, Any]],
        expires_in: timedelta = timedelta(days=30)  # Default 30 day expiry
    ) -> None:
        """Store a set of locations (e.g., all AEMET municipalities)."""
        try:
            now = datetime.now(ZoneInfo("UTC"))
            expires = now + expires_in
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO location_sets
                    (service_type, set_type, data, expires, last_modified)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    service_type,
                    set_type,
                    json.dumps(data),
                    expires.isoformat(),
                    now.isoformat()
                ))
                
                self.logger.info(
                    "Stored location set",
                    extra={
                        'service': service_type,
                        'set_type': set_type,
                        'count': len(data),
                        'expires': expires.isoformat()
                    }
                )
        except Exception as e:
            self.logger.error(
                "Failed to store location set",
                extra={
                    'error': str(e),
                    'service': service_type,
                    'set_type': set_type
                }
            )
            raise
    
    def get_location_set(
        self,
        service_type: str,
        set_type: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get a set of locations if not expired."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT data, expires
                    FROM location_sets
                    WHERE service_type = ?
                    AND set_type = ?
                    AND expires > datetime('now', 'utc')
                """, (service_type, set_type))
                
                row = cursor.fetchone()
                if row:
                    data = json.loads(row[0])
                    self.logger.info(
                        "Cache hit for location set",
                        extra={
                            'service': service_type,
                            'set_type': set_type,
                            'count': len(data),
                            'expires': row[1]
                        }
                    )
                    return data
                
                self.logger.info(
                    "Cache miss for location set",
                    extra={
                        'service': service_type,
                        'set_type': set_type
                    }
                )
                return None
                
        except Exception as e:
            self.logger.error(
                "Failed to get location set",
                extra={
                    'error': str(e),
                    'service': service_type,
                    'set_type': set_type
                }
            )
            return None
    
    def store_location_mapping(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        location_id: str,
        location_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Store a mapping between coordinates and a service-specific location."""
        try:
            now = datetime.now(ZoneInfo("UTC"))
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO location_mappings
                    (service_type, location_id, location_name, latitude, longitude, metadata, last_modified)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    service_type,
                    location_id,
                    location_name,
                    latitude,
                    longitude,
                    json.dumps(metadata) if metadata else None,
                    now.isoformat()
                ))
                
                self.logger.info(
                    "Stored location mapping",
                    extra={
                        'service': service_type,
                        'location_id': location_id,
                        'location_name': location_name,
                        'coords': (latitude, longitude)
                    }
                )
        except Exception as e:
            self.logger.error(
                "Failed to store location mapping",
                extra={
                    'error': str(e),
                    'service': service_type,
                    'location_id': location_id
                }
            )
            raise
    
    def get_nearest_location(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        max_distance_km: float = 50.0  # Default 50km max distance
    ) -> Optional[Dict[str, Any]]:
        """Find nearest cached location for given coordinates."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get all locations for this service
                cursor = conn.execute("""
                    SELECT location_id, location_name, latitude, longitude, metadata
                    FROM location_mappings
                    WHERE service_type = ?
                """, (service_type,))
                
                nearest = None
                min_distance = float('inf')
                
                for row in cursor:
                    loc_id, loc_name, loc_lat, loc_lon, metadata = row
                    distance = self._haversine_distance(latitude, longitude, loc_lat, loc_lon)
                    
                    if distance < min_distance and distance <= max_distance_km:
                        min_distance = distance
                        nearest = {
                            'id': loc_id,
                            'name': loc_name,
                            'latitude': loc_lat,
                            'longitude': loc_lon,
                            'distance': distance,
                            'metadata': json.loads(metadata) if metadata else None
                        }
                
                if nearest:
                    self.logger.info(
                        "Found nearest location",
                        extra={
                            'service': service_type,
                            'location': nearest['name'],
                            'distance_km': nearest['distance']
                        }
                    )
                    return nearest
                
                self.logger.info(
                    "No nearby location found",
                    extra={
                        'service': service_type,
                        'coords': (latitude, longitude),
                        'max_distance': max_distance_km
                    }
                )
                return None
                
        except Exception as e:
            self.logger.error(
                "Failed to get nearest location",
                extra={
                    'error': str(e),
                    'service': service_type,
                    'coords': (latitude, longitude)
                }
            )
            return None
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance between two points on the earth.
        
        Args:
            lat1: Latitude of first point in degrees
            lon1: Longitude of first point in degrees
            lat2: Latitude of second point in degrees
            lon2: Longitude of second point in degrees
            
        Returns:
            Distance between points in kilometers
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r 
    
   