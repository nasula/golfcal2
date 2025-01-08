"""OpenWeather service implementation."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import requests
from zoneinfo import ZoneInfo

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherCode
from golfcal2.exceptions import (
    WeatherError,
    WeatherServiceUnavailable,
    WeatherDataError,
    ErrorCode,
    handle_errors,
    aggregate_error
)
from golfcal2.services.weather_schemas import OPEN_WEATHER_SCHEMA
from golfcal2.utils.database import WeatherDatabase
from golfcal2.utils.rate_limiter import RateLimiter
from golfcal2.utils.time_utils import round_to_hour

logger = logging.getLogger(__name__)

class OpenWeatherService(WeatherService):
    """OpenWeather API implementation.
    
    This service uses OpenWeather's API to provide weather forecasts globally.
    It serves as a fallback service for regions not covered by specialized services.
    """

    @handle_errors(WeatherError, "open_weather", "initialize service")
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        """Initialize OpenWeather service.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Configuration dictionary containing API key
        """
        super().__init__(local_tz, utc_tz)
        
        self.base_url = "https://api.openweathermap.org/data/2.5/"
        self.api_key = config.get('api_keys', {}).get('weather', {}).get('openweather')
        
        if not self.api_key:
            raise WeatherServiceUnavailable(
                "OpenWeather API key not configured",
                aggregate_error("API key not configured", "open_weather", None)
            )
        
        # Initialize database for caching
        self.db = WeatherDatabase('open_weather', OPEN_WEATHER_SCHEMA)
        
        # Initialize rate limiter (60 calls per minute)
        self.rate_limiter = RateLimiter(max_calls=60, time_window=60)
        
        self.set_log_context(service="OpenWeather")
    
    @handle_errors(WeatherError, "open_weather", "make API request")
    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, str],
        error_context: str
    ) -> Dict[str, Any]:
        """Make request to OpenWeather API with rate limiting."""
        # Wait for rate limit
        sleep_time = self.rate_limiter.get_sleep_time()
        if sleep_time > 0:
            logger.debug(f"Rate limit: sleeping for {sleep_time} seconds")
            time.sleep(sleep_time)
        
        url = urljoin(self.base_url, endpoint)
        params['appid'] = self.api_key
        params['units'] = 'metric'
        
        logger.debug(f"OpenWeather URL: {url} (params: {params})")
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            self.rate_limiter.add_call()
            return response.json()
            
        except requests.Timeout:
            raise WeatherServiceUnavailable(
                "OpenWeather API request timed out",
                aggregate_error("Request timed out", "open_weather", None)
            )
        except requests.RequestException as e:
            raise WeatherServiceUnavailable(
                f"OpenWeather API request failed: {str(e)}",
                aggregate_error(str(e), "open_weather", None)
            )
        except ValueError as e:
            raise WeatherServiceUnavailable(
                f"Invalid response from OpenWeather API: {str(e)}",
                aggregate_error(str(e), "open_weather", None)
            )
    
    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> List[WeatherData]:
        """Fetch weather forecasts from OpenWeather API.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecasts
            end_time: End time for forecasts
            
        Returns:
            List of WeatherData objects
        """
        try:
            params = {
                'lat': str(lat),
                'lon': str(lon)
            }
            
            data = self._make_request(
                'forecast',
                params,
                "open_weather",
            )
            
            forecasts = []
            for item in data['list']:
                time = datetime.fromtimestamp(item['dt'], self.utc_tz)
                if start_time <= time <= end_time:
                    forecasts.append(self._parse_forecast(item, time))
            
            return forecasts
            
        except Exception as e:
            raise WeatherServiceUnavailable(
                f"Failed to fetch OpenWeather forecasts: {str(e)}",
                aggregate_error(str(e), "open_weather", e.__traceback__)
            )
    
    def _parse_forecast(
        self,
        data: Dict[str, Any],
        time: datetime
    ) -> WeatherData:
        """Parse OpenWeather forecast data into WeatherData object."""
        try:
            weather = data['weather'][0]
            
            return WeatherData(
                temperature=data['main']['temp'],
                precipitation=data['rain']['3h'] if 'rain' in data else 0.0,
                precipitation_probability=data['pop'] * 100,
                wind_speed=data['wind']['speed'],
                wind_direction=self._get_wind_direction(data['wind']['deg']),
                symbol=self._get_weather_symbol(weather['id'], time),
                elaboration_time=time,
                thunder_probability=self._get_thunder_probability(weather['id'])
            )
            
        except KeyError as e:
            raise WeatherServiceUnavailable(
                f"Invalid forecast data format: {str(e)}",
                aggregate_error(str(error), "open_weather", None)
            )
        except Exception as e:
            raise WeatherServiceUnavailable(
                f"Failed to parse forecast: {str(e)}",
                aggregate_error(str(error), "open_weather", e.__traceback__)
            )
    
    def _get_weather_symbol(
        self,
        code: int,
        time: datetime
    ) -> WeatherCode:
        """Convert OpenWeather code to WeatherCode."""
        with handle_errors(WeatherError, "open_weather", "get weather symbol"):
            # Map OpenWeather codes to our weather codes
            # See: https://openweathermap.org/weather-conditions
            code_map = {
                # Clear
                800: WeatherCode.CLEARSKY_DAY if self._is_daytime(time) else WeatherCode.CLEARSKY_NIGHT,
                
                # Clouds
                801: WeatherCode.FAIR_DAY if self._is_daytime(time) else WeatherCode.FAIR_NIGHT,
                802: WeatherCode.PARTLYCLOUDY_DAY if self._is_daytime(time) else WeatherCode.PARTLYCLOUDY_NIGHT,
                803: WeatherCode.CLOUDY,
                804: WeatherCode.CLOUDY,
                
                # Rain
                500: WeatherCode.LIGHTRAINSUN_DAY if self._is_daytime(time) else WeatherCode.LIGHTRAINSUN_NIGHT,
                501: WeatherCode.RAIN,
                502: WeatherCode.HEAVYRAIN,
                503: WeatherCode.HEAVYRAIN,
                504: WeatherCode.HEAVYRAIN,
                
                # Thunderstorm
                200: WeatherCode.RAINANDTHUNDER,
                201: WeatherCode.RAINANDTHUNDER,
                202: WeatherCode.RAINANDTHUNDER,
                210: WeatherCode.THUNDER,
                211: WeatherCode.THUNDER,
                212: WeatherCode.THUNDER,
                221: WeatherCode.THUNDER,
                230: WeatherCode.RAINANDTHUNDER,
                231: WeatherCode.RAINANDTHUNDER,
                232: WeatherCode.RAINANDTHUNDER
            }
            
            return code_map.get(code, WeatherCode.UNKNOWN)
    
    def _get_thunder_probability(self, code: int) -> float:
        """Get thunder probability based on weather code."""
        with handle_errors(WeatherError, "open_weather", "get thunder probability"):
            # Thunder probabilities based on weather codes
            thunder_map = {
                # Thunderstorm with light rain
                200: 0.8,
                # Thunderstorm with rain
                201: 0.9,
                # Thunderstorm with heavy rain
                202: 1.0,
                # Light thunderstorm
                210: 0.6,
                # Thunderstorm
                211: 0.7,
                # Heavy thunderstorm
                212: 0.8,
                # Ragged thunderstorm
                221: 0.7,
                # Thunderstorm with light drizzle
                230: 0.6,
                # Thunderstorm with drizzle
                231: 0.7,
                # Thunderstorm with heavy drizzle
                232: 0.8
            }
            
            return thunder_map.get(code, 0.0)
    
    def _get_block_size(self, start_time: datetime) -> timedelta:
        """Get block size for OpenWeather forecasts.
        
        OpenWeather provides 3-hour blocks for 5 days.
        """
        return timedelta(hours=3)
    
    def _get_expiry_time(self, elaboration_time: datetime) -> datetime:
        """Get expiry time for OpenWeather data.
        
        OpenWeather updates their forecasts every 6 hours at:
        - 00:00 UTC
        - 06:00 UTC
        - 12:00 UTC
        - 18:00 UTC
        
        We add 15 minutes to ensure the new data is available.
        """
        current = round_to_hour(elaboration_time)
        hours_since_midnight = current.hour
        
        # Find next update time
        if hours_since_midnight < 6:
            next_update = current.replace(hour=6, minute=15)
        elif hours_since_midnight < 12:
            next_update = current.replace(hour=12, minute=15)
        elif hours_since_midnight < 18:
            next_update = current.replace(hour=18, minute=15)
        else:
            next_update = (current + timedelta(days=1)).replace(hour=0, minute=15)
        
        return next_update
    
    def _get_wind_direction(self, degrees: float) -> str:
        """Convert wind degrees to cardinal direction."""
        with handle_errors(WeatherError, "open_weather", "get wind direction"):
            directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            
            # Convert degrees to 16-point compass
            val = int((degrees / 22.5) + 0.5)
            return directions[val % 16]