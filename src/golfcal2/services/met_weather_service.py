"""
Weather service implementation for Norwegian Meteorological Institute (MET).
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, cast, Iterator
from zoneinfo import ZoneInfo

import requests

from golfcal2.exceptions import ErrorCode
from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import (
    WeatherData, WeatherResponse, WeatherCode, WeatherError,
    WeatherServiceUnavailable, WeatherServiceTimeout, WeatherServiceRateLimited
)
from golfcal2.utils.logging_utils import get_logger

class MetWeatherService(WeatherService):
    """Weather service implementation for Norwegian Meteorological Institute (MET)."""

    service_type: str = "met"
    HOURLY_RANGE: int = 168  # 7 days
    SIX_HOURLY_RANGE: int = 216  # 9 days
    MAX_FORECAST_RANGE: int = 216  # 9 days

    def __init__(self, local_tz: Union[str, ZoneInfo], utc_tz: Union[str, ZoneInfo], config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the service.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Optional service configuration
        """
        super().__init__(local_tz, utc_tz)
        self.config = config or {}
        self.set_log_context(service="met_weather")

    def _get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data from MET.
        
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
            
            if hours_ahead > self.MAX_FORECAST_RANGE:
                self.warning(
                    "Request beyond maximum forecast range",
                    max_range_hours=self.MAX_FORECAST_RANGE,
                    requested_hours=hours_ahead,
                    end_time=end_time.isoformat()
                )
                return None
            
            # Fetch and parse forecast data
            response_data = self._fetch_forecasts(lat, lon, start_time, end_time)
            if not response_data:
                return None
                
            return self._parse_response(response_data)
            
        except Exception as e:
            self.error("Failed to get weather data from MET", exc_info=e)
            return None

    def _fetch_forecasts(self, latitude: float, longitude: float, start_time: datetime, end_time: datetime) -> Optional[Dict[str, Any]]:
        """Fetch forecasts from MET API."""
        if (end_time - start_time).total_seconds() / 3600 > self.MAX_FORECAST_RANGE:
            self._handle_errors(
                ErrorCode.WEATHER_ERROR,
                f"Request exceeds maximum forecast range of {self.MAX_FORECAST_RANGE} hours"
            )
            return None

        try:
            url = f"https://api.met.no/weatherapi/locationforecast/2.0/complete"
            headers = {
                'User-Agent': 'GolfCal/2.0 github.com/jarkko/golfcal2'
            }
            params = {
                'lat': latitude,
                'lon': longitude
            }
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            self._handle_errors(
                ErrorCode.TIMEOUT,
                "Request timed out"
            )
            return None
        except requests.exceptions.RequestException as e:
            self._handle_errors(
                ErrorCode.WEATHER_REQUEST_ERROR,
                f"Request failed: {str(e)}"
            )
            return None

    def _parse_response(self, response_data: Dict[str, Any]) -> Optional[WeatherResponse]:
        """Parse MET API response into WeatherData objects.
        
        Args:
            response_data: Raw response data from MET API
            
        Returns:
            List of WeatherData objects or None if parsing fails
        """
        try:
            weather_data = []
            now_utc = datetime.now(self.utc_tz)
            
            # Get forecast data
            forecast = response_data.get('properties', {}).get('timeseries', [])
            if not forecast:
                self._handle_errors(
                    ErrorCode.WEATHER_PARSE_ERROR,
                    "No forecast data in response"
                )
                return None

            # Parse each forecast entry
            for i, entry in enumerate(forecast):
                try:
                    # Get time and data
                    time = datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
                    data = entry.get('data', {})
                    instant = data.get('instant', {}).get('details', {})
                    
                    # Get block end time from next forecast's start time
                    block_end = None
                    if i < len(forecast) - 1:
                        next_time = datetime.fromisoformat(forecast[i + 1]['time'].replace('Z', '+00:00'))
                        block_end = next_time
                    else:
                        # For last entry, use same duration as previous block
                        block_end = time + (time - prev_time if i > 0 else timedelta(hours=1))
                    
                    block_duration = block_end - time
                    
                    # Get appropriate forecast data block
                    next_block = data.get('next_6_hours' if block_duration.total_seconds() > 3600 else 'next_1_hours', {})
                    if not next_block:
                        continue
                    
                    # Get values with defaults
                    temperature = instant.get('air_temperature', 0.0)
                    precipitation = next_block.get('details', {}).get('precipitation_amount', 0.0)
                    precipitation_probability = next_block.get('details', {}).get('probability_of_precipitation', 0.0)
                    wind_speed = instant.get('wind_speed', 0.0)
                    wind_direction = instant.get('wind_from_direction', 0.0)
                    symbol = next_block.get('summary', {}).get('symbol_code', 'unknown')
                    
                    # Calculate thunder probability based on weather code
                    thunder_probability = 0.0
                    if 'thunder' in symbol.lower():
                        thunder_probability = 50.0  # Default probability for thunder conditions
                    
                    # Convert time to local timezone
                    local_time = time.astimezone(self.local_tz)
                    
                    self.debug(
                        "Processing forecast entry",
                        time=time.isoformat(),
                        block_end=block_end.isoformat(),
                        block_duration=block_duration.total_seconds() / 3600,
                        block_type="hourly" if block_duration.total_seconds() <= 3600 else "6-hour"
                    )
                    
                    weather_data.append(WeatherData(
                        temperature=temperature,
                        precipitation=precipitation,
                        precipitation_probability=precipitation_probability,
                        wind_speed=wind_speed,
                        wind_direction=wind_direction,
                        weather_code=WeatherCode(self._map_met_code(symbol)),
                        time=local_time,
                        thunder_probability=thunder_probability,
                        block_duration=block_duration
                    ))
                    
                    prev_time = time
                except (KeyError, ValueError) as e:
                    self._handle_errors(
                        ErrorCode.WEATHER_PARSE_ERROR,
                        f"Failed to parse weather entry: {e}"
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
                f"Failed to parse weather data: {e}"
            )
            return None

    def _map_met_code(self, code: str) -> str:
        """Map MET symbol code to internal weather code string."""
        # Extract base code without variants (_day, _night, _polartwilight)
        base_code = code.split('_')[0]

        # Map MET codes to internal codes
        # Reference: https://api.met.no/weatherapi/weathericon/2.0/documentation
        if base_code == 'clearsky':
            return WeatherCode.CLEARSKY_DAY.value if 'day' in code else WeatherCode.CLEARSKY_NIGHT.value
        elif base_code == 'fair':
            return WeatherCode.FAIR_DAY.value if 'day' in code else WeatherCode.FAIR_NIGHT.value
        elif base_code == 'partlycloudy':
            return WeatherCode.PARTLYCLOUDY_DAY.value if 'day' in code else WeatherCode.PARTLYCLOUDY_NIGHT.value
        elif base_code == 'cloudy':
            return WeatherCode.CLOUDY.value
        elif base_code == 'fog':
            return WeatherCode.FOG.value
        elif base_code == 'lightrainshowers':
            return WeatherCode.LIGHTRAINSHOWERS_DAY.value if 'day' in code else WeatherCode.LIGHTRAINSHOWERS_NIGHT.value
        elif base_code == 'rainshowers':
            return WeatherCode.RAINSHOWERS_DAY.value if 'day' in code else WeatherCode.RAINSHOWERS_NIGHT.value
        elif base_code == 'heavyrainshowers':
            return WeatherCode.HEAVYRAINSHOWERS_DAY.value if 'day' in code else WeatherCode.HEAVYRAINSHOWERS_NIGHT.value
        elif base_code == 'lightrain':
            return WeatherCode.LIGHTRAIN.value
        elif base_code == 'rain':
            return WeatherCode.RAIN.value
        elif base_code == 'heavyrain':
            return WeatherCode.HEAVYRAIN.value
        elif base_code == 'lightsleet':
            return WeatherCode.LIGHTSLEET.value
        elif base_code == 'sleet':
            return WeatherCode.SLEET.value
        elif base_code == 'heavysleet':
            return WeatherCode.HEAVYSLEET.value
        elif base_code == 'lightsnow':
            return WeatherCode.LIGHTSNOW.value
        elif base_code == 'snow':
            return WeatherCode.SNOW.value
        elif base_code == 'heavysnow':
            return WeatherCode.HEAVYSNOW.value
        elif base_code == 'lightsnowshowers':
            return WeatherCode.LIGHTSNOWSHOWERS_DAY.value if 'day' in code else WeatherCode.LIGHTSNOWSHOWERS_NIGHT.value
        elif base_code == 'snowshowers':
            return WeatherCode.SNOWSHOWERS_DAY.value if 'day' in code else WeatherCode.SNOWSHOWERS_NIGHT.value
        elif base_code == 'heavysnowshowers':
            return WeatherCode.HEAVYSNOWSHOWERS_DAY.value if 'day' in code else WeatherCode.HEAVYSNOWSHOWERS_NIGHT.value
        elif base_code == 'thunder':
            return WeatherCode.THUNDER.value
        return WeatherCode.UNKNOWN.value

    def _handle_errors(self, error_code: ErrorCode, message: str) -> None:
        """Handle errors by raising appropriate exceptions.
        
        Args:
            error_code: Error code
            message: Error message
        """
        if error_code == ErrorCode.TIMEOUT:
            raise WeatherServiceTimeout(message)
        elif error_code == ErrorCode.RATE_LIMITED:
            raise WeatherServiceRateLimited(message)
        elif error_code == ErrorCode.SERVICE_UNAVAILABLE:
            raise WeatherServiceUnavailable(message)
        else:
            raise WeatherError(message, error_code)