"""Weather location cache for storing and retrieving location data."""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from math import radians, sin, cos, sqrt, atan2

from golfcal2.utils.logging_utils import EnhancedLoggerMixin
from golfcal2.exceptions import WeatherError, handle_errors

class WeatherLocationCache(EnhancedLoggerMixin):
    """Cache for weather service location data."""
    
    def __init__(self):
        """Initialize cache."""
        super().__init__()
        self.db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'weather_locations.db')
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database tables."""
        with handle_errors(WeatherError, "weather_cache", "initialize database"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create municipalities table for AEMET
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS municipalities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        municipality_code TEXT NOT NULL,
                        name TEXT NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        last_updated TIMESTAMP NOT NULL,
                        UNIQUE(municipality_code)
                    )
                """)
                
                # Create locations table for IPMA
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS locations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        location_code TEXT NOT NULL,
                        name TEXT NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        last_updated TIMESTAMP NOT NULL,
                        UNIQUE(location_code)
                    )
                """)
                
                # Create coordinates to location mapping table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS coordinate_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        service TEXT NOT NULL,
                        location_code TEXT NOT NULL,
                        distance REAL NOT NULL,
                        last_updated TIMESTAMP NOT NULL,
                        UNIQUE(latitude, longitude, service)
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
    
    def get_municipality(self, lat: float, lon: float, max_age_days: int = 30, max_distance_km: float = 10.0) -> Optional[Dict[str, Any]]:
        """Get nearest municipality for coordinates."""
        with handle_errors(WeatherError, "weather_cache", "get municipality"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Calculate cutoff time
                cutoff = datetime.now() - timedelta(days=max_age_days)
                
                # Find the nearest municipality within max_distance
                cursor.execute("""
                    WITH location_distances AS (
                        SELECT 
                            m.municipality_code,
                            m.name,
                            m.latitude,
                            m.longitude,
                            (6371 * acos(cos(radians(?)) * cos(radians(m.latitude)) * 
                             cos(radians(m.longitude) - radians(?)) + 
                             sin(radians(?)) * sin(radians(m.latitude)))) AS distance
                        FROM municipalities m
                        WHERE m.last_updated > ?
                    )
                    SELECT 
                        municipality_code,
                        name,
                        latitude,
                        longitude,
                        distance
                    FROM location_distances
                    WHERE distance <= ?
                    ORDER BY distance ASC
                    LIMIT 1
                """, (lat, lon, lat, cutoff, max_distance_km))
                
                result = cursor.fetchone()
                if result:
                    # Cache this mapping for future use
                    self.cache_municipality(
                        lat=lat,
                        lon=lon,
                        municipality_code=result[0],
                        name=result[1],
                        mun_lat=result[2],
                        mun_lon=result[3],
                        distance=result[4]
                    )
                    return {
                        'code': result[0],
                        'name': result[1],
                        'latitude': result[2],
                        'longitude': result[3],
                        'distance': result[4]
                    }
                
                # If no result within max_distance, try to find any nearest municipality
                cursor.execute("""
                    WITH location_distances AS (
                        SELECT 
                            m.municipality_code,
                            m.name,
                            m.latitude,
                            m.longitude,
                            (6371 * acos(cos(radians(?)) * cos(radians(m.latitude)) * 
                             cos(radians(m.longitude) - radians(?)) + 
                             sin(radians(?)) * sin(radians(m.latitude)))) AS distance
                        FROM municipalities m
                        WHERE m.last_updated > ?
                    )
                    SELECT 
                        municipality_code,
                        name,
                        latitude,
                        longitude,
                        distance
                    FROM location_distances
                    ORDER BY distance ASC
                    LIMIT 1
                """, (lat, lon, lat, cutoff))
                
                result = cursor.fetchone()
                if result:
                    # Cache this mapping for future use
                    self.cache_municipality(
                        lat=lat,
                        lon=lon,
                        municipality_code=result[0],
                        name=result[1],
                        mun_lat=result[2],
                        mun_lon=result[3],
                        distance=result[4]
                    )
                    return {
                        'code': result[0],
                        'name': result[1],
                        'latitude': result[2],
                        'longitude': result[3],
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
        with handle_errors(WeatherError, "weather_cache", "cache municipality"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.now()
                
                # Insert/update municipality
                cursor.execute("""
                    INSERT INTO municipalities 
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
    
    def get_ipma_location(self, lat: float, lon: float, max_age_days: int = 30, max_distance_km: float = 10.0) -> Optional[Dict[str, Any]]:
        """Get nearest IPMA location for coordinates."""
        with handle_errors(WeatherError, "weather_cache", "get ipma location"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Calculate cutoff time
                cutoff = datetime.now() - timedelta(days=max_age_days)
                
                # Find the nearest location within max_distance
                cursor.execute("""
                    WITH location_distances AS (
                        SELECT 
                            l.location_code,
                            l.name,
                            l.latitude,
                            l.longitude,
                            (6371 * acos(cos(radians(?)) * cos(radians(l.latitude)) * 
                             cos(radians(l.longitude) - radians(?)) + 
                             sin(radians(?)) * sin(radians(l.latitude)))) AS distance
                        FROM locations l
                        WHERE l.last_updated > ?
                    )
                    SELECT 
                        location_code,
                        name,
                        latitude,
                        longitude,
                        distance
                    FROM location_distances
                    WHERE distance <= ?
                    ORDER BY distance ASC
                    LIMIT 1
                """, (lat, lon, lat, cutoff, max_distance_km))
                
                result = cursor.fetchone()
                if result:
                    # Cache this mapping for future use
                    self.cache_ipma_location(
                        lat=lat,
                        lon=lon,
                        location_code=result[0],
                        name=result[1],
                        loc_lat=result[2],
                        loc_lon=result[3],
                        distance=result[4]
                    )
                    return {
                        'code': result[0],
                        'name': result[1],
                        'latitude': result[2],
                        'longitude': result[3],
                        'distance': result[4]
                    }
                
                # If no result within max_distance, try to find any nearest location
                cursor.execute("""
                    WITH location_distances AS (
                        SELECT 
                            l.location_code,
                            l.name,
                            l.latitude,
                            l.longitude,
                            (6371 * acos(cos(radians(?)) * cos(radians(l.latitude)) * 
                             cos(radians(l.longitude) - radians(?)) + 
                             sin(radians(?)) * sin(radians(l.latitude)))) AS distance
                        FROM locations l
                        WHERE l.last_updated > ?
                    )
                    SELECT 
                        location_code,
                        name,
                        latitude,
                        longitude,
                        distance
                    FROM location_distances
                    ORDER BY distance ASC
                    LIMIT 1
                """, (lat, lon, lat, cutoff))
                
                result = cursor.fetchone()
                if result:
                    # Cache this mapping for future use
                    self.cache_ipma_location(
                        lat=lat,
                        lon=lon,
                        location_code=result[0],
                        name=result[1],
                        loc_lat=result[2],
                        loc_lon=result[3],
                        distance=result[4]
                    )
                    return {
                        'code': result[0],
                        'name': result[1],
                        'latitude': result[2],
                        'longitude': result[3],
                        'distance': result[4]
                    }
                return None
    
    def cache_ipma_location(
        self,
        lat: float,
        lon: float,
        location_code: str,
        name: str,
        loc_lat: float,
        loc_lon: float,
        distance: float
    ) -> None:
        """Cache IPMA location data."""
        with handle_errors(WeatherError, "weather_cache", "cache ipma location"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.now()
                
                # Insert/update location
                cursor.execute("""
                    INSERT INTO locations 
                    (location_code, name, latitude, longitude, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(location_code) DO UPDATE SET
                    name=excluded.name,
                    latitude=excluded.latitude,
                    longitude=excluded.longitude,
                    last_updated=excluded.last_updated
                """, (location_code, name, loc_lat, loc_lon, now))
                
                # Insert/update coordinate mapping
                cursor.execute("""
                    INSERT INTO coordinate_mappings
                    (latitude, longitude, service, location_code, distance, last_updated)
                    VALUES (?, ?, 'ipma', ?, ?, ?)
                    ON CONFLICT(latitude, longitude, service) DO UPDATE SET
                    location_code=excluded.location_code,
                    distance=excluded.distance,
                    last_updated=excluded.last_updated
                """, (lat, lon, location_code, distance, now))
                
                conn.commit()
    
    def cleanup(self, max_age_days: int = 30) -> None:
        """Clean up old cache entries."""
        with handle_errors(WeatherError, "weather_cache", "cleanup"):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cutoff = datetime.now() - timedelta(days=max_age_days)
                
                # Delete old mappings
                cursor.execute("DELETE FROM coordinate_mappings WHERE last_updated < ?", (cutoff,))
                
                # Delete unused municipalities
                cursor.execute("""
                    DELETE FROM municipalities 
                    WHERE municipality_code NOT IN (
                        SELECT DISTINCT location_code 
                        FROM coordinate_mappings 
                        WHERE service = 'aemet'
                    )
                """)
                
                # Delete unused locations
                cursor.execute("""
                    DELETE FROM locations 
                    WHERE location_code NOT IN (
                        SELECT DISTINCT location_code 
                        FROM coordinate_mappings 
                        WHERE service = 'ipma'
                    )
                """)
                
                conn.commit() 