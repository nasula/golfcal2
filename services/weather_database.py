"""Weather database manager for caching weather data."""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

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
    
    def _init_db(self):
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
                
                # Convert ISO format times to database format
                db_times = []
                for t in times:
                    try:
                        # Try parsing as ISO format with timezone
                        dt = datetime.fromisoformat(t)
                        # Convert to UTC if it has timezone
                        if dt.tzinfo:
                            dt = dt.astimezone(timezone.utc)
                        # Store in database format
                        db_times.append(dt.strftime('%Y-%m-%dT%H:%M:%S+00:00'))
                    except ValueError as e:
                        self.error(f"Failed to parse time {t}: {e}")
                        continue
                
                if not db_times:
                    self.error("No valid times to query")
                    return {}
                
                # Fetch data for all times at once
                placeholders = ','.join(['?' for _ in db_times])
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
                
                self.debug(
                    "Executing query",
                    location=location,
                    times=db_times,
                    data_type=data_type,
                    fields=fields,
                    query=query
                )
                
                cursor.execute(query, [location] + db_times + [data_type])
                results = cursor.fetchall()
                
                # Convert results to dictionary
                for result in results:
                    time = result[0]
                    data = {}
                    for i, field in enumerate(fields, 1):
                        data[field] = result[i]
                    weather_data[time] = data
                    self.debug(f"Found cached data for {time}: {data}")
                
                return weather_data
                
        except Exception as e:
            self.error(f"Failed to get weather data from cache: {e}")
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
            self.debug(
                "Storing weather data",
                entries=len(data),
                first_entry=data[0] if data else None,
                expires=expires,
                last_modified=last_modified
            )
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Store each entry
                for entry in data:
                    try:
                        # Ensure time is in ISO format with timezone
                        try:
                            dt = datetime.fromisoformat(entry['time'])
                            if not dt.tzinfo:
                                dt = dt.replace(tzinfo=timezone.utc)
                            else:
                                dt = dt.astimezone(timezone.utc)
                            entry['time'] = dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                        except ValueError:
                            # If not ISO format, try parsing as regular datetime
                            dt = datetime.strptime(entry['time'], '%Y-%m-%d %H:%M:%S')
                            dt = dt.replace(tzinfo=timezone.utc)
                            entry['time'] = dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                        
                        # Convert expiration and last modified times if provided
                        expires_str = None
                        if expires:
                            try:
                                exp_dt = datetime.fromisoformat(expires)
                                if not exp_dt.tzinfo:
                                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                                else:
                                    exp_dt = exp_dt.astimezone(timezone.utc)
                                expires_str = exp_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                            except ValueError:
                                exp_dt = datetime.strptime(expires, '%Y-%m-%d %H:%M:%S')
                                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                                expires_str = exp_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                        
                        last_modified_str = None
                        if last_modified:
                            try:
                                mod_dt = datetime.fromisoformat(last_modified)
                                if not mod_dt.tzinfo:
                                    mod_dt = mod_dt.replace(tzinfo=timezone.utc)
                                else:
                                    mod_dt = mod_dt.astimezone(timezone.utc)
                                last_modified_str = mod_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                            except ValueError:
                                mod_dt = datetime.strptime(last_modified, '%Y-%m-%d %H:%M:%S')
                                mod_dt = mod_dt.replace(tzinfo=timezone.utc)
                                last_modified_str = mod_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                        
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
                        ] + [entry.get(field) for field in fields] + [expires_str, last_modified_str]
                        
                        self.debug(
                            "Executing insert query",
                            location=entry['location'],
                            time=entry['time'],
                            field_count=len(fields),
                            query=query,
                            values=values,
                            expires=expires_str
                        )
                        
                        cursor.execute(query, values)
                        
                    except Exception as e:
                        self.error(
                            "Failed to store entry",
                            error=str(e),
                            entry=entry,
                            exc_info=True
                        )
                        continue
                
                conn.commit()
                self.debug("Successfully committed weather data to database")
                
        except Exception as e:
            self.error(
                "Failed to store weather data",
                error=str(e),
                entry_count=len(data) if data else 0,
                first_entry=data[0] if data else None,
                exc_info=True
            )
            raise 