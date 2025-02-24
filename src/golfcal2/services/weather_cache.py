"""Weather location cache for storing and retrieving location data."""

import os
import sqlite3
from datetime import datetime
from datetime import timedelta
from math import atan2
from math import cos
from math import radians
from math import sin
from math import sqrt
from typing import Any

import requests

from golfcal2.exceptions import handle_errors
from golfcal2.services.weather_types import WeatherError
from golfcal2.utils.logging_utils import EnhancedLoggerMixin


class WeatherLocationCache(EnhancedLoggerMixin):
    """Cache for weather service location data."""
    
    def __init__(self, config):
        """Initialize cache with database connection.
        
        Args:
            config: Application configuration
        """
        super().__init__()
        self.config = config
        self.db_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(self.db_dir, 'weather_cache.db')
        
        # Ensure database exists
        self._init_db()
        
        self.set_log_context(service="weather_cache")
    
    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def _init_db(self) -> None:
        """Initialize database tables."""
        with handle_errors(WeatherError, "weather_cache", "initialize database"):
            # Ensure directory exists
            os.makedirs(self.db_dir, exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create municipalities table for AEMET
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS aemet_municipalities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL,
                        name TEXT NOT NULL,
                        loc_lat REAL NOT NULL,
                        loc_lon REAL NOT NULL,
                        last_updated TIMESTAMP NOT NULL,
                        UNIQUE(code)
                    )
                """)
                
                # Create locations table for IPMA
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ipma_locations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lat REAL NOT NULL,
                        lon REAL NOT NULL,
                        code TEXT NOT NULL,
                        name TEXT NOT NULL,
                        loc_lat REAL NOT NULL,
                        loc_lon REAL NOT NULL,
                        distance REAL NOT NULL,
                        last_updated TIMESTAMP NOT NULL,
                        UNIQUE(lat, lon)
                    )
                """)
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Haversine distance between two points."""
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    def get_municipality(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Get nearest municipality for coordinates."""
        with handle_errors(WeatherError, "weather_cache", "get municipality"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Find nearest municipality using Haversine formula
                cursor.execute("""
                    WITH municipality_distances AS (
                        SELECT 
                            code,
                            name,
                            loc_lat,
                            loc_lon,
                            (6371 * acos(cos(radians(?)) * cos(radians(loc_lat)) * 
                             cos(radians(loc_lon) - radians(?)) + 
                             sin(radians(?)) * sin(radians(loc_lat)))) AS distance
                        FROM aemet_municipalities
                    )
                    SELECT 
                        code,
                        name,
                        loc_lat,
                        loc_lon,
                        distance
                    FROM municipality_distances
                    WHERE distance <= 100
                    ORDER BY distance ASC
                    LIMIT 1
                """, [lat, lon, lat])
                
                result = cursor.fetchone()
                if result:
                    return {
                        'code': result[0],
                        'name': result[1],
                        'loc_lat': result[2],
                        'loc_lon': result[3],
                        'distance': result[4]
                    }
                return None
    
    def cache_municipality(
        self,
        lat: float,
        lon: float,
        municipality_code: str,
        name: str,
        mun_lat: float,
        mun_lon: float,
        distance: float
    ) -> None:
        """Cache municipality data."""
        # Skip if distance is too large
        if distance > 100:
            self.debug(f"Skipping municipality cache due to large distance: {distance}km")
            return
            
        with handle_errors(WeatherError, "weather_cache", "cache municipality"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.now()
                
                # Insert/update municipality
                cursor.execute("""
                    INSERT INTO aemet_municipalities 
                    (municipality_code, name, latitude, longitude, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(municipality_code) DO UPDATE SET
                    name=excluded.name,
                    latitude=excluded.latitude,
                    longitude=excluded.longitude,
                    last_updated=excluded.last_updated
                """, (municipality_code, name, mun_lat, mun_lon, now))
                
                # Insert/update coordinate mapping
                cursor.execute("""
                    INSERT INTO coordinate_mappings
                    (latitude, longitude, service, location_code, distance, last_updated)
                    VALUES (?, ?, 'aemet', ?, ?, ?)
                    ON CONFLICT(latitude, longitude, service) DO UPDATE SET
                    location_code=excluded.location_code,
                    distance=excluded.distance,
                    last_updated=excluded.last_updated
                """, (lat, lon, municipality_code, distance, now))
                
                conn.commit()
    
    def get_ipma_location(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Get cached IPMA location for coordinates."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT code, name, loc_lat, loc_lon, distance FROM ipma_locations WHERE lat = ? AND lon = ?",
                    [lat, lon]
                )
                result = cursor.fetchone()
                if result:
                    code, name, loc_lat, loc_lon, distance = result
                    # Only return if within 100km
                    if distance <= 100:
                        return {
                            'code': code,
                            'name': name,
                            'loc_lat': loc_lat,
                            'loc_lon': loc_lon,
                            'distance': distance
                        }
                return None
        except Exception as e:
            self.error(f"Failed to get IPMA location from cache: {e}")
            return None
            
    def get_aemet_municipality(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Get nearest AEMET municipality for coordinates."""
        with handle_errors(WeatherError, "weather_cache", "get aemet municipality"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if we have any municipalities
                cursor.execute("SELECT COUNT(*) FROM aemet_municipalities")
                count = cursor.fetchone()[0]
                
                if count == 0:
                    self.debug("No municipalities in database, loading static list")
                    self._load_static_municipalities()
                
                # Find nearest municipality using Haversine formula
                cursor.execute("""
                    WITH municipality_distances AS (
                        SELECT 
                            code,
                            name,
                            loc_lat,
                            loc_lon,
                            (6371 * acos(cos(radians(?)) * cos(radians(loc_lat)) * 
                             cos(radians(loc_lon) - radians(?)) + 
                             sin(radians(?)) * sin(radians(loc_lat)))) AS distance
                        FROM aemet_municipalities
                    )
                    SELECT 
                        code,
                        name,
                        loc_lat,
                        loc_lon,
                        distance
                    FROM municipality_distances
                    ORDER BY distance ASC
                    LIMIT 1
                """, [lat, lon, lat])
                
                result = cursor.fetchone()
                if result:
                    return {
                        'code': result[0],
                        'name': result[1],
                        'loc_lat': result[2],
                        'loc_lon': result[3],
                        'distance': result[4]
                    }
                return None
    
    def cache_ipma_location(self, lat: float, lon: float, location_code: str, name: str, 
                          loc_lat: float, loc_lon: float, distance: float) -> None:
        """Cache IPMA location for coordinates."""
        # Skip if distance is too large
        if distance > 100:
            self.debug(f"Skipping location cache due to large distance: {distance}km")
            return
            
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO ipma_locations 
                    (lat, lon, code, name, loc_lat, loc_lon, distance, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, [lat, lon, location_code, name, loc_lat, loc_lon, distance])
                conn.commit()
        except Exception as e:
            self.error(f"Failed to cache IPMA location: {e}")
            
    def cache_aemet_municipality(self, lat: float, lon: float, municipality_code: str, name: str,
                               loc_lat: float, loc_lon: float, distance: float) -> None:
        """Cache AEMET municipality for coordinates."""
        # Skip if distance is too large
        if distance > 100:
            self.debug(f"Skipping municipality cache due to large distance: {distance}km")
            return
            
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO aemet_municipalities
                    (lat, lon, code, name, loc_lat, loc_lon, distance, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, [lat, lon, municipality_code, name, loc_lat, loc_lon, distance])
                conn.commit()
        except Exception as e:
            self.error(f"Failed to cache AEMET municipality: {e}")
    
    def cleanup(self, max_age_days: int = 30) -> None:
        """Clean up old cache entries."""
        with handle_errors(WeatherError, "weather_cache", "cleanup"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cutoff = datetime.now() - timedelta(days=max_age_days)
                
                # Delete old IPMA locations
                cursor.execute("DELETE FROM locations WHERE last_updated < ?", (cutoff,))
                
                conn.commit() 
    
    def _load_static_municipalities(self):
        """Load municipalities from AEMET API into database."""
        try:
            # Check if we already have municipalities
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM aemet_municipalities")
                count = cursor.fetchone()[0]
                
                if count > 0:
                    self.debug(f"Already have {count} municipalities in database")
                    return
                
                # First request to get data URL
                api_url = "https://opendata.aemet.es/opendata/api/maestro/municipios"
                headers = {
                    'Accept': 'application/json',
                    'api_key': self.config.global_config['api_keys']['weather']['aemet']
                }
                
                self.debug("Getting municipality data URL from AEMET API")
                response = requests.get(api_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data_info = response.json()
                    if 'datos' not in data_info:
                        self.error("No data URL in AEMET response")
                        return
                    
                    # Second request to get actual municipality data
                    data_url = data_info['datos']
                    self.debug(f"Fetching municipalities from {data_url}")
                    
                    # Need to use same headers for data request
                    data_response = requests.get(data_url, headers=headers, timeout=10)
                    if data_response.status_code != 200:
                        self.error(f"Failed to fetch municipality data: {data_response.status_code}")
                        return
                    
                    municipalities = data_response.json()
                    self.debug(f"Loading {len(municipalities)} municipalities into database")
                    
                    # Insert all municipalities
                    for municipality in municipalities:
                        try:
                            # Extract numeric ID from the municipality data
                            mun_id = municipality['id']
                            if mun_id.startswith('id'):
                                mun_id = mun_id[2:]  # Remove 'id' prefix
                            
                            cursor.execute("""
                                INSERT INTO aemet_municipalities
                                (code, name, loc_lat, loc_lon, last_updated)
                                VALUES (?, ?, ?, ?, datetime('now'))
                            """, [
                                mun_id.zfill(5),  # Ensure 5 digits with leading zeros
                                municipality['nombre'],
                                float(municipality['latitud_dec']),
                                float(municipality['longitud_dec'])
                            ])
                        except (KeyError, ValueError) as e:
                            self.warning(f"Failed to process municipality: {e}", municipality=municipality)
                            continue
                    
                    conn.commit()
                    self.debug(f"Successfully loaded {len(municipalities)} municipalities")
                else:
                    self.error(f"Failed to get municipality data URL: {response.status_code}")
                    return
                
        except Exception as e:
            self.error(f"Failed to load municipalities: {e!s}", exc_info=True)
            raise 