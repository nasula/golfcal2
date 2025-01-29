"""
Weather service implementation for Norwegian Meteorological Institute (MET).
"""

import logging
import os
from datetime import datetime, timedelta, timezone
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
from golfcal2.services.weather_database import WeatherResponseCache

class MetWeatherService(WeatherService):
    """Weather service implementation for Norwegian Meteorological Institute (MET)."""

    service_type: str = "met"
    HOURLY_RANGE: int = 48  # 2 days
    SIX_HOURLY_RANGE: int = 240  # 10 days
    MAX_FORECAST_RANGE: int = 216  # 9 days

    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        """Initialize service."""
        super().__init__(local_tz, utc_tz, config)
        
        # Initialize database and cache
        data_dir = config.get('directories', {}).get('data', 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
        
        # Rate limiting configuration
        self._last_request_time: float = 0.0

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

        try:
            url = f"https://api.met.no/weatherapi/locationforecast/2.0/complete"
            headers = {
                'User-Agent': 'GolfCal2/2.0 (https://github.com/jarkko/golfcal2; jarkkoahonen@icloud.com)'
            }
            params = {
                'lat': latitude,
                'lon': longitude
            }
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            if not data:
                self._handle_errors(
                    ErrorCode.WEATHER_ERROR,
                    "Empty response from MET API"
                )
            return data
        except requests.exceptions.Timeout:
            self._handle_errors(
                ErrorCode.TIMEOUT,
                "Request timed out"
            )
        except requests.exceptions.RequestException as e:
            self._handle_errors(
                ErrorCode.WEATHER_REQUEST_ERROR,
                f"Request failed: {str(e)}"
            )

    def _parse_response(self, response_data: Dict[str, Any]) -> Optional[WeatherResponse]:
        """Parse MET API response into WeatherData objects.
        
        Args:
            response_data: Raw response data from MET API
            
        Returns:
            List of WeatherData objects or None if parsing fails
        """
        try:
            if not response_data or 'properties' not in response_data:
                return None
                
            timeseries = response_data['properties']['timeseries']
            if not timeseries:
                return None
                
            weather_data: List[WeatherData] = []
            prev_time: Optional[datetime] = None
            
            for entry in timeseries:
                # Handle 'Z' suffix in timestamp by replacing it with +00:00
                time_str = entry['time'].replace('Z', '+00:00')
                try:
                    time = datetime.fromisoformat(time_str)
                except ValueError:
                    # If that fails, try parsing without timezone and assume UTC
                    time = datetime.strptime(entry['time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                
                if prev_time and time <= prev_time:
                    continue
                    
                data = entry['data']['instant']['details']
                weather_data.append(
                    WeatherData(
                        time=time,
                        temperature=data.get('air_temperature', 0.0),
                        precipitation=data.get('precipitation_amount', 0.0),
                        precipitation_probability=0.0,  # MET doesn't provide this
                        wind_speed=data.get('wind_speed', 0.0),
                        wind_direction=data.get('wind_from_direction', 0.0),
                        weather_code=WeatherCode(self._map_weather_code(data.get('symbol_code', ''))),
                        humidity=data.get('relative_humidity', 0.0),
                        cloud_cover=data.get('cloud_area_fraction', 0.0)
                    )
                )
                prev_time = time
                
            return WeatherResponse(
                data=weather_data,
                elaboration_time=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            raise WeatherError(
                f"Failed to parse Met weather response: {str(e)}",
                str(ErrorCode.WEATHER_PARSE_ERROR)
            )

    def _map_weather_code(self, code: str) -> str:
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
            raise WeatherError(message, str(error_code))