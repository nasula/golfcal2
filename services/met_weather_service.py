"""MET.no weather service implementation."""

import os
import json
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import requests
import pytz
import math

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService

class MetWeatherService(WeatherService, LoggerMixin):
    """Service for handling weather data from MET.no API."""
    
    def __init__(self):
        """Initialize service with API endpoint and database connection."""
        super().__init__()
        self.api_endpoint = 'https://api.met.no/weatherapi/locationforecast/2.0/complete.json'
        self.headers = {
            'User-Agent': 'GolfCal/1.0 github.com/jahonen/golfcal jarkko.ahonen@iki.fi',
        }
        # Set up database path
        self.db_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'weather.db')
        self.db_dir = os.path.dirname(self.db_file)
        
        # Ensure data directory exists
        os.makedirs(self.db_dir, exist_ok=True)
        
        # Initialize database
        self._init_db()
        
        # Track API calls to respect rate limits
        self._last_api_call = None
        self._min_call_interval = timedelta(seconds=1)  # Minimum 1 second between calls

    def get_weather(self, lat: float, lon: float, date: datetime, duration_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get weather data for given coordinates and date."""
        # Convert date to UTC for API request
        utc_date = date.astimezone(pytz.UTC)
        self.logger.debug(f"Converting time from {date} to UTC: {utc_date}")
        
        # Get time blocks based on how far in the future the date is
        interval, event_blocks = self.get_time_blocks(utc_date, duration_minutes)
        self.logger.debug(f"Time blocks: interval={interval}h, blocks={event_blocks}")
        
        # Calculate times to fetch
        times_to_fetch = []
        event_date = utc_date.date()
        for block_start, block_end in event_blocks:
            # Create datetime for this block
            block_time = datetime.combine(event_date, datetime.min.time(), tzinfo=utc_date.tzinfo)
            block_time = block_time.replace(hour=block_start)
            times_to_fetch.append(block_time.strftime('%Y-%m-%dT%H:%M:%SZ'))
        
        self.logger.debug(f"Fetching weather for times: {times_to_fetch}")
        
        # Get weather data
        weather_data = self._fetch_weather_data(lat, lon, times_to_fetch, interval)
        if not weather_data:
            self.logger.error("No weather data returned from _fetch_weather_data")
            return None
        
        self.logger.debug(f"Received weather data: {weather_data}")
        
        # Return all weather data points
        forecasts = []
        for time_str in times_to_fetch:
            if time_str in weather_data:
                data = weather_data[time_str]
                # Parse time from ISO format
                forecast_time = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')
                # Convert to local time
                local_time = forecast_time.astimezone(date.tzinfo)
                forecast = {
                    'time': local_time,
                    'data_type': data.get('data_type', 'next_1_hours'),
                    'symbol_code': data['summary_code'],
                    'air_temperature': data['air_temperature'],
                    'precipitation_amount': data.get('precipitation_amount', 0.0),
                    'wind_speed': data['wind_speed'],
                    'wind_from_direction': data.get('wind_from_direction', 0),
                    'probability_of_precipitation': data.get('probability_of_precipitation', 0.0),
                    'probability_of_thunder': data.get('probability_of_thunder', 0.0)
                }
                self.logger.debug(f"Adding forecast for {local_time}: {forecast}")
                forecasts.append(forecast)
            else:
                self.logger.warning(f"No weather data found for time {time_str}")
        
        if not forecasts:
            self.logger.error("No forecasts could be created from weather data")
            return None
            
        # Return all forecasts
        result = {
            'forecasts': forecasts,
            'symbol_code': forecasts[0]['symbol_code'],
            'air_temperature': forecasts[0]['air_temperature'],
            'precipitation_amount': forecasts[0]['precipitation_amount'],
            'wind_speed': forecasts[0]['wind_speed'],
            'wind_from_direction': forecasts[0]['wind_from_direction'],
            'probability_of_precipitation': forecasts[0]['probability_of_precipitation'],
            'probability_of_thunder': forecasts[0]['probability_of_thunder']
        }
        self.logger.debug(f"Returning weather result: {result}")
        return result

    def _init_db(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Drop the old table if it exists
            cursor.execute('DROP TABLE IF EXISTS weather')
            
            # Create table with correct schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weather (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL,
                    time TEXT NOT NULL,
                    data_type TEXT NOT NULL DEFAULT 'next_1_hours',
                    air_pressure REAL,
                    air_temperature REAL,
                    cloud_area_fraction REAL,
                    dew_point_temperature REAL,
                    fog_area_fraction REAL,
                    relative_humidity REAL,
                    ultraviolet_index REAL,
                    wind_from_direction REAL,
                    wind_speed REAL,
                    wind_speed_gust REAL,
                    precipitation_amount REAL,
                    precipitation_max REAL,
                    precipitation_min REAL,
                    probability_of_precipitation REAL,
                    probability_of_thunder REAL,
                    temperature_max REAL,
                    temperature_min REAL,
                    summary_code TEXT,
                    expires TEXT,
                    last_modified TEXT,
                    precipitation_rate REAL,
                    precipitation_intensity REAL,
                    UNIQUE(location, time, data_type)
                )
            ''')
            
            conn.commit()

    def _try_get_weather_data(
        self,
        times_to_fetch: List[str],
        interval: int,
        lat: float,
        lon: float
    ) -> Dict[str, Dict[str, Any]]:
        """Try to get weather data from DB or API for specific interval type."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            weather_data = {}
            need_fetch = False
            now = datetime.now()
            
            # Fetch data for all times at once
            placeholders = ','.join(['?' for _ in times_to_fetch])
            query = f'''
                SELECT time, air_temperature, probability_of_precipitation, precipitation_amount,
                       wind_speed, probability_of_thunder, summary_code, expires, data_type,
                       wind_from_direction
                FROM weather
                WHERE location = ? 
                AND time IN ({placeholders})
                AND data_type = ?
                ORDER BY time ASC
            '''
            
            cursor.execute(query, [f"{lat},{lon}"] + times_to_fetch + [f'next_{interval}_hours'])
            results = cursor.fetchall()
            
            if len(results) != len(times_to_fetch):
                need_fetch = True
            else:
                # Check expiration for all results
                for result in results:
                    if result[7]:  # expires field
                        try:
                            expires_dt = datetime.strptime(result[7], '%Y-%m-%dT%H:%M:%SZ')
                            if expires_dt < now:
                                need_fetch = True
                                break
                        except Exception:
                            need_fetch = True
                            break
                
                if not need_fetch:
                    # Add valid data to result
                    for result in results:
                        weather_data[result[0]] = {
                            'air_temperature': result[1],
                            'probability_of_precipitation': result[2],
                            'precipitation_amount': result[3],
                            'wind_speed': result[4],
                            'probability_of_thunder': result[5],
                            'summary_code': result[6],
                            'data_type': result[8],
                            'wind_from_direction': result[9]
                        }
                        self.logger.debug(f"DB data for {result[0]}: {weather_data[result[0]]}")
            
            if not need_fetch:
                return weather_data
            
            # Fetch from API
            weather_data = self._fetch_from_api(lat, lon, times_to_fetch)
            if weather_data:
                self.logger.debug(f"API data: {weather_data}")
            
            return weather_data

    def _fetch_from_api(
        self, 
        lat: float,
        lon: float,
        times_to_fetch: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch weather data from the API."""
        try:
            # Respect rate limits
            now = datetime.now()
            if self._last_api_call and (now - self._last_api_call) < self._min_call_interval:
                sleep_time = (self._min_call_interval - (now - self._last_api_call)).total_seconds()
                time.sleep(sleep_time)
            
            # Prepare API request
            params = {
                'lat': lat,
                'lon': lon
            }
            
            # Log the URL and parameters
            self.logger.debug(f"MET.no request: {self.api_endpoint} {params}")
            
            # Make the request with proper headers
            response = requests.get(self.api_endpoint, headers=self.headers, params=params)
            self._last_api_call = datetime.now()
            
            # Handle specific error cases
            if response.status_code == 403:
                self.logger.error(f"MET.no API request failed: {response.status_code}, URL: {response.url}")
                return {}
            elif response.status_code == 429:
                # Back off for a longer time on rate limit
                self._min_call_interval = min(self._min_call_interval * 2, timedelta(minutes=5))
                return {}
            elif response.status_code != 200:
                self.logger.error(f"MET.no API request failed: {response.status_code}, URL: {response.url}")
                return {}
            
            # Reset backoff on successful request
            self._min_call_interval = timedelta(seconds=1)
            
            # Parse response
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                self.logger.error("Failed to decode MET.no JSON response")
                return {}
            
            # Get expiration and last modified from headers for caching
            expires = response.headers.get('Expires')
            last_modified = response.headers.get('Last-Modified')
            
            # Parse and store the data
            parsed_data = self._parse_weather_data(response_json, lat, lon)
            if not parsed_data:
                self.logger.error("No data returned from MET.no _parse_weather_data")
                return {}
            
            # Store the data with proper expiration
            try:
                self._store_weather_data(parsed_data, expires, last_modified)
                
                # Return only the data for the requested times
                weather_data = {}
                for entry in parsed_data:
                    time_str = entry['time']
                    if time_str in times_to_fetch:
                        instant_details = entry.get('data', {}).get('instant', {}).get('details', {})
                        next_1_hours = entry.get('data', {}).get('next_1_hours', {})
                        next_6_hours = entry.get('data', {}).get('next_6_hours', {})
                        
                        # Get the forecast details based on availability
                        forecast = next_1_hours if next_1_hours else next_6_hours
                        forecast_details = forecast.get('details', {})
                        forecast_summary = forecast.get('summary', {})
                        
                        # Skip if we don't have the required data
                        if not instant_details or not forecast:
                            continue
                        
                        weather_data[time_str] = {
                            'air_temperature': instant_details.get('air_temperature'),
                            'precipitation_amount': forecast_details.get('precipitation_amount', 0.0),
                            'probability_of_precipitation': forecast_details.get('probability_of_precipitation', 0.0),
                            'probability_of_thunder': forecast_details.get('probability_of_thunder', 0.0),
                            'wind_speed': instant_details.get('wind_speed'),
                            'wind_from_direction': instant_details.get('wind_from_direction'),
                            'summary_code': forecast_summary.get('symbol_code', 'cloudy'),
                            'data_type': 'next_1_hours' if next_1_hours else 'next_6_hours'
                        }
                        
                        # Skip if any required field is None
                        if any(v is None for v in weather_data[time_str].values()):
                            del weather_data[time_str]
                            continue
                
                if not weather_data:
                    self.logger.error(f"No matching times found in MET.no data. Times to fetch: {times_to_fetch}")
                else:
                    self.logger.debug(f"Found weather data for {len(weather_data)} time blocks")
                
                return weather_data
                
            except Exception as e:
                self.logger.error(f"Failed to store or process MET.no data: {e}")
                return {}
            
        except requests.exceptions.RequestException:
            return {}
        except Exception:
            return {}

    def _parse_weather_data(self, data: Dict[str, Any], lat: float, lon: float) -> List[Dict[str, Any]]:
        """Parse weather data from API response."""
        try:
            parsed_data = []
            
            # Get time series data
            timeseries = data.get('properties', {}).get('timeseries', [])
            if not timeseries:
                self.logger.error("No timeseries data found in API response")
                return []
            
            self.logger.debug(f"Found {len(timeseries)} time points in API response")
            
            # Process each time point
            for entry in timeseries:
                time = entry.get('time')
                if not time:
                    self.logger.warning("Time missing from entry, skipping")
                    continue
                
                # Get instant and forecast data
                data = entry.get('data', {})
                instant = data.get('instant', {}).get('details', {})
                next_1_hours = data.get('next_1_hours', {})
                next_6_hours = data.get('next_6_hours', {})
                
                # Get the forecast details based on availability
                forecast = next_1_hours if next_1_hours else next_6_hours
                forecast_details = forecast.get('details', {})
                forecast_summary = forecast.get('summary', {})
                
                self.logger.debug(f"Processing time point {time}:")
                self.logger.debug(f"  Instant data: {instant}")
                self.logger.debug(f"  1h forecast: {next_1_hours}")
                self.logger.debug(f"  6h forecast: {next_6_hours}")
                
                # Skip if we don't have the required data
                if not instant or not forecast:
                    self.logger.warning(f"Missing required data for {time}, skipping")
                    continue
                
                # Create base entry with instant data
                weather_entry = {
                    'location': f"{lat},{lon}",
                    'time': time,
                    'data': {
                        'instant': {
                            'details': instant
                        }
                    },
                    'air_temperature': instant.get('air_temperature'),
                    'wind_speed': instant.get('wind_speed'),
                    'wind_from_direction': instant.get('wind_from_direction'),
                    'relative_humidity': instant.get('relative_humidity'),
                    'cloud_area_fraction': instant.get('cloud_area_fraction'),
                    'fog_area_fraction': instant.get('fog_area_fraction'),
                    'ultraviolet_index': instant.get('ultraviolet_index_clear_sky'),
                    'air_pressure': instant.get('air_pressure_at_sea_level'),
                    'dew_point_temperature': instant.get('dew_point_temperature'),
                    'wind_speed_gust': instant.get('wind_speed_of_gust'),
                    # Add forecast data
                    'precipitation_amount': forecast_details.get('precipitation_amount', 0.0),
                    'probability_of_precipitation': forecast_details.get('probability_of_precipitation', 0.0),
                    'probability_of_thunder': forecast_details.get('probability_of_thunder', 0.0),
                    'summary_code': forecast_summary.get('symbol_code', 'cloudy'),
                    'data_type': 'next_1_hours' if next_1_hours else 'next_6_hours'
                }
                
                # Add the complete forecast data
                if next_1_hours:
                    weather_entry['data']['next_1_hours'] = next_1_hours
                if next_6_hours:
                    weather_entry['data']['next_6_hours'] = next_6_hours
                
                self.logger.debug(f"Created weather entry for {time}: {weather_entry}")
                parsed_data.append(weather_entry)
            
            self.logger.debug(f"Parsed {len(parsed_data)} weather entries")
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"Failed to parse weather data: {e}")
            return []

    def _store_weather_data(self, parsed_data: List[Dict[str, Any]], expires: Optional[str], last_modified: Optional[str]) -> None:
        """Store weather data in the database."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Convert dates to ISO format
                expires_iso = self._convert_date_to_iso(expires) if expires else None
                last_modified_iso = self._convert_date_to_iso(last_modified) if last_modified else None
                
                # Store each entry
                for entry in parsed_data:
                    # Prepare values for insertion
                    values = (
                        entry['location'],
                        entry['time'],
                        entry.get('data_type'),
                        entry.get('air_pressure'),
                        entry.get('air_temperature'),
                        entry.get('cloud_area_fraction'),
                        entry.get('dew_point_temperature'),
                        entry.get('fog_area_fraction'),
                        entry.get('relative_humidity'),
                        entry.get('ultraviolet_index'),
                        entry.get('wind_from_direction'),
                        entry.get('wind_speed'),
                        entry.get('wind_speed_gust'),
                        entry.get('precipitation_amount'),
                        entry.get('precipitation_max'),
                        entry.get('precipitation_min'),
                        entry.get('precipitation_rate'),
                        entry.get('precipitation_intensity'),
                        entry.get('probability_of_precipitation'),
                        entry.get('probability_of_thunder'),
                        entry.get('temperature_max'),
                        entry.get('temperature_min'),
                        entry.get('summary_code'),
                        expires_iso,
                        last_modified_iso
                    )
                    
                    # Insert or replace data
                    cursor.execute('''
                        INSERT OR REPLACE INTO weather (
                            location, time, data_type,
                            air_pressure, air_temperature, cloud_area_fraction,
                            dew_point_temperature, fog_area_fraction, relative_humidity,
                            ultraviolet_index, wind_from_direction, wind_speed,
                            wind_speed_gust, precipitation_amount, precipitation_max,
                            precipitation_min, precipitation_rate, precipitation_intensity,
                            probability_of_precipitation, probability_of_thunder, temperature_max,
                            temperature_min, summary_code, expires, last_modified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', values)
                
                conn.commit()
                
        except Exception:
            raise

    def _convert_date_to_iso(self, date_str: str) -> Optional[str]:
        """Convert date string to ISO format."""
        try:
            # Parse various date formats
            for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%Y-%m-%dT%H:%M:%SZ']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except ValueError:
                    continue
            return None
        except Exception:
            return None 

    def _fetch_weather_data(self, lat: float, lon: float, times: List[str], interval: int) -> Dict[str, Dict[str, Any]]:
        """Fetch weather data from MET.no API."""
        # Try to get from cache first
        weather_data = self._try_get_weather_data(times, interval, lat, lon)
        if not weather_data:
            # Fetch from API if not in cache
            weather_data = self._fetch_from_api(lat, lon, times)
        
        return weather_data 