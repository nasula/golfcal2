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
import requests

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
    HOURLY_RANGE: int = 168  # 7 days
    SIX_HOURLY_RANGE: int = 216  # 9 days
    MAX_FORECAST_RANGE: int = 216  # 9 days

    def __init__(self, local_tz: Union[str, ZoneInfo], utc_tz: Union[str, ZoneInfo], config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize service.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Optional service configuration
        """
        super().__init__(local_tz, utc_tz)
        self.config = config or {}
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
        try:
            if code == 0:  # Clear sky
                return WeatherCode.CLEARSKY_DAY if 6 <= hour < 22 else WeatherCode.CLEARSKY_NIGHT
            elif code == 1:  # Mainly clear
                return WeatherCode.FAIR_DAY if 6 <= hour < 22 else WeatherCode.FAIR_NIGHT
            elif code == 2:  # Partly cloudy
                return WeatherCode.PARTLYCLOUDY_DAY if 6 <= hour < 22 else WeatherCode.PARTLYCLOUDY_NIGHT
            elif code == 3:  # Overcast
                return WeatherCode.CLOUDY
            elif code in (45, 48):  # Foggy
                return WeatherCode.FOG
            elif code in (51, 53, 55):  # Drizzle
                return WeatherCode.LIGHTRAIN
            elif code in (61, 63):  # Rain
                return WeatherCode.RAIN
            elif code == 65:  # Heavy rain
                return WeatherCode.HEAVYRAIN
            elif code in (71, 73, 75):  # Snow
                return WeatherCode.SNOW
            elif code in (77,):  # Snow grains
                return WeatherCode.SLEET
            elif code == 80:  # Light rain showers
                return WeatherCode.LIGHTRAINSHOWERS_DAY if 6 <= hour < 22 else WeatherCode.LIGHTRAINSHOWERS_NIGHT
            elif code == 81:  # Rain showers
                return WeatherCode.RAINSHOWERS_DAY if 6 <= hour < 22 else WeatherCode.RAINSHOWERS_NIGHT
            elif code == 82:  # Heavy rain showers
                return WeatherCode.HEAVYRAINSHOWERS_DAY if 6 <= hour < 22 else WeatherCode.HEAVYRAINSHOWERS_NIGHT
            elif code == 85:  # Snow showers
                return WeatherCode.SNOWSHOWERS_DAY if 6 <= hour < 22 else WeatherCode.SNOWSHOWERS_NIGHT
            elif code == 86:  # Heavy snow showers
                return WeatherCode.HEAVYSNOWSHOWERS_DAY if 6 <= hour < 22 else WeatherCode.HEAVYSNOWSHOWERS_NIGHT
            elif code in (95, 96, 99):  # Thunderstorm
                return WeatherCode.THUNDER
            return WeatherCode.UNKNOWN
        except Exception as e:
            self._handle_errors(
                ErrorCode.WEATHER_PARSE_ERROR,
                f"Failed to map weather code {code}: {str(e)}"
            )
            return WeatherCode.UNKNOWN

    def _fetch_forecasts(self, latitude: float, longitude: float, start_time: datetime, end_time: datetime) -> Optional[Dict[str, Any]]:
        """Fetch forecasts from Open-Meteo API."""
        if (end_time - start_time).total_seconds() / 3600 > self.MAX_FORECAST_RANGE:
            self._handle_errors(
                ErrorCode.WEATHER_ERROR,
                f"Request exceeds maximum forecast range of {self.MAX_FORECAST_RANGE} hours"
            )
            return None

        try:
            url = f"https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': latitude,
                'longitude': longitude,
                'hourly': 'temperature_2m,precipitation,precipitation_probability,weathercode,windspeed_10m,winddirection_10m',
                'timezone': 'UTC',
                'start_date': start_time.date().isoformat(),
                'end_date': end_time.date().isoformat()
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._handle_errors(
                ErrorCode.WEATHER_REQUEST_ERROR,
                f"Failed to fetch weather data: {str(e)}"
            )
            return None

    def _parse_response(self, response_data: Dict[str, Any]) -> Optional[WeatherResponse]:
        """Parse response from Open-Meteo API."""
        try:
            if not isinstance(response_data, dict) or 'hourly' not in response_data:
                self._handle_errors(
                    ErrorCode.WEATHER_PARSE_ERROR,
                    "Invalid response format from Open-Meteo API"
                )
                return None

            hourly = response_data['hourly']
            if not isinstance(hourly, dict):
                self._handle_errors(
                    ErrorCode.WEATHER_PARSE_ERROR,
                    "Invalid hourly data format from Open-Meteo API"
                )
                return None

            times = hourly.get('time', [])
            if not times:
                return None

            weather_data = []
            for i, time_str in enumerate(times):
                try:
                    time = datetime.fromisoformat(time_str)
                    weather_data.append(WeatherData(
                        elaboration_time=time,
                        temperature=hourly['temperature_2m'][i],
                        precipitation=hourly['precipitation'][i],
                        precipitation_probability=hourly['precipitation_probability'][i],
                        wind_speed=hourly['windspeed_10m'][i],
                        wind_direction=hourly['winddirection_10m'][i],
                        weather_code=self._map_wmo_code(hourly['weathercode'][i], time.hour),
                        symbol_time_range=f"{time.hour:02d}:00-{((time.hour + 1) % 24):02d}:00",
                        thunder_probability=self._get_thunder_probability(hourly['weathercode'][i])
                    ))
                except (KeyError, IndexError, ValueError) as e:
                    self._handle_errors(
                        ErrorCode.WEATHER_PARSE_ERROR,
                        f"Failed to parse weather entry: {str(e)}"
                    )

            if not weather_data:
                return None

            return WeatherResponse(
                data=weather_data,
                elaboration_time=datetime.now(self.utc_tz)
            )

        except Exception as e:
            self._handle_errors(
                ErrorCode.WEATHER_PARSE_ERROR,
                f"Failed to parse weather data: {str(e)}"
            )
            return None

    def _get_thunder_probability(self, wmo_code: int) -> float:
        """Get thunder probability based on WMO weather code."""
        # WMO codes for thunderstorms: 95 (slight/moderate), 96 (with hail), 99 (heavy)
        if wmo_code in (95, 96, 99):
            return 80.0 if wmo_code == 99 else 50.0
        return 0.0

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
                
            forecasts = self._parse_response(response_data)
            if not forecasts:
                return None
                
            return forecasts
            
        except Exception as e:
            self.error("Failed to get weather data from Open-Meteo", exc_info=e)
            return None 