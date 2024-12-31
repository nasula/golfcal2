"""Weather database manager for caching weather data."""

import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

from golfcal2.utils.logging_utils import LoggerMixin

class WeatherDatabase(LoggerMixin):
    """Manages weather data caching in SQLite database."""
    
    def __init__(self, db_name: str, schema: Dict[str, List[str]]):
        """Initialize database with schema.
        
        Args:
            db_name: Name of the database file (without .db extension)
            schema: Dictionary of table names to column definitions
        """
        LoggerMixin.__init__(self)
        self.db_file = os.path.join(os.path.dirname(__file__), '..', 'data', f'{db_name}.db')
        self.db_dir = os.path.dirname(self.db_file)
        self.schema = schema
        self._init_db()
    
    def _init_db(self):
        """Initialize database with provided schema."""
        try:
            os.makedirs(self.db_dir, exist_ok=True)
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                for table_name, columns in self.schema.items():
                    cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
                    cursor.execute(f'''
                        CREATE TABLE {table_name} (
                            {", ".join(columns)}
                        )
                    ''')
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_file)
    
    def get_weather_data(
        self,
        location: str,
        times: List[str],
        data_type: str,
        fields: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get weather data from cache.
        
        Args:
            location: Location identifier (e.g. "lat,lon")
            times: List of time strings to fetch
            data_type: Type of forecast (e.g. "next_1_hours")
            fields: List of fields to fetch
            
        Returns:
            Dictionary mapping times to weather data
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                weather_data = {}
                
                # Fetch data for all times at once
                placeholders = ','.join(['?' for _ in times])
                field_list = ', '.join(fields)
                query = f'''
                    SELECT time, {field_list}
                    FROM weather
                    WHERE location = ? 
                    AND time IN ({placeholders})
                    AND data_type = ?
                    AND (expires IS NULL OR expires > datetime('now'))
                    ORDER BY time ASC
                '''
                
                cursor.execute(query, [location] + times + [data_type])
                results = cursor.fetchall()
                
                # Convert results to dictionary
                for result in results:
                    time = result[0]
                    data = {}
                    for i, field in enumerate(fields, 1):
                        data[field] = result[i]
                    weather_data[time] = data
                    self.logger.debug(f"Found cached data for {time}: {data}")
                
                return weather_data
                
        except Exception as e:
            self.logger.error(f"Failed to get weather data from cache: {e}")
            return {}
    
    def store_weather_data(
        self,
        data: List[Dict[str, Any]],
        expires: Optional[str] = None,
        last_modified: Optional[str] = None
    ):
        """Store weather data in cache.
        
        Args:
            data: List of weather data entries
            expires: Optional expiration time
            last_modified: Optional last modified time
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Store each entry
                for entry in data:
                    # Get all fields except location and time
                    fields = [k for k in entry.keys() if k not in ['location', 'time']]
                    field_list = ', '.join(['location', 'time'] + fields)
                    value_list = ', '.join(['?'] * (len(fields) + 2))
                    
                    query = f'''
                        INSERT OR REPLACE INTO weather 
                        ({field_list}, expires, last_modified)
                        VALUES ({value_list}, ?, ?)
                    '''
                    
                    values = [
                        entry['location'],
                        entry['time']
                    ] + [entry.get(field) for field in fields] + [expires, last_modified]
                    
                    cursor.execute(query, values)
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to store weather data: {e}") 