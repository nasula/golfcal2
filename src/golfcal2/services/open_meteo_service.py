"""Weather service implementation using Open-Meteo API.

Source: Open-Meteo
API Documentation: https://open-meteo.com/en/docs
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union, Iterator
from zoneinfo import ZoneInfo
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherCode, WeatherResponse, WeatherError
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.utils.logging_utils import log_execution, EnhancedLoggerMixin, get_logger
from golfcal2.exceptions import (
    GolfCalError,
    APIError,
    APITimeoutError,
    APIRateLimitError,
    APIResponseError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.config.types import AppConfig

@handle_errors(GolfCalError, service="weather", operation="open_meteo")
class OpenMeteoService(WeatherService):
    """Service for handling weather data using Open-Meteo API.
    
    Open-Meteo provides free weather forecast APIs without key requirements.
    Data is updated hourly.
    """

    service_type: str = "open_meteo"
    HOURLY_RANGE: int = 168  # 7 days of hourly forecasts
    SIX_HOURLY_RANGE: int = 240  # 10 days of 6-hourly forecasts

    def __init__(self, timezone: Union[str, ZoneInfo], utc: Union[str, ZoneInfo], config: Dict[str, Any]) -> None:
        """Initialize service.
        
        Args:
            timezone: Local timezone
            utc: UTC timezone
            config: Service configuration
        """
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
            self._last_api_call: Optional[datetime] = None
            self._min_call_interval = timedelta(seconds=1)
            self._last_request_time: float = 0.0

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

    def _map_wmo_code(self, code: int, hour: int) -> WeatherCode:
        """Map WMO weather codes to internal codes.
        
        Args:
            code: WMO weather code from Open-Meteo
            hour: Hour of the day (0-23) to determine day/night
            
        Returns:
            WeatherCode: Internal weather code
        """
        # Determine if it's day or night (simple 6-20 rule)
        is_daytime = 6 <= hour < 20
        
        # Map WMO codes to our internal codes
        # Reference: https://open-meteo.com/en/docs
        code_map = {
            0: WeatherCode.CLEARSKY_DAY if is_daytime else WeatherCode.CLEARSKY_NIGHT,
            1: WeatherCode.FAIR_DAY if is_daytime else WeatherCode.FAIR_NIGHT,
            2: WeatherCode.PARTLYCLOUDY_DAY if is_daytime else WeatherCode.PARTLYCLOUDY_NIGHT,
            3: WeatherCode.CLOUDY,
            45: WeatherCode.FOG,
            48: WeatherCode.FOG,
            51: WeatherCode.LIGHTRAIN,
            53: WeatherCode.RAIN,
            55: WeatherCode.HEAVYRAIN,
            56: WeatherCode.SLEET,
            57: WeatherCode.SLEET,
            61: WeatherCode.LIGHTRAIN,
            63: WeatherCode.RAIN,
            65: WeatherCode.HEAVYRAIN,
            66: WeatherCode.SLEET,
            67: WeatherCode.SLEET,
            71: WeatherCode.LIGHTSNOW,
            73: WeatherCode.SNOW,
            75: WeatherCode.HEAVYSNOW,
            77: WeatherCode.SNOW,
            80: WeatherCode.LIGHTRAINSHOWERS_DAY if is_daytime else WeatherCode.LIGHTRAINSHOWERS_NIGHT,
            81: WeatherCode.RAINSHOWERS_DAY if is_daytime else WeatherCode.RAINSHOWERS_NIGHT,
            82: WeatherCode.HEAVYRAINSHOWERS_DAY if is_daytime else WeatherCode.HEAVYRAINSHOWERS_NIGHT,
            85: WeatherCode.LIGHTSNOWSHOWERS_DAY if is_daytime else WeatherCode.LIGHTSNOWSHOWERS_NIGHT,
            86: WeatherCode.SNOWSHOWERS_DAY if is_daytime else WeatherCode.SNOWSHOWERS_NIGHT,
            95: WeatherCode.THUNDER,
            96: WeatherCode.THUNDER,
            99: WeatherCode.THUNDER
        }
        
        return code_map.get(code, WeatherCode.CLOUDY)  # Default to cloudy if code not found

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
                        'windspeed_10m': windspeed,
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
    ) -> Optional[List[WeatherData]]:
        """Parse OpenMeteo API response into WeatherData objects."""
        try:
            if not isinstance(response_data, dict):
                self.warning("Invalid response data type")
                return None

            hourly = response_data.get('hourly', [])
            if not isinstance(hourly, list):
                self.warning("Invalid hourly data type")
                return None

            forecasts = []
            for entry in hourly:
                try:
                    time = datetime.fromisoformat(entry['time'])
                    
                    # Skip if outside requested range
                    if time < start_time or time > end_time:
                        continue
                        
                    # Skip if not aligned with interval for 6-hourly blocks
                    if interval > 1 and time.hour % interval != 0:
                        continue

                    weather_data = WeatherData(
                        elaboration_time=time,
                        temperature=entry['temperature_2m'],
                        precipitation=entry['precipitation'],
                        precipitation_probability=entry['precipitation_probability'],
                        wind_speed=entry['windspeed_10m'] / 3.6,  # Convert km/h to m/s
                        wind_direction=entry['winddirection_10m'],
                        weather_code=entry['weathercode'],  # Already mapped in _fetch_forecasts
                        symbol_time_range=f"{time.hour:02d}:00-{((time.hour + interval) % 24):02d}:00"
                    )
                    forecasts.append(weather_data)
                except (KeyError, IndexError, ValueError) as e:
                    self.warning(f"Failed to process entry: {e}")
                    continue

            return forecasts if forecasts else None

        except (KeyError, ValueError, TypeError) as e:
            self.error(f"Failed to parse OpenMeteo response: {str(e)}", exc_info=e)
            return None

    def _get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data from Open-Meteo.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecast
            end_time: End time for forecast
            club: Optional club identifier for caching
            
        Returns:
            Optional[WeatherResponse]: Weather data if available
        """
        try:
            # Check if request is beyond maximum forecast range
            now_utc = datetime.now(self.utc_tz)
            hours_ahead = (end_time - now_utc).total_seconds() / 3600
            
            if hours_ahead > self.SIX_HOURLY_RANGE * 24:
                self.warning(
                    "Request beyond maximum forecast range",
                    max_range_hours=self.SIX_HOURLY_RANGE * 24,
                    requested_hours=hours_ahead,
                    end_time=end_time.isoformat()
                )
                return None

            # Determine forecast interval based on time range
            interval = self.get_block_size(hours_ahead)
            
            # Fetch and parse forecast data
            response_data = self._fetch_forecasts(lat, lon, start_time, end_time)
            if not response_data:
                return None
                
            forecasts = self._parse_response(response_data, start_time, end_time, interval)
            if not forecasts:
                return None
                
            return WeatherResponse(
                elaboration_time=now_utc,
                data=forecasts
            )
            
        except Exception as e:
            self.error("Failed to get weather data from Open-Meteo", exc_info=e)
            return None 