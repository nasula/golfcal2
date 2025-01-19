"""Weather service implementation using Open-Meteo API.

Source: Open-Meteo
API Documentation: https://open-meteo.com/en/docs
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherCode, WeatherResponse
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.utils.logging_utils import log_execution, EnhancedLoggerMixin, get_logger
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
from golfcal2.config.types import AppConfig

class OpenMeteoService(WeatherService):
    """Service for handling weather data using Open-Meteo API.
    
    Open-Meteo provides free weather forecast APIs without key requirements.
    Data is updated hourly.
    """

    def __init__(self, timezone: ZoneInfo, utc: ZoneInfo, config: Dict[str, Any]):
        """Initialize service."""
        super().__init__(timezone, utc)
        self.config = config
        self.set_log_context(service="open_meteo")
        
        # Configure logger
        for handler in self.logger.handlers:
            handler.set_name('open_meteo')  # Ensure unique handler names
        self.logger.propagate = True  # Allow logs to propagate to root logger
        
        # Test debug call to verify logger name mapping
        self.debug(">>> TEST DEBUG: OpenMeteoService initialized", logger_name=self.logger.name)
        
        with handle_errors(WeatherError, "open_meteo", "initialize service"):
            # Setup cache and retry mechanism
            cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
            retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
            self.client = openmeteo_requests.Client(session=retry_session)
            
            # Initialize database and cache
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
            os.makedirs(data_dir, exist_ok=True)
            self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
            self.location_cache = WeatherLocationCache(os.path.join(data_dir, 'weather_locations.db'))
            
            # Rate limiting configuration
            self._last_api_call = None
            self._min_call_interval = timedelta(seconds=1)
            self._last_request_time = 0
            
            # Service type for caching
            self.service_type = 'open_meteo'

    def get_block_size(self, hours_ahead: float) -> int:
        """Get the block size in hours for grouping forecasts.
        
        Open-Meteo provides:
        - Hourly forecasts for 7 days
        - 3-hourly forecasts beyond 7 days
        
        Args:
            hours_ahead: Number of hours ahead of current time
            
        Returns:
            int: Block size in hours
        """
        if hours_ahead <= 168:  # 7 days
            return 1
        return 3

    def get_expiry_time(self) -> datetime:
        """Get expiry time for Open-Meteo weather data.
        
        Open-Meteo updates their forecasts hourly.
        """
        now = datetime.now(self.utc_tz)
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return next_hour

    def _map_wmo_code(self, code: int, hour: int) -> str:
        """Map WMO weather codes to internal codes.
        
        Args:
            code: WMO weather code from Open-Meteo
            hour: Hour of the day (0-23) to determine day/night
            
        Returns:
            Internal weather code string
        """
        # Determine if it's day or night (simple 6-20 rule)
        is_daytime = 6 <= hour < 20
        day_night = 'day' if is_daytime else 'night'
        
        # Map WMO codes to our internal codes
        # Reference: https://open-meteo.com/en/docs
        code_map = {
            0: f'clearsky_{day_night}',      # Clear sky
            1: f'fair_{day_night}',          # Mainly clear
            2: f'partlycloudy_{day_night}',  # Partly cloudy
            3: 'cloudy',                     # Overcast
            45: 'fog',                       # Foggy
            48: 'fog',                       # Depositing rime fog
            51: 'lightrain',                 # Light drizzle
            53: 'rain',                      # Moderate drizzle
            55: 'heavyrain',                 # Dense drizzle
            56: 'sleet',                     # Light freezing drizzle
            57: 'sleet',                     # Dense freezing drizzle
            61: 'lightrain',                 # Slight rain
            63: 'rain',                      # Moderate rain
            65: 'heavyrain',                 # Heavy rain
            66: 'sleet',                     # Light freezing rain
            67: 'sleet',                     # Heavy freezing rain
            71: 'lightsnow',                 # Slight snow fall
            73: 'snow',                      # Moderate snow fall
            75: 'heavysnow',                 # Heavy snow fall
            77: 'snow',                      # Snow grains
            80: 'lightrainshowers',          # Slight rain showers
            81: 'rainshowers',               # Moderate rain showers
            82: 'heavyrainshowers',          # Violent rain showers
            85: 'lightsnowshowers',          # Slight snow showers
            86: 'snowshowers',               # Heavy snow showers
            95: 'rainandthunder',            # Thunderstorm
            96: 'rainandthunder',            # Thunderstorm with slight hail
            99: 'rainandthunder'             # Thunderstorm with heavy hail
        }
        
        return code_map.get(code, 'cloudy')  # Default to cloudy if code not found

    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from Open-Meteo API."""
        try:
            # Calculate time range for fetching data
            now = datetime.now(self.utc_tz)
            hours_ahead = (end_time - now).total_seconds() / 3600
            
            # Configure API parameters
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": [
                    "temperature_2m",
                    "precipitation",
                    "precipitation_probability",
                    "weathercode",
                    "windspeed_10m",
                    "winddirection_10m"
                ],
                "timezone": "UTC"
            }
            
            self.debug("Making API request with params", params=params)
            
            # Make API request
            response = self.client.weather_api("https://api.open-meteo.com/v1/forecast", params=params)
            
            self.debug("Got API response", 
                      response_type=type(response).__name__,
                      response_len=len(response) if isinstance(response, list) else 0)
            
            if not response or not isinstance(response, list) or len(response) == 0:
                self.error("Failed to get forecast data")
                return None
            
            # Get the first response (should only be one)
            data = response[0]
            hourly = data.Hourly()
            
            if not hourly:
                self.error("No hourly data in response")
                return None
            
            self.debug("Processing hourly data",
                      variables_length=hourly.VariablesLength())
            
            # Get timestamps
            timestamps = []
            interval = hourly.Interval()  # Usually 3600 for hourly data
            start_timestamp = hourly.Time()
            end_timestamp = hourly.TimeEnd()
            
            current_timestamp = start_timestamp
            while current_timestamp < end_timestamp:
                timestamps.append(datetime.fromtimestamp(current_timestamp, tz=self.utc_tz))
                current_timestamp += interval
            
            # Convert response to dictionary
            hourly_entries = []
            
            # Variables are in the same order as in the request
            var_indices = {
                'temperature_2m': 0,      # temperature_2m
                'precipitation': 1,        # precipitation
                'precipitation_probability': 2,  # precipitation_probability
                'weathercode': 3,         # weathercode
                'windspeed_10m': 4,       # windspeed_10m
                'winddirection_10m': 5    # winddirection_10m
            }
            
            # Process each timestamp
            for i, timestamp in enumerate(timestamps):
                try:
                    # Skip if outside requested range
                    if timestamp < start_time or timestamp > end_time:
                        continue
                        
                    # Get hour for weather code mapping
                    hour = timestamp.hour
                    
                    # Get values for each variable at this timestamp
                    temp = hourly.Variables(var_indices['temperature_2m']).Values(i)
                    precip = hourly.Variables(var_indices['precipitation']).Values(i)
                    precip_prob = hourly.Variables(var_indices['precipitation_probability']).Values(i)
                    weathercode = int(hourly.Variables(var_indices['weathercode']).Values(i))
                    windspeed = hourly.Variables(var_indices['windspeed_10m']).Values(i)
                    winddir = hourly.Variables(var_indices['winddirection_10m']).Values(i)
                    
                    entry = {
                        'time': timestamp.isoformat(),
                        'temperature_2m': temp,
                        'precipitation': precip,
                        'precipitation_probability': precip_prob,
                        'weathercode': self._map_wmo_code(weathercode, hour),
                        'windspeed_10m': windspeed / 3.6,  # Convert km/h to m/s
                        'winddirection_10m': winddir
                    }
                    
                    self.debug("Processed hourly entry", index=i, entry=entry)
                    
                    hourly_entries.append(entry)
                except (IndexError, ValueError, AttributeError) as e:
                    self.warning(f"Error parsing forecast at index {i}: {e}")
                    continue
            
            self.debug("Processed all hourly entries", total_entries=len(hourly_entries))
            
            return {'hourly': hourly_entries}
            
        except Exception as e:
            self.error("Error fetching forecasts", exc_info=e)
            return None

    def _parse_response(
        self,
        response_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        interval: int
    ) -> Optional[WeatherResponse]:
        """Parse raw API response into WeatherData objects."""
        try:
            forecasts = []
            
            # Extract forecast data from response
            hourly_data = response_data.get('hourly', [])
            if not hourly_data:
                self.warning("No hourly data in response")
                return None
            
            for entry in hourly_data:
                try:
                    time = datetime.fromisoformat(entry['time'])
                    if time < start_time or time > end_time:
                        continue
                        
                    forecast = WeatherData(
                        elaboration_time=time,
                        block_duration=timedelta(hours=interval),
                        temperature=entry['temperature_2m'],
                        precipitation=entry['precipitation'],
                        precipitation_probability=entry['precipitation_probability'],
                        wind_speed=entry['windspeed_10m'],
                        wind_direction=entry['winddirection_10m'],
                        weather_code=str(entry['weathercode']),  # Convert to string since it's a WMO code
                        weather_description='',  # Open-Meteo doesn't provide this
                        thunder_probability=0.0  # Open-Meteo doesn't provide this
                    )
                    forecasts.append(forecast)
                    
                except (KeyError, ValueError) as e:
                    self.warning(f"Error parsing forecast entry: {e}", entry=entry)
                    continue
            
            if not forecasts:
                self.warning("No forecasts found in response for requested time range")
                return None
            
            # Sort forecasts by time
            forecasts.sort(key=lambda x: x.elaboration_time)
            
            return WeatherResponse(data=forecasts, expires=datetime.now(self.utc_tz) + timedelta(hours=1))
            
        except Exception as e:
            self.error("Error parsing weather response", error=str(e))
            return None 

    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: str = None
    ) -> Optional[List[WeatherData]]:
        """Get weather data from Open-Meteo.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecasts
            end_time: End time for forecasts
            club: Optional club identifier (not used for Open-Meteo)
            
        Returns:
            List of WeatherData objects or None if no data found
        """
        try:
            # Calculate time range for fetching data
            now = datetime.now(self.utc_tz)
            hours_ahead = (end_time - now).total_seconds() / 3600
            interval = self.get_block_size(hours_ahead)
            
            # Check cache first
            cached_response = self.cache.get_response(
                service_type=self.service_type,
                latitude=lat,
                longitude=lon,
                start_time=start_time,
                end_time=end_time
            )
            
            if cached_response:
                self.info(
                    "Using cached response",
                    location=f"{lat},{lon}",
                    time_range=f"{start_time.isoformat()} to {end_time.isoformat()}",
                    interval=interval
                )
                return self._parse_response(cached_response['response'], start_time, end_time, interval)
            
            # If not in cache, fetch from API
            self.info(
                "Fetching new data from API",
                coords=(lat, lon),
                time_range=f"{start_time.isoformat()} to {end_time.isoformat()}",
                interval=interval
            )
            
            # Fetch data for the full forecast range
            response_data = self._fetch_forecasts(lat, lon, start_time, end_time)
            if not response_data:
                self.warning("No forecasts found for requested time range")
                return None
            
            # Store the full response in cache
            self.cache.store_response(
                service_type=self.service_type,
                latitude=lat,
                longitude=lon,
                response_data=response_data,
                forecast_start=start_time,
                forecast_end=end_time,
                expires=datetime.now(self.utc_tz) + timedelta(hours=1)
            )
            
            # Parse and return just the requested time range
            response = self._parse_response(response_data, start_time, end_time, interval)
            if response and response.data:
                return response.data
            
            self.warning("No weather data found")
            return None
            
        except Exception as e:
            self.error("Error getting weather data", exc_info=e)
            return None 