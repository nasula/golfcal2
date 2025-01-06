"""MET.no weather service implementation."""

import os
import json
import time
import pytz
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import requests

from golfcal2.utils.logging_utils import log_execution
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import MET_SCHEMA
from golfcal2.services.weather_types import WeatherService, WeatherData, WeatherCode
from golfcal2.exceptions import (
    WeatherError,
    APIError,
    APITimeoutError,
    APIRateLimitError,
    APIResponseError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error

class MetWeatherService(WeatherService):
    """Service for handling weather data from MET.no API."""
    
    BASE_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz, utc_tz, config):
        """Initialize service with API endpoints and credentials.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Application configuration
        """
        super().__init__(local_tz, utc_tz)
        
        with handle_errors(WeatherError, "met_weather", "initialize service"):
            # MET.no API configuration
            self.endpoint = self.BASE_URL
            self.headers = {
                'Accept': 'application/json',
                'User-Agent': self.USER_AGENT,
            }
            
            # Initialize database
            self.db = WeatherDatabase('met_weather', MET_SCHEMA)
            
            # Rate limiting configuration
            self._last_api_call = None
            self._min_call_interval = timedelta(seconds=1)  # MET.no requires 1 second between calls
            
            self.set_log_context(service="MET.no")
    
    @log_execution(level='DEBUG')
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, altitude: Optional[int] = None) -> List[WeatherData]:
        """Get weather data for location and time range.
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            start_time: Start time for forecast
            end_time: End time for forecast
            altitude: Optional ground surface height in meters for more precise temperature values
        """
        with handle_errors(
            WeatherError,
            "met_weather",
            f"get weather for coordinates ({lat}, {lon})",
            lambda: []  # Fallback to empty list on error
        ):
            self.set_log_context(
                latitude=lat,
                longitude=lon,
                altitude=altitude,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat()
            )
            
            # Calculate time range
            if not end_time:
                end_time = start_time + timedelta(hours=4)  # Default to 4-hour duration
            
            # Try to get from cache first
            location = f"{lat},{lon}"
            if altitude:
                location += f",{altitude}"
                
            times_to_fetch = []
            current = start_time
            while current <= end_time:
                times_to_fetch.append(current.strftime('%Y-%m-%dT%H:%M:%SZ'))
                current += timedelta(hours=1)
            
            fields = [
                'air_temperature', 'precipitation_amount', 'wind_speed',
                'wind_from_direction', 'probability_of_precipitation',
                'probability_of_thunder', 'summary_code'
            ]
            
            weather_data = self.db.get_weather_data(location, times_to_fetch, 'next_1_hours', fields)
            
            if not weather_data:
                # Fetch from API if not in cache
                api_data = self._fetch_from_api(lat, lon, altitude)
                if not api_data:
                    error = WeatherError(
                        "Failed to fetch weather data from MET.no API",
                        ErrorCode.API_ERROR,
                        {"location": location}
                    )
                    aggregate_error(str(error), "met_weather", None)
                    return []
                
                # Parse and store in cache
                weather_data = self._parse_api_data(api_data, start_time, end_time)
                if not weather_data:
                    error = WeatherError(
                        "Failed to parse weather data from MET.no API",
                        ErrorCode.PARSING_ERROR,
                        {"location": location}
                    )
                    aggregate_error(str(error), "met_weather", None)
                    return []
                
                # Store in cache
                db_entries = []
                for time_str, data in weather_data.items():
                    entry = {
                        'location': location,
                        'time': time_str,
                        'data_type': 'next_1_hours',
                        'air_temperature': data.get('temperature'),
                        'precipitation_amount': data.get('precipitation'),
                        'wind_speed': data.get('wind_speed'),
                        'wind_from_direction': data.get('wind_direction'),
                        'probability_of_precipitation': data.get('precipitation_probability'),
                        'probability_of_thunder': data.get('thunder_probability', 0.0),
                        'summary_code': data.get('symbol')
                    }
                    db_entries.append(entry)
                
                # Store with 2-hour expiry
                expires = (datetime.utcnow() + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
                try:
                    self.db.store_weather_data(db_entries, expires=expires)
                except Exception as e:
                    error = WeatherError(
                        "Failed to store weather data in cache",
                        ErrorCode.CACHE_ERROR,
                        {"location": location}
                    )
                    aggregate_error(str(error), "met_weather", e.__traceback__)
            
            # Convert to WeatherData objects
            forecasts = []
            for time_str in times_to_fetch:
                if time_str in weather_data:
                    data = weather_data[time_str]
                    forecast = WeatherData(
                        temperature=data.get('temperature', 0.0),
                        precipitation=data.get('precipitation', 0.0),
                        precipitation_probability=data.get('precipitation_probability'),
                        wind_speed=data.get('wind_speed', 0.0),
                        wind_direction=str(data.get('wind_direction')) if data.get('wind_direction') is not None else None,
                        symbol=data.get('symbol', 'cloudy'),
                        elaboration_time=datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=self.utc_tz),
                        thunder_probability=data.get('probability_of_thunder')
                    )
                    forecasts.append(forecast)
            
            return forecasts

    def _fetch_from_api(self, lat: float, lon: float, altitude: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Fetch weather data from MET.no API.
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            altitude: Optional ground surface height in meters
        """
        with handle_errors(
            WeatherError,
            "met_weather",
            f"fetch from API for coordinates ({lat}, {lon})",
            lambda: None  # Fallback to None on error
        ):
            # Rate limiting
            if self._last_api_call:
                elapsed = datetime.now() - self._last_api_call
                if elapsed < self._min_call_interval:
                    sleep_time = (self._min_call_interval - elapsed).total_seconds()
                    self.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
            
            # Build API URL
            params = {
                'lat': f"{lat:.4f}",
                'lon': f"{lon:.4f}",
            }
            
            if altitude is not None:
                params['altitude'] = str(int(altitude))
            
            self.debug(f"MET.no URL: {self.endpoint} (params: {params})")
            
            try:
                # Make API request
                response = requests.get(self.endpoint, params=params, headers=self.headers, timeout=10)
                
                self._last_api_call = datetime.now()
                
                if response.status_code == 429:  # Too Many Requests
                    error = APIRateLimitError(
                        "MET.no API rate limit exceeded",
                        retry_after=int(response.headers.get('Retry-After', 60))
                    )
                    aggregate_error(str(error), "met_weather", None)
                    return None
                
                if response.status_code != 200:
                    error = APIResponseError(
                        f"MET.no API request failed with status {response.status_code}",
                        response=response
                    )
                    aggregate_error(str(error), "met_weather", None)
                    return None
                
                return response.json()
                
            except requests.exceptions.Timeout:
                error = APITimeoutError(
                    "MET.no API request timed out",
                    {"url": self.endpoint}
                )
                aggregate_error(str(error), "met_weather", None)
                return None
            except requests.exceptions.RequestException as e:
                error = APIError(
                    f"MET.no API request failed: {str(e)}",
                    ErrorCode.REQUEST_FAILED,
                    {"url": self.endpoint}
                )
                aggregate_error(str(error), "met_weather", e.__traceback__)
                return None 

    def _parse_api_data(self, data: Dict[str, Any], start_time: datetime, end_time: datetime) -> Dict[str, Dict[str, Any]]:
        """Parse API response data into internal format."""
        with handle_errors(
            WeatherError,
            "met_weather",
            "parse API data",
            lambda: {}  # Fallback to empty dict on error
        ):
            if not data or 'properties' not in data:
                error = WeatherError(
                    "Invalid API response format",
                    ErrorCode.INVALID_RESPONSE,
                    {"response": data}
                )
                aggregate_error(str(error), "met_weather", None)
                return {}
            
            timeseries = data['properties'].get('timeseries', [])
            if not timeseries:
                error = WeatherError(
                    "No timeseries data in API response",
                    ErrorCode.INVALID_RESPONSE,
                    {"response": data}
                )
                aggregate_error(str(error), "met_weather", None)
                return {}
            
            weather_data = {}
            for entry in timeseries:
                with handle_errors(
                    WeatherError,
                    "met_weather",
                    "parse forecast entry",
                    lambda: None  # Skip entry on error
                ):
                    # Get timestamp
                    time_str = entry.get('time')
                    if not time_str:
                        continue
                        
                    forecast_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    
                    # Skip if outside our time range
                    if forecast_time < start_time or forecast_time > end_time:
                        continue
                    
                    # Get instant data
                    instant = entry.get('data', {}).get('instant', {}).get('details', {})
                    if not instant:
                        error = WeatherError(
                            "Missing instant data in forecast entry",
                            ErrorCode.INVALID_RESPONSE,
                            {"entry": entry}
                        )
                        aggregate_error(str(error), "met_weather", None)
                        continue
                    
                    # Get next 1 hour data
                    next_1_hour = entry.get('data', {}).get('next_1_hours', {})
                    details = next_1_hour.get('details', {})
                    summary = next_1_hour.get('summary', {})
                    
                    # Get symbol code
                    symbol_code = summary.get('symbol_code', 'cloudy')
                    
                    # Get thunder probability from API data first
                    thunder_prob = details.get('probability_of_thunder', 0.0)
                    
                    # If not available, calculate from symbol code as fallback
                    if not thunder_prob and 'thunder' in symbol_code:
                        # Extract intensity from symbol code
                        if 'heavy' in symbol_code:
                            thunder_prob = 80.0
                        elif 'light' in symbol_code:
                            thunder_prob = 20.0
                        else:
                            thunder_prob = 50.0
                    
                    weather_data[time_str] = {
                        'temperature': instant.get('air_temperature'),
                        'precipitation': details.get('precipitation_amount', 0.0),
                        'precipitation_probability': details.get('probability_of_precipitation'),
                        'wind_speed': instant.get('wind_speed'),
                        'wind_direction': self._get_wind_direction(instant.get('wind_from_direction')),
                        'symbol': symbol_code,
                        'thunder_probability': thunder_prob
                    }
            
            return weather_data
    
    def _get_wind_direction(self, degrees: Optional[float]) -> Optional[str]:
        """Convert wind direction from degrees to cardinal direction."""
        with handle_errors(
            WeatherError,
            "met_weather",
            f"get wind direction from {degrees} degrees",
            lambda: None  # Fallback to None on error
        ):
            if degrees is None:
                return None
                
            directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
            index = round(degrees / 45) % 8
            return directions[index]
    
    def _map_symbol_code(self, symbol_code: str) -> str:
        """Map MET.no symbol codes to our internal weather codes.
        
        See https://api.met.no/weatherapi/weathericon/2.0/documentation for symbol codes.
        """
        with handle_errors(
            WeatherError,
            "met_weather",
            f"map symbol code {symbol_code}",
            lambda: 'CLOUDY'  # Fallback to CLOUDY on error
        ):
            # Basic mapping of MET.no symbol codes to our internal codes
            symbol_map = {
                'clearsky': 'CLEAR',
                'fair': 'PARTLY_CLOUDY',
                'partlycloudy': 'PARTLY_CLOUDY',
                'cloudy': 'CLOUDY',
                'fog': 'FOG',
                'rain': 'RAIN',
                'sleet': 'SLEET',
                'snow': 'SNOW',
                'rainshowers': 'RAIN_SHOWERS',
                'sleetshowers': 'SLEET_SHOWERS',
                'snowshowers': 'SNOW_SHOWERS',
                'lightrainshowers': 'LIGHT_RAIN',
                'heavyrainshowers': 'HEAVY_RAIN',
                'lightrain': 'LIGHT_RAIN',
                'heavyrain': 'HEAVY_RAIN',
                'lightsnow': 'LIGHT_SNOW',
                'heavysnow': 'HEAVY_SNOW',
                'thunder': 'THUNDER',
                'rainandthunder': 'RAIN_AND_THUNDER',
                'sleetandthunder': 'SLEET_AND_THUNDER',
                'snowandthunder': 'SNOW_AND_THUNDER',
                'rainshowersandthunder': 'RAIN_AND_THUNDER',
                'sleetshowersandthunder': 'SLEET_AND_THUNDER',
                'snowshowersandthunder': 'SNOW_AND_THUNDER'
            }
            
            return symbol_map.get(symbol_code, 'CLOUDY')  # Default to CLOUDY if unknown code 

    def _parse_weather_data(self, data: Dict[str, Any], lat: float, lon: float) -> List[Dict[str, Any]]:
        """Parse weather data from API response."""
        with handle_errors(
            WeatherError,
            "met_weather",
            "parse weather data",
            lambda: []  # Fallback to empty list on error
        ):
            parsed_data = []
            
            # Get time series data
            timeseries = data.get('properties', {}).get('timeseries', [])
            if not timeseries:
                error = WeatherError(
                    "No timeseries data found in API response",
                    ErrorCode.INVALID_RESPONSE,
                    {"data": data}
                )
                aggregate_error(str(error), "met_weather", None)
                return []
            
            self.debug(f"Found {len(timeseries)} time points in API response")
            
            # Process each time point
            for entry in timeseries:
                with handle_errors(
                    WeatherError,
                    "met_weather",
                    "process time point",
                    lambda: None  # Skip entry on error
                ):
                    time = entry.get('time')
                    if not time:
                        self.warning("Time missing from entry, skipping")
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
                    
                    self.debug(f"Processing time point {time}:")
                    self.debug(f"  Instant data: {instant}")
                    self.debug(f"  1h forecast: {next_1_hours}")
                    self.debug(f"  6h forecast: {next_6_hours}")
                    
                    # Skip if we don't have the required data
                    if not instant or not forecast:
                        self.warning(f"Missing required data for {time}, skipping")
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
                        'precipitation_amount': data.get('precipitation', 0.0),
                        'wind_speed': data.get('wind_speed', 0.0),
                        'wind_from_direction': data.get('wind_from_direction'),
                        'relative_humidity': instant.get('relative_humidity'),
                        'cloud_area_fraction': instant.get('cloud_area_fraction'),
                        'fog_area_fraction': instant.get('fog_area_fraction'),
                        'ultraviolet_index': instant.get('ultraviolet_index_clear_sky'),
                        'air_pressure': instant.get('air_pressure_at_sea_level'),
                        'dew_point_temperature': instant.get('dew_point_temperature'),
                        'wind_speed_gust': data.get('wind_speed_of_gust', 0.0),
                        # Add forecast data
                        'precipitation_probability': forecast_details.get('probability_of_precipitation', 0.0),
                        'probability_of_thunder': forecast_details.get('probability_of_thunder', 0.0),
                        'summary_code': forecast_summary.get('symbol_code', 'cloudy'),
                        'data_type': 'next_1_hours' if next_1_hours else 'next_6_hours'
                    }
                    
                    # Add the complete forecast data
                    if next_1_hours:
                        weather_entry['data']['next_1_hours'] = next_1_hours
                    if next_6_hours:
                        weather_entry['data']['next_6_hours'] = next_6_hours
                    
                    self.debug(f"Created weather entry for {time}: {weather_entry}")
                    parsed_data.append(weather_entry)
            
            self.debug(f"Parsed {len(parsed_data)} weather entries")
            return parsed_data

    def _store_weather_data(self, parsed_data: List[Dict[str, Any]], expires: Optional[str], last_modified: Optional[str]) -> None:
        """Store weather data in the database."""
        with handle_errors(
            WeatherError,
            "met_weather",
            "store weather data",
            lambda: None  # Fallback to None on error
        ):
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Convert dates to ISO format
                expires_iso = self._convert_date_to_iso(expires) if expires else None
                last_modified_iso = self._convert_date_to_iso(last_modified) if last_modified else None
                
                # Store each entry
                for entry in parsed_data:
                    with handle_errors(
                        WeatherError,
                        "met_weather",
                        "store weather entry",
                        lambda: None  # Skip entry on error
                    ):
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

    def _convert_date_to_iso(self, date_str: str) -> Optional[str]:
        """Convert date string to ISO format."""
        with handle_errors(
            WeatherError,
            "met_weather",
            "convert date to ISO format",
            lambda: None  # Fallback to None on error
        ):
            # Parse various date formats
            for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%Y-%m-%dT%H:%M:%SZ']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except ValueError:
                    continue
            return None

    def _fetch_weather_data(self, lat: float, lon: float, times: List[str], interval: int) -> Dict[str, Dict[str, Any]]:
        """Fetch weather data from MET.no API."""
        with handle_errors(
            WeatherError,
            "met_weather",
            f"fetch weather data for coordinates ({lat}, {lon})",
            lambda: {}  # Fallback to empty dict on error
        ):
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
        with handle_errors(
            WeatherError,
            "met_weather",
            "parse MET data",
            lambda: None  # Fallback to None on error
        ):
            if not data or data.get('type') != 'Feature':
                error = WeatherError(
                    "Invalid API response format - not a GeoJSON Feature",
                    ErrorCode.INVALID_RESPONSE,
                    {"data": data}
                )
                aggregate_error(str(error), "met_weather", None)
                return None
            
            properties = data.get('properties')
            if not properties:
                error = WeatherError(
                    "No properties found in API response",
                    ErrorCode.INVALID_RESPONSE,
                    {"data": data}
                )
                aggregate_error(str(error), "met_weather", None)
                return None
            
            timeseries = properties.get('timeseries')
            if not timeseries:
                error = WeatherError(
                    "No timeseries data found in API response",
                    ErrorCode.INVALID_RESPONSE,
                    {"data": data}
                )
                aggregate_error(str(error), "met_weather", None)
                return None
            
            # Calculate end time
            if duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
            else:
                end_time = start_time + timedelta(hours=4)  # Default to 4 hours
            
            # Parse each forecast
            parsed_data = {}
            for entry in timeseries:
                with handle_errors(
                    WeatherError,
                    "met_weather",
                    "parse forecast entry",
                    lambda: None  # Skip entry on error
                ):
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
            
            if not parsed_data:
                self.warning(f"No valid forecasts found between {start_time} and {end_time}")
                return None
            
            self.debug(f"Successfully parsed {len(parsed_data)} forecasts")
            return parsed_data

    def _get_expires_from_headers(self) -> str:
        """Get expiry time from API response headers.
        
        Met.no API updates data every hour, but we'll use a conservative
        2-hour expiry to ensure we have fresh data.
        """
        with handle_errors(
            WeatherError,
            "met_weather",
            "get expires from headers",
            lambda: (datetime.now(self.utc_tz) + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')  # Fallback to 2 hours from now
        ):
            return (datetime.now(self.utc_tz) + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')

    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch forecasts from MET.no API."""
        with handle_errors(
            WeatherError,
            "met_weather",
            f"fetch forecasts for coordinates ({lat}, {lon})",
            lambda: []  # Fallback to empty list on error
        ):
            # Apply rate limiting
            self._apply_rate_limit()
            
            # Prepare request
            params = {
                'lat': f"{lat:.4f}",
                'lon': f"{lon:.4f}"
            }
            
            headers = {
                'User-Agent': self.USER_AGENT
            }
            
            # Log request details
            self.debug(
                "MET.no URL",
                url=self.BASE_URL,
                params=params
            )
            
            try:
                # Make request
                response = requests.get(
                    self.BASE_URL,
                    params=params,
                    headers=headers,
                    timeout=(10, 30)  # (connect timeout, read timeout)
                )
                
                if response.status_code == 429:  # Too Many Requests
                    error = APIRateLimitError(
                        "MET.no API rate limit exceeded",
                        retry_after=int(response.headers.get('Retry-After', 60))
                    )
                    aggregate_error(str(error), "met_weather", None)
                    return []
                
                if response.status_code != 200:
                    error = APIResponseError(
                        f"MET.no API request failed with status {response.status_code}",
                        response=response
                    )
                    aggregate_error(str(error), "met_weather", None)
                    return []
                
                # Parse response
                data = response.json()
                forecasts = self._parse_response(data, start_time, end_time)
                
                self.info(
                    "Successfully parsed forecasts",
                    count=len(forecasts)
                )
                
                return forecasts
                
            except requests.exceptions.Timeout:
                error = APITimeoutError(
                    "MET.no API request timed out",
                    {"url": self.BASE_URL}
                )
                aggregate_error(str(error), "met_weather", None)
                return []
            except requests.exceptions.RequestException as e:
                error = APIError(
                    f"MET.no API request failed: {str(e)}",
                    ErrorCode.REQUEST_FAILED,
                    {"url": self.BASE_URL}
                )
                aggregate_error(str(error), "met_weather", e.__traceback__)
                return []

    @log_execution(level='DEBUG')
    def _parse_response(self, data: Dict[str, Any], start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Parse MET.no API response."""
        with handle_errors(
            WeatherError,
            "met_weather",
            "parse API response",
            lambda: []  # Fallback to empty list on error
        ):
            forecasts = []
            
            try:
                timeseries = data['properties']['timeseries']
                
                for entry in timeseries:
                    with handle_errors(
                        WeatherError,
                        "met_weather",
                        "parse forecast entry",
                        lambda: None  # Skip entry on error
                    ):
                        time_str = entry['time']
                        forecast_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        
                        # Skip forecasts outside our time range
                        if not (start_time <= forecast_time <= end_time):
                            continue
                        
                        # Get instant data
                        instant = entry['data']['instant']['details']
                        
                        # Get precipitation data from next_1_hours if available, else next_6_hours
                        precip_data = (
                            entry['data'].get('next_1_hours', {}).get('details', {}) or
                            entry['data'].get('next_6_hours', {}).get('details', {})
                        )
                        
                        # Get symbol from next_1_hours if available, else next_6_hours
                        symbol_data = (
                            entry['data'].get('next_1_hours', {}).get('summary', {}) or
                            entry['data'].get('next_6_hours', {}).get('summary', {})
                        )
                        
                        forecast = WeatherData(
                            temperature=instant.get('air_temperature'),
                            precipitation=precip_data.get('precipitation_amount', 0.0),
                            precipitation_probability=precip_data.get('probability_of_precipitation'),
                            wind_speed=instant.get('wind_speed', 0.0),
                            wind_direction=self._get_wind_direction(instant.get('wind_from_direction')),
                            symbol=symbol_data.get('symbol_code', 'cloudy'),
                            elaboration_time=forecast_time,
                            thunder_probability=entry['data'].get('probability_of_thunder', 0.0)
                        )
                        
                        forecasts.append(forecast)
                
                return forecasts
                
            except KeyError as e:
                error = WeatherError(
                    "Invalid data structure in MET.no response",
                    ErrorCode.INVALID_RESPONSE,
                    {
                        "error": str(e),
                        "data_keys": list(data.keys()) if isinstance(data, dict) else None
                    }
                )
                aggregate_error(str(error), "met_weather", e.__traceback__)
                return []

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting for MET.no API."""
        with handle_errors(
            WeatherError,
            "met_weather",
            "apply rate limit",
            lambda: None  # Fallback to None on error
        ):
            # Ensure at least 1 second between requests
            elapsed = time.time() - self._last_request_time
            if elapsed < 1.0:
                sleep_time = 1.0 - elapsed
                self.debug(
                    "Rate limit",
                    sleep_seconds=sleep_time
                )
                time.sleep(sleep_time)
            self._last_request_time = time.time() 

    def get_block_size(self, hours_ahead: float) -> int:
        """Get block size for MET.no forecasts.
        
        First 48 hours: 1-hour blocks
        Beyond 48 hours: 6-hour blocks
        """
        return 6 if hours_ahead > 48 else 1 