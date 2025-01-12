"""Database for storing weather data and raw API responses."""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from zoneinfo import ZoneInfo

from golfcal2.utils.logging_utils import get_logger

class WeatherResponseCache:
    """Cache for storing raw weather API responses."""
    
    def __init__(self, db_path: str = 'weather_cache.db'):
        """Initialize the cache."""
        self.logger = get_logger(__name__)
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Create locations table to handle different location types
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weather_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_type TEXT NOT NULL,
                    location_id TEXT,           -- Service-specific ID (municipality code, grid point, etc.)
                    location_name TEXT,         -- Human readable name
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    metadata TEXT,              -- JSON string for additional location data
                    last_modified TEXT NOT NULL,
                    UNIQUE(service_type, latitude, longitude)
                )
            """)
            
            # Create responses table with foreign key to locations
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weather_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_ref INTEGER NOT NULL,
                    response_data TEXT NOT NULL,  -- JSON string of raw API response
                    forecast_start TEXT NOT NULL, -- ISO format UTC
                    forecast_end TEXT NOT NULL,   -- ISO format UTC
                    expires TEXT NOT NULL,        -- ISO format UTC
                    last_modified TEXT NOT NULL,  -- ISO format UTC
                    FOREIGN KEY(location_ref) REFERENCES weather_locations(id),
                    UNIQUE(location_ref, forecast_start, forecast_end)
                )
            """)
            
            # Create indices for efficient lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_location_coords ON weather_locations(latitude, longitude)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_location_service ON weather_locations(service_type, location_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_forecast_time ON weather_responses(forecast_start, forecast_end)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expiry ON weather_responses(expires)")
    
    def _get_or_create_location(
        self,
        conn: sqlite3.Connection,
        service_type: str,
        latitude: float,
        longitude: float,
        location_id: Optional[str] = None,
        location_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """Get or create a location entry and return its ID."""
        now = datetime.now(ZoneInfo("UTC"))
        
        # Try to find existing location
        cursor = conn.execute("""
            SELECT id FROM weather_locations
            WHERE service_type = ? AND latitude = ? AND longitude = ?
        """, (service_type, latitude, longitude))
        
        row = cursor.fetchone()
        if row:
            # Update metadata if provided
            if metadata or location_id or location_name:
                conn.execute("""
                    UPDATE weather_locations
                    SET location_id = COALESCE(?, location_id),
                        location_name = COALESCE(?, location_name),
                        metadata = COALESCE(?, metadata),
                        last_modified = ?
                    WHERE id = ?
                """, (
                    location_id,
                    location_name,
                    json.dumps(metadata) if metadata else None,
                    now.isoformat(),
                    row[0]
                ))
            return row[0]
        
        # Create new location
        cursor = conn.execute("""
            INSERT INTO weather_locations
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
        return cursor.lastrowid
    
    def store_response(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        response_data: Dict[str, Any],
        forecast_start: datetime,
        forecast_end: datetime,
        expires: datetime,
        location_id: Optional[str] = None,
        location_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Store a raw API response."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                now = datetime.now(ZoneInfo("UTC"))
                
                # Get or create location
                location_ref = self._get_or_create_location(
                    conn,
                    service_type,
                    latitude,
                    longitude,
                    location_id,
                    location_name,
                    metadata
                )
                
                self.logger.debug(
                    "Storing weather response",
                    service=service_type,
                    location_id=location_id,
                    location_name=location_name,
                    coords=(latitude, longitude),
                    time_range=f"{forecast_start.isoformat()} to {forecast_end.isoformat()}",
                    expires=expires.isoformat()
                )
                
                conn.execute("""
                    INSERT OR REPLACE INTO weather_responses
                    (location_ref, response_data, forecast_start, forecast_end, expires, last_modified)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    location_ref,
                    json.dumps(response_data),
                    forecast_start.isoformat(),
                    forecast_end.isoformat(),
                    expires.isoformat(),
                    now.isoformat()
                ))
        except Exception as e:
            self.logger.error(
                "Failed to store weather response",
                error=str(e),
                service=service_type,
                location_id=location_id,
                coords=(latitude, longitude)
            )
            raise
    
    def get_response(
        self,
        service_type: str,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
        location_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a cached response that covers the requested time range."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                self.logger.debug(
                    "Looking up weather response",
                    service=service_type,
                    coords=(latitude, longitude),
                    location_id=location_id,
                    time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
                )
                
                # Find responses that cover our time range and haven't expired
                query = """
                    SELECT r.response_data, r.forecast_start, r.forecast_end, r.expires,
                           l.location_id, l.location_name, l.metadata
                    FROM weather_responses r
                    JOIN weather_locations l ON r.location_ref = l.id
                    WHERE l.service_type = ?
                    AND l.latitude = ?
                    AND l.longitude = ?
                    AND r.forecast_start <= ?
                    AND r.forecast_end >= ?
                    AND (r.expires IS NULL OR r.expires > datetime('now', 'utc'))
                """
                params = [service_type, latitude, longitude, start_time.isoformat(), end_time.isoformat()]
                
                if location_id:
                    query += " AND l.location_id = ?"
                    params.append(location_id)
                
                query += " ORDER BY r.last_modified DESC LIMIT 1"
                
                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    response_data = json.loads(row[0])
                    location_metadata = json.loads(row[6]) if row[6] else None
                    
                    self.logger.info(
                        "Cache hit",
                        service=service_type,
                        coords=(latitude, longitude),
                        location_id=row[4],
                        location_name=row[5],
                        forecast_range=f"{row[1]} to {row[2]}",
                        expires=row[3]
                    )
                    
                    # Return response with location metadata
                    return {
                        'response': response_data,
                        'location': {
                            'id': row[4],
                            'name': row[5],
                            'metadata': location_metadata
                        }
                    }
                
                self.logger.info(
                    "Cache miss",
                    service=service_type,
                    coords=(latitude, longitude),
                    location_id=location_id,
                    time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
                )
                return None
                
        except Exception as e:
            self.logger.error(
                "Failed to get weather response",
                error=str(e),
                service=service_type,
                coords=(latitude, longitude),
                location_id=location_id
            )
            return None
    
    def cleanup_expired(self) -> int:
        """Remove expired responses. Returns number of entries removed."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM weather_responses
                    WHERE expires < datetime('now', 'utc')
                """)
                deleted = cursor.rowcount
                self.logger.info(f"Removed {deleted} expired weather responses")
                return deleted
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired responses: {e}")
            return 0 