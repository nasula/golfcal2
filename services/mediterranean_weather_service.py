"""Mediterranean weather service implementation.

Source: AEMET and IPMA APIs
"""

import os
import json
import time
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from golfcal2.utils.logging_utils import EnhancedLoggerMixin, log_execution
from golfcal2.services.weather_types import WeatherService, WeatherData, WeatherCode
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import MEDITERRANEAN_SCHEMA
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

class MediterraneanWeatherService(WeatherService):
    """Weather service using OpenWeather API."""
    
    def __init__(self, local_tz, utc_tz, config):
        """Initialize service with API endpoints and credentials.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Application configuration
        """
        super().__init__(local_tz, utc_tz)
        
        with handle_errors(WeatherError, "mediterranean_weather", "initialize service"):
            # OpenWeather API configuration
            self.api_key = config.global_config['api_keys']['weather']['openweather']
            if not self.api_key:
                error = WeatherError(
                    "OpenWeather API key not configured",
                    ErrorCode.CONFIG_MISSING,
                    {"setting": "api_keys.weather.openweather"}
                )
                aggregate_error(str(error), "mediterranean_weather", None)
                raise error
                
            self.endpoint = 'https://api.openweathermap.org/data/2.5'  # Use free 5-day forecast API
            self.headers = {
                'Accept': 'application/json',
                'User-Agent': 'GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)',
            }
            
            # Initialize database and cache
            self.db = WeatherDatabase('mediterranean_weather', MEDITERRANEAN_SCHEMA)
            self.cache = self.db  # Use database as cache
            
            # Rate limiting configuration
            self._last_api_call = None
            self._min_call_interval = timedelta(seconds=1)
            
            self.set_log_context(service="Mediterranean")
    
    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch forecasts from OpenWeather API."""
        with handle_errors(
            WeatherError,
            "mediterranean_weather",
            f"fetch forecasts for coordinates ({lat}, {lon})",
            lambda: []  # Fallback to empty list on error
        ):
            if not self.api_key:
                error = WeatherError(
                    "OpenWeather API key not configured",
                    ErrorCode.CONFIG_MISSING,
                    {"setting": "OPENWEATHER_API_KEY"}
                )
                aggregate_error(str(error), "mediterranean_weather", None)
                return []

            # Get weather data from OpenWeather 5-day forecast API
            forecast_url = f"{self.endpoint}/forecast"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric',  # Use Celsius and meters/sec
            }
            
            self.debug(
                "OpenWeather URL",
                url=forecast_url,
                params=params
            )
            
            # Respect rate limits
            if self._last_api_call:
                time_since_last = datetime.now() - self._last_api_call
                if time_since_last < self._min_call_interval:
                    sleep_time = (self._min_call_interval - time_since_last).total_seconds()
                    self.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
            
            try:
                response = requests.get(
                    forecast_url,
                    params=params,
                    headers=self.headers,
                    timeout=10
                )
                
                self._last_api_call = datetime.now()
                
                if response.status_code == 429:  # Too Many Requests
                    error = APIRateLimitError(
                        "OpenWeather API rate limit exceeded",
                        retry_after=int(response.headers.get('Retry-After', 60))
                    )
                    aggregate_error(str(error), "mediterranean_weather", None)
                    return []
                
                if response.status_code != 200:
                    error = APIResponseError(
                        f"OpenWeather API request failed with status {response.status_code}",
                        response=response
                    )
                    aggregate_error(str(error), "mediterranean_weather", None)
                    return []

                data = response.json()
                if not data or 'list' not in data:
                    error = WeatherError(
                        "Invalid response format from OpenWeather API",
                        ErrorCode.INVALID_RESPONSE,
                        {"response": data}
                    )
                    aggregate_error(str(error), "mediterranean_weather", None)
                    return []

                forecasts = []
                for forecast in data['list']:
                    with handle_errors(
                        WeatherError,
                        "mediterranean_weather",
                        "process forecast entry",
                        lambda: None
                    ):
                        # Convert timestamp to datetime (OpenWeather returns UTC times)
                        time_str = forecast['dt_txt']
                        forecast_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        forecast_time = forecast_time.replace(tzinfo=self.utc_tz)
                        
                        # Calculate block end time (in UTC)
                        block_end_time = forecast_time + timedelta(hours=3)
                        
                        # Include block if it overlaps with our time range
                        # (block starts before range ends AND block ends after range starts)
                        # Note: start_time and end_time are already in UTC
                        if forecast_time <= end_time and block_end_time >= start_time:
                            # Extract weather data
                            main = forecast.get('main', {})
                            wind = forecast.get('wind', {})
                            weather = forecast.get('weather', [{}])[0]
                            rain = forecast.get('rain', {})
                            
                            # Map OpenWeather codes to our codes
                            weather_id = str(weather.get('id', '800'))  # Default to clear sky
                            hour = forecast_time.hour
                            try:
                                symbol_code = self._map_openweather_code(weather_id, hour)
                            except Exception as e:
                                error = WeatherError(
                                    f"Failed to map weather code: {str(e)}",
                                    ErrorCode.VALIDATION_FAILED,
                                    {
                                        "code": weather_id,
                                        "hour": hour,
                                        "forecast_time": forecast_time.isoformat()
                                    }
                                )
                                aggregate_error(str(error), "mediterranean_weather", e.__traceback__)
                                continue

                            # Calculate thunder probability based on weather code
                            thunder_prob = 0.0
                            if weather_id.startswith('2'):  # 2xx codes are thunderstorm conditions
                                # Convert weather code to probability:
                                # 200-202: Light to heavy thunderstorm with rain
                                # 210-212: Light to heavy thunderstorm
                                # 221: Ragged thunderstorm
                                # 230-232: Thunderstorm with drizzle
                                intensity_map = {
                                    '200': 30.0,  # Light thunderstorm
                                    '201': 60.0,  # Thunderstorm
                                    '202': 90.0,  # Heavy thunderstorm
                                    '210': 20.0,  # Light thunderstorm
                                    '211': 50.0,  # Thunderstorm
                                    '212': 80.0,  # Heavy thunderstorm
                                    '221': 40.0,  # Ragged thunderstorm
                                    '230': 25.0,  # Light thunderstorm with drizzle
                                    '231': 45.0,  # Thunderstorm with drizzle
                                    '232': 65.0   # Heavy thunderstorm with drizzle
                                }
                                thunder_prob = intensity_map.get(weather_id, 50.0)

                            forecast_data = WeatherData(
                                temperature=main.get('temp'),
                                precipitation=rain.get('3h', 0.0) / 3.0,  # Convert 3h to 1h
                                precipitation_probability=forecast.get('pop', 0.0) * 100,  # Convert to percentage
                                wind_speed=wind.get('speed'),
                                wind_direction=self._get_wind_direction(wind.get('deg')),
                                symbol=symbol_code,
                                elaboration_time=forecast_time,
                                thunder_probability=thunder_prob,
                                block_duration=timedelta(hours=3)  # OpenWeather uses 3-hour blocks
                            )
                            forecasts.append(forecast_data)

                return sorted(forecasts, key=lambda x: x.elaboration_time)
                
            except requests.exceptions.Timeout:
                error = APITimeoutError(
                    "OpenWeather API request timed out",
                    {"url": forecast_url}
                )
                aggregate_error(str(error), "mediterranean_weather", None)
                return []
            except requests.exceptions.RequestException as e:
                error = APIError(
                    f"OpenWeather API request failed: {str(e)}",
                    ErrorCode.REQUEST_FAILED,
                    {"url": forecast_url}
                )
                aggregate_error(str(error), "mediterranean_weather", e.__traceback__)
                return []
    
    def _get_wind_direction(self, degrees: Optional[float]) -> Optional[str]:
        """Convert wind direction from degrees to cardinal direction."""
        with handle_errors(
            WeatherError,
            "mediterranean_weather",
            f"get wind direction from {degrees} degrees",
            lambda: None  # Fallback to None on error
        ):
            if degrees is None:
                return None
                
            directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
            index = round(degrees / 45) % 8
            return directions[index]
    
    def _map_openweather_code(self, code: str, hour: int) -> str:
        """Map OpenWeather API codes to our weather codes.
        
        OpenWeather codes:
        - 800: Clear sky
        - 801: Few clouds (11-25%)
        - 802: Scattered clouds (25-50%)
        - 803: Broken clouds (51-84%)
        - 804: Overcast clouds (85-100%)
        - 500s: Rain
        - 600s: Snow
        - 200s: Thunderstorm
        - 300s: Drizzle
        - 700s: Atmosphere (mist, fog, etc)
        """
        with handle_errors(
            WeatherError,
            "mediterranean_weather",
            f"map weather code {code}",
            lambda: WeatherCode.CLOUDY  # Fallback to cloudy on error
        ):
            is_day = 6 <= hour <= 18
            
            code_map = {
                # Clear conditions
                '800': 'clearsky_day' if is_day else 'clearsky_night',
                '801': 'fair_day' if is_day else 'fair_night',
                '802': 'partlycloudy_day' if is_day else 'partlycloudy_night',
                '803': 'cloudy',
                '804': 'cloudy',
                
                # Rain
                '500': 'lightrain',
                '501': 'rain',
                '502': 'heavyrain',
                '503': 'heavyrain',
                '504': 'heavyrain',
                '511': 'sleet',
                '520': 'lightrainshowers_day' if is_day else 'lightrainshowers_night',
                '521': 'rainshowers_day' if is_day else 'rainshowers_night',
                '522': 'heavyrainshowers_day' if is_day else 'heavyrainshowers_night',
                
                # Snow
                '600': 'lightsnow',
                '601': 'snow',
                '602': 'heavysnow',
                '611': 'sleet',
                '612': 'lightsleet',
                '613': 'heavysleet',
                '615': 'lightsleet',
                '616': 'sleet',
                '620': 'lightsnowshowers_day' if is_day else 'lightsnowshowers_night',
                '621': 'snowshowers_day' if is_day else 'snowshowers_night',
                '622': 'heavysnow',
                
                # Thunderstorm
                '200': 'rainandthunder',
                '201': 'rainandthunder',
                '202': 'heavyrainandthunder',
                '210': 'rainandthunder',
                '211': 'rainandthunder',
                '212': 'heavyrainandthunder',
                '221': 'heavyrainandthunder',
                '230': 'rainandthunder',
                '231': 'rainandthunder',
                '232': 'heavyrainandthunder',
                
                # Drizzle
                '300': 'lightrain',
                '301': 'rain',
                '302': 'heavyrain',
                '310': 'lightrain',
                '311': 'rain',
                '312': 'heavyrain',
                '313': 'rainshowers_day' if is_day else 'rainshowers_night',
            }
            
            return code_map.get(code, 'cloudy')  # Default to cloudy if code not found
    
    def get_block_size(self, hours_ahead: float) -> int:
        """Get block size for Mediterranean forecasts.
        
        Always uses 3-hour blocks
        """
        return 3
    
    def get_expiry_time(self) -> datetime:
        """Get expiry time for Mediterranean weather data.
        
        OpenWeather updates their 5-day/3-hour forecast data every hour.
        We'll set expiry to the next hour to ensure fresh data.
        """
        now = datetime.now(self.utc_tz)
        
        # Set expiry to the next hour
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        return next_hour
    
    @log_execution(level='DEBUG', include_args=True)
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, club: str = None) -> Optional[List[WeatherData]]:
        """Get weather data from OpenWeather API."""
        try:
            # Ensure we have timezone-aware datetimes
            if start_time.tzinfo is None or end_time.tzinfo is None:
                raise ValueError("start_time and end_time must be timezone-aware")
            
            now_utc = datetime.now(self.utc_tz)
            
            # Use the timezone from the start_time parameter for all local time operations
            local_tz = start_time.tzinfo
            self.debug(
                "Using timezone for weather data",
                timezone=str(local_tz),
                coordinates=f"({lat}, {lon})"
            )
            
            # Check forecast range - OpenWeather provides:
            # - 3-hour blocks for 5 days
            hours_ahead = (start_time - now_utc).total_seconds() / 3600
            if hours_ahead > 120:  # 5 days
                self.info(
                    "Requested time beyond OpenWeather forecast range",
                    requested_time=start_time.isoformat(),
                    hours_ahead=hours_ahead,
                    max_hours=120
                )
                return None
            
            # Always use 3-hour blocks for OpenWeather
            interval = 3
            
            # Use data type based on interval
            data_type = 'hourly'  # OpenWeather always provides hourly data
            
            # For 3-hour blocks, align start and end times to block boundaries in local time
            local_start = start_time.astimezone(local_tz)
            block_start = ((local_start.hour) // 3) * 3
            base_time = local_start.replace(hour=block_start, minute=0, second=0, microsecond=0)
            base_time = base_time.astimezone(self.utc_tz)  # Convert to UTC after aligning
            
            # Round up end time to next 3-hour block in local time
            local_end = end_time.astimezone(local_tz)
            block_end = ((local_end.hour + 2) // 3) * 3
            if block_end == 24:  # Handle case where we need the next day
                fetch_end_time = (local_end + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                fetch_end_time = local_end.replace(hour=block_end, minute=0, second=0, microsecond=0)
            fetch_end_time = fetch_end_time.astimezone(self.utc_tz)  # Convert to UTC after aligning
            
            self.debug(
                "Using forecast interval",
                hours_ahead=hours_ahead,
                interval=interval,
                aligned_start=base_time.isoformat(),
                aligned_end=fetch_end_time.isoformat()
            )
            
            # Check cache first
            location = f"{lat:.4f},{lon:.4f}"
            # Generate a list of times to check in cache
            cache_times = []
            current_time = base_time
            while current_time <= fetch_end_time:
                cache_times.append(current_time.isoformat())
                current_time += timedelta(hours=interval)
                
            fields = ['air_temperature', 'precipitation_amount', 'probability_of_precipitation', 
                     'wind_speed', 'wind_from_direction', 'summary_code', 'probability_of_thunder',
                     'block_duration_hours']
            
            self.debug(
                "Checking cache",
                location=location,
                times=cache_times
            )

            cached_data = self.db.get_weather_data(location, cache_times, data_type, fields)
            if cached_data and len(cached_data) == len(cache_times):
                self.info(
                    "Cache hit",
                    location=location,
                    start_time=base_time.isoformat(),
                    end_time=fetch_end_time.isoformat(),
                    block_count=len(cached_data)
                )
                return self._process_cached_data(cached_data)

            self.info(
                "Cache miss",
                location=location,
                start_time=base_time.isoformat(),
                end_time=fetch_end_time.isoformat(),
                cached_count=len(cached_data) if cached_data else 0,
                expected_count=len(cache_times)
            )
            
            # Get the forecasts
            forecasts = self._fetch_forecasts(lat, lon, base_time, fetch_end_time)
            if not forecasts:
                return None
                
            # Sort forecasts by time
            forecasts.sort(key=lambda x: x.elaboration_time)
            
            # Update cache with new forecasts
            try:
                cache_data = []
                for forecast in forecasts:
                    cache_entry = {
                        'location': location,
                        'time': forecast.elaboration_time.isoformat(),
                        'data_type': data_type,
                        'air_temperature': forecast.temperature,
                        'precipitation_amount': forecast.precipitation,
                        'probability_of_precipitation': forecast.precipitation_probability,
                        'wind_speed': forecast.wind_speed,
                        'wind_from_direction': forecast.wind_direction,
                        'summary_code': forecast.symbol,
                        'probability_of_thunder': forecast.thunder_probability,
                        'block_duration_hours': interval
                    }
                    cache_data.append(cache_entry)
                
                if cache_data:  # Only store if we have data
                    self.debug(
                        "Storing forecasts in cache",
                        count=len(cache_data),
                        data_type=data_type,
                        block_hours=[interval] * len(cache_data)
                    )
                    
                    # Calculate expiry time based on OpenWeather's update schedule
                    expires = self.get_expiry_time()
                    
                    self.debug(
                        "Setting cache expiry",
                        expires=expires.isoformat()
                    )
                    
                    self.db.store_weather_data(
                        cache_data,
                        expires=expires.isoformat(),
                        last_modified=now_utc.isoformat()
                    )
            except Exception as e:
                self.warning(f"Failed to update cache: {e}")
            
            return forecasts
        except Exception as e:
            self.error(f"Failed to get weather data: {e}")
            return None
            
    def _process_cached_data(self, cached_data: Dict[str, Dict[str, Any]]) -> List[WeatherData]:
        """Process cached weather data into WeatherData objects.
        
        Args:
            cached_data: Dictionary mapping time strings to weather data dictionaries
            
        Returns:
            List of WeatherData objects sorted by time
        """
        forecasts = []
        for time_str, data in cached_data.items():
            time = datetime.fromisoformat(time_str)
            forecast = WeatherData(
                temperature=data['air_temperature'],
                precipitation=data['precipitation_amount'],
                precipitation_probability=data['probability_of_precipitation'],
                wind_speed=data['wind_speed'],
                wind_direction=data['wind_from_direction'],
                symbol=data['summary_code'],
                elaboration_time=time,
                thunder_probability=data['probability_of_thunder'],
                block_duration=timedelta(hours=data.get('block_duration_hours', 3))  # Default to 3 hours
            )
            forecasts.append(forecast)
        
        return sorted(forecasts, key=lambda x: x.elaboration_time)