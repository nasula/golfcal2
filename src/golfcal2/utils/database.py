"""Database utilities for weather data caching."""

import os
import sqlite3
from typing import Any

from golfcal2.utils.logging_utils import LoggerMixin


class WeatherDatabase(LoggerMixin):
    """Manages weather data caching in SQLite database."""
    
    def __init__(self, db_name: str, schema: dict[str, list[str]]):
        """Initialize database with schema.
        
        Args:
            db_name: Name of the database file (without .db extension)
            schema: Dictionary of table names to column definitions
        """
        LoggerMixin.__init__(self)
        
        # Use the data directory in the workspace
        self.db_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.db_file = os.path.join(self.db_dir, f'{db_name}.db')
        self.schema = schema
        
        self.debug(
            "Initializing weather database",
            db_file=self.db_file,
            db_dir=self.db_dir
        )
        
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database with provided schema."""
        try:
            os.makedirs(self.db_dir, exist_ok=True)
            self.debug(f"Ensuring database directory exists: {self.db_dir}")
            
            # Only create tables if they don't exist (don't drop existing tables)
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                for table_name, columns in self.schema.items():
                    self.debug(f"Creating table if not exists: {table_name}")
                    cursor.execute(f'''
                        CREATE TABLE IF NOT EXISTS {table_name} (
                            {", ".join(columns)}
                        )
                    ''')
                conn.commit()
                self.debug("Database initialization complete")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise
    
    def get_weather_data(
        self,
        location: str,
        times: list[str],
        data_type: str,
        fields: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Get weather data from cache for given location and times.
        
        Args:
            location: Location string (e.g. "60.123,24.456")
            times: List of ISO format time strings
            data_type: Type of data to fetch (e.g. "daily", "hourly")
            fields: List of fields to fetch
            
        Returns:
            Dictionary mapping time strings to weather data dictionaries
        """
        try:
            self.debug(
                "Fetching weather data from cache",
                location=location,
                time_count=len(times),
                data_type=data_type,
                fields=fields
            )
            
            # Build query
            field_str = ", ".join(fields)
            placeholders = ", ".join("?" for _ in times)
            query = f"""
                SELECT time, {field_str}
                FROM weather_{data_type}
                WHERE location = ? AND time IN ({placeholders})
            """
            
            # Execute query
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(query, [location] + times)
                rows = cursor.fetchall()
                
                # Convert to dictionary
                weather_data = {}
                for row in rows:
                    time_str = row[0]
                    data = {
                        field: value
                        for field, value in zip(fields, row[1:], strict=False)
                    }
                    weather_data[time_str] = data
                
                self.debug(
                    "Retrieved weather data from cache",
                    found_entries=len(weather_data)
                )
                
                return weather_data
                
        except Exception as e:
            self.error(f"Failed to get weather data from cache: {e}")
            return {} 