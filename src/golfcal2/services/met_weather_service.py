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
from golfcal2.services.weather_types import WeatherData, WeatherResponse, WeatherCode
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

            # Determine forecast interval based on time range
            interval = self.get_block_size(hours_ahead)
            
            # Fetch and parse forecast data
            response_data = self._fetch_forecasts(lat, lon, start_time, end_time)
            if not response_data:
                return None
                
            weather_data = self._parse_response(response_data)
            if not weather_data:
                return None
                
            return weather_data  # Return the WeatherResponse directly
            
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
        except requests.exceptions.RequestException as e:
            self._handle_errors(
                ErrorCode.WEATHER_REQUEST_ERROR,
                f"Failed to fetch weather data: {str(e)}"
            )
            return None

    def _parse_response(self, response_data: Dict[str, Any]) -> Optional[WeatherResponse]:
        """Parse response from MET API."""
        try:
            if not isinstance(response_data, dict) or 'properties' not in response_data:
                self._handle_errors(
                    ErrorCode.WEATHER_PARSE_ERROR,
                    "Invalid response format from MET API"
                )
                return None

            timeseries = response_data.get('properties', {}).get('timeseries', [])
            if not timeseries:
                return None

            weather_data = []
            for entry in timeseries:
                try:
                    time = datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
                    instant = entry.get('data', {}).get('instant', {}).get('details', {})
                    next_hour = entry.get('data', {}).get('next_1_hours', {})
                    next_six_hours = entry.get('data', {}).get('next_6_hours', {})

                    # Get precipitation and its probability
                    precipitation = (
                        next_hour.get('details', {}).get('precipitation_amount')
                        or next_six_hours.get('details', {}).get('precipitation_amount')
                        or 0.0
                    )
                    precipitation_probability = (
                        next_hour.get('details', {}).get('probability_of_precipitation')
                        or next_six_hours.get('details', {}).get('probability_of_precipitation')
                    )
                    
                    # Get thunder probability
                    thunder_probability = (
                        next_hour.get('details', {}).get('probability_of_thunder')
                        or next_six_hours.get('details', {}).get('probability_of_thunder')
                    )

                    # Get symbol code from next_1_hours if available, otherwise from next_6_hours
                    symbol = (
                        next_hour.get('summary', {}).get('symbol_code')
                        or next_six_hours.get('summary', {}).get('symbol_code')
                        or 'cloudy'
                    )

                    # Determine interval based on which forecast is available
                    interval = 1 if 'next_1_hours' in entry.get('data', {}) else 6

                    # Convert time to local timezone for symbol_time_range
                    local_time = time.astimezone(self.local_tz)
                    weather_data.append(WeatherData(
                        elaboration_time=time,
                        temperature=instant.get('air_temperature'),
                        precipitation=precipitation,
                        precipitation_probability=precipitation_probability,
                        thunder_probability=thunder_probability,
                        wind_speed=instant.get('wind_speed'),
                        wind_direction=instant.get('wind_from_direction'),
                        weather_code=self._map_met_code(symbol),
                        symbol_time_range=f"{local_time.hour:02d}:00-{((local_time.hour + interval) % 24):02d}:00"
                    ))
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