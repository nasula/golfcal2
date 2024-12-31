"""MET.no weather service implementation."""

import os
import json
import time
import pytz
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import requests

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import MET_SCHEMA

class MetWeatherService(WeatherService, LoggerMixin):
    """Service for handling weather data from MET.no API."""
    
    def __init__(self, local_tz, utc_tz):
        """Initialize service with API endpoints and credentials."""
        WeatherService.__init__(self)
        LoggerMixin.__init__(self)
        
        # MET.no API configuration
        self.endpoint = 'https://api.met.no/weatherapi/locationforecast/2.0'
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'GolfCal/1.0 github.com/jahonen/golfcal jarkko.ahonen@iki.fi',
        }
        
        # Timezone settings
        self.utc_tz = utc_tz
        self.local_tz = local_tz
        
        # Track API calls
        self._last_api_call = None
        self._min_call_interval = timedelta(seconds=1)
        
        # Initialize database
        self.db = WeatherDatabase('met_weather', MET_SCHEMA)
    
    def get_weather(self, lat: float, lon: float, date: datetime, duration_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get weather data for location and time."""
        try:
            # Calculate time range
            start_time = date.replace(minute=0, second=0, microsecond=0)
            if duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
            else:
                end_time = start_time + timedelta(hours=4)  # Default to 4 hours

            # Generate list of hours to fetch
            target_hours = []
            current = start_time
            while current <= end_time:
                target_hours.append(current)
                current += timedelta(hours=1)

            # Try to get from cache first
            times_to_fetch = [t.strftime('%Y-%m-%dT%H:%M:%SZ') for t in target_hours]
            location = f"{lat},{lon}"
            fields = [
                'air_temperature', 'precipitation_amount', 'wind_speed',
                'wind_from_direction', 'probability_of_precipitation',
                'probability_of_thunder', 'summary_code'
            ]
            
            weather_data = self.db.get_weather_data(location, times_to_fetch, 'next_1_hours', fields)
            
            if not weather_data:
                # Fetch from API if not in cache
                api_data = self._fetch_from_api(lat, lon)
                if not api_data:
                    return None
                
                # Parse and store in cache
                parsed_data = self._parse_met_data(api_data, start_time, duration_minutes)
                if not parsed_data:
                    return None
                
                # Convert to database format and store
                db_entries = []
                for time_str, data in parsed_data.items():
                    entry = {
                        'location': location,
                        'time': time_str,
                        'data_type': 'next_1_hours',
                        'air_temperature': data.get('air_temperature'),
                        'precipitation_amount': data.get('precipitation_amount'),
                        'wind_speed': data.get('wind_speed'),
                        'wind_from_direction': data.get('wind_from_direction'),
                        'probability_of_precipitation': data.get('probability_of_precipitation'),
                        'probability_of_thunder': data.get('probability_of_thunder'),
                        'summary_code': data.get('symbol_code')
                    }
                    db_entries.append(entry)
                
                # Store in cache with expiry from API response
                expires = self._get_expires_from_headers()
                self.db.store_weather_data(db_entries, expires=expires)
                
                weather_data = parsed_data

            # Convert cached data to forecast format
            forecasts = []
            for target_time in target_hours:
                time_str = target_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                if time_str in weather_data:
                    data = weather_data[time_str]
                    forecast = {
                        'time': target_time,
                        'data_type': 'next_1_hours',
                        'symbol_code': data.get('summary_code'),
                        'air_temperature': data.get('air_temperature'),
                        'precipitation_amount': data.get('precipitation_amount'),
                        'wind_speed': data.get('wind_speed'),
                        'wind_from_direction': data.get('wind_from_direction'),
                        'probability_of_precipitation': data.get('probability_of_precipitation'),
                        'probability_of_thunder': data.get('probability_of_thunder')
                    }
                    forecasts.append(forecast)

            if not forecasts:
                return None

            # Return first forecast's data as the main weather data
            first_forecast = forecasts[0]
            return {
                'forecasts': forecasts,
                'symbol_code': first_forecast['symbol_code'],
                'air_temperature': first_forecast['air_temperature'],
                'precipitation_amount': first_forecast['precipitation_amount'],
                'wind_speed': first_forecast['wind_speed'],
                'wind_from_direction': first_forecast['wind_from_direction'],
                'probability_of_precipitation': first_forecast['probability_of_precipitation'],
                'probability_of_thunder': first_forecast['probability_of_thunder']
            }

        except Exception as e:
            self.logger.error(f"Failed to get MET weather for {lat},{lon}: {e}", exc_info=True)
            return None

    def _fetch_from_api(self, lat: float, lon: float, start_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Fetch weather data from MET.no API."""
        try:
            # Rate limiting
            if self._last_api_call:
                elapsed = datetime.now() - self._last_api_call
                if elapsed < self._min_call_interval:
                    sleep_time = (self._min_call_interval - elapsed).total_seconds()
                    self.logger.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
            
            # Build API URL
            url = f"{self.endpoint}/complete"
            params = {
                'lat': f"{lat:.4f}",
                'lon': f"{lon:.4f}",
            }
            
            self.logger.debug(f"MET.no URL: {url} (params: {params})")
            
            # Make API request
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            self._last_api_call = datetime.now()
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Failed to fetch MET data: {e}", exc_info=True)
            return None

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

    def _parse_met_data(self, data: Dict[str, Any], start_time: datetime, duration_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Parse MET API response into our format.
        
        API response format from https://api.met.no/weatherapi/locationforecast/2.0/swagger:
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat, altitude]
            },
            "properties": {
                "meta": {
                    "updated_at": "2019-12-03T13:52:13Z",
                    "units": {...}
                },
                "timeseries": [{
                    "time": "2019-12-03T14:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_temperature": 17.1,
                                "wind_speed": 5.9,
                                "wind_from_direction": 121.3,
                                ...
                            }
                        },
                        "next_1_hours": {
                            "summary": {
                                "symbol_code": "cloudy"
                            },
                            "details": {
                                "precipitation_amount": 1.71,
                                "probability_of_precipitation": 37,
                                "probability_of_thunder": 54.32
                            }
                        }
                    }
                }]
            }
        }
        """
        try:
            if not data or data.get('type') != 'Feature':
                self.logger.error("Invalid API response format - not a GeoJSON Feature")
                return None
            
            properties = data.get('properties')
            if not properties:
                self.logger.error("No properties found in API response")
                return None
            
            timeseries = properties.get('timeseries')
            if not timeseries:
                self.logger.error("No timeseries data found in API response")
                return None
            
            # Calculate end time
            if duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
            else:
                end_time = start_time + timedelta(hours=4)  # Default to 4 hours
            
            # Parse each forecast
            parsed_data = {}
            for entry in timeseries:
                try:
                    # Convert timestamp to datetime
                    time_str = entry['time']
                    forecast_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    
                    # Skip if outside our time range
                    if forecast_time < start_time or forecast_time > end_time:
                        continue
                    
                    # Extract weather data
                    data = entry.get('data', {})
                    instant = data.get('instant', {}).get('details', {})
                    next_1_hours = data.get('next_1_hours', {})
                    summary = next_1_hours.get('summary', {})
                    details = next_1_hours.get('details', {})
                    
                    if not instant or not next_1_hours:
                        continue
                    
                    parsed_data[forecast_time.strftime('%Y-%m-%dT%H:%M:%SZ')] = {
                        'air_temperature': instant.get('air_temperature'),
                        'precipitation_amount': details.get('precipitation_amount'),
                        'wind_speed': instant.get('wind_speed'),
                        'wind_from_direction': instant.get('wind_from_direction'),
                        'probability_of_precipitation': details.get('probability_of_precipitation'),
                        'probability_of_thunder': details.get('probability_of_thunder', 0.0),
                        'symbol_code': summary.get('symbol_code')
                    }
                    
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Failed to parse forecast: {e}")
                    continue
            
            if not parsed_data:
                self.logger.warning(f"No valid forecasts found between {start_time} and {end_time}")
                return None
                
            self.logger.debug(f"Successfully parsed {len(parsed_data)} forecasts")
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"Failed to parse MET data: {e}")
            return None 

    def _get_expires_from_headers(self) -> str:
        """Get expiry time from API response headers.
        
        Met.no API updates data every hour, but we'll use a conservative
        2-hour expiry to ensure we have fresh data.
        """
        return (datetime.now(self.utc_tz) + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ') 