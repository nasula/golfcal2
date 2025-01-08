"""Mediterranean weather service implementation.

Source: AEMET and IPMA APIs
"""

import os
import json
import time
import math
from datetime import datetime, timedelta
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
                        # Convert timestamp to datetime
                        time_str = forecast['dt_txt']
                        forecast_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        forecast_time = forecast_time.replace(tzinfo=self.utc_tz)
                        
                        # Skip if outside our time range
                        if forecast_time < start_time or forecast_time > end_time:
                            continue
                        
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
                            thunder_probability=thunder_prob
                        )
                        forecasts.append(forecast_data)

                return forecasts
                
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
        
        Mediterranean weather service updates their forecasts every 6 hours at:
        - 00:00 UTC
        - 06:00 UTC
        - 12:00 UTC
        - 18:00 UTC
        """
        now = datetime.now(self.utc_tz)
        
        # Calculate next update time
        current_hour = now.hour
        update_hours = [0, 6, 12, 18]
        
        # Find the next update hour
        next_update_hour = next((hour for hour in update_hours if hour > current_hour), update_hours[0])
        
        # If we're past all update hours today, the next update is tomorrow at 00:00
        if next_update_hour <= current_hour:
            next_update = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_update = now.replace(hour=next_update_hour, minute=0, second=0, microsecond=0)
        
        return next_update
    
    @log_execution(level='DEBUG', include_args=True)
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, club: str = None) -> Optional[List[WeatherData]]:
        """Get weather data from Mediterranean weather service."""
        try:
            now_utc = datetime.now(ZoneInfo("UTC"))
            
            # Determine if the start time is more than 48 hours in the future
            is_far_future = (start_time - now_utc).total_seconds() > 48 * 3600
            interval = 6 if is_far_future else 1
            
            # Calculate the base time for fetching weather data
            base_hour = (start_time.hour // interval) * interval
            base_time = start_time.replace(hour=base_hour, minute=0, second=0, microsecond=0)
            
            # Adjust base_time if necessary to ensure we cover the event start
            if base_time > start_time:
                base_time -= timedelta(hours=interval)
            
            # Calculate end time to ensure we cover the event end
            end_hour = min(23, ((end_time.hour + interval - 1) // interval) * interval)  # Ensure hour doesn't exceed 23
            fetch_end_time = end_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            if fetch_end_time < end_time:
                # If we need to go to the next day, add a day and set hour to 0
                fetch_end_time = (fetch_end_time + timedelta(days=1)).replace(hour=0)
            
            # Check if we have cached data
            if club and self.cache:
                location = f"{lat:.4f},{lon:.4f}"
                times = [base_time.strftime('%Y-%m-%dT%H:%M:%S+00:00')]
                fields = ['air_temperature', 'precipitation_amount', 'probability_of_precipitation', 'wind_speed', 'wind_from_direction', 'summary_code', 'probability_of_thunder']
                cached_data = self.cache.get_weather_data(location, times, 'hourly', fields)
                if cached_data:
                    # Convert cached data to WeatherData objects
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
                            block_duration=timedelta(hours=interval)
                        )
                        forecasts.append(forecast)
                    return forecasts
            
            # Fetch data from API
            forecasts = self._fetch_forecasts(lat, lon, base_time, fetch_end_time)
            if not forecasts:
                return None
            
            # Set block duration for each forecast
            for forecast in forecasts:
                forecast.block_duration = timedelta(hours=interval)
            
            # Cache the results
            if club and self.cache:
                # Convert forecasts to database format
                cache_data = []
                location = f"{lat:.4f},{lon:.4f}"
                for forecast in forecasts:
                    cache_data.append({
                        'location': location,
                        'time': forecast.elaboration_time.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                        'data_type': 'hourly',
                        'air_temperature': forecast.temperature,
                        'precipitation_amount': forecast.precipitation,
                        'probability_of_precipitation': forecast.precipitation_probability,
                        'wind_speed': forecast.wind_speed,
                        'wind_from_direction': forecast.wind_direction,
                        'summary_code': forecast.symbol,
                        'probability_of_thunder': forecast.thunder_probability
                    })
                self.cache.store_weather_data(
                    cache_data,
                    expires=(now_utc + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                    last_modified=now_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                )
            
            return forecasts
        except Exception as e:
            self.error(f"Failed to get weather data: {e}")
            return None
            
    def _parse_response(self, data: Dict[str, Any], start_time: datetime, end_time: datetime, interval: int) -> List[WeatherData]:
        """Parse weather data from Mediterranean weather service response."""
        try:
            forecasts = []
            timeseries = data.get('properties', {}).get('timeseries', [])
            
            for entry in timeseries:
                time_str = entry.get('time')
                if not time_str:
                    continue
                
                time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                
                # Only include times within our range
                if time < start_time or time > end_time:
                    continue
                
                # Skip entries not in the requested interval
                if time.hour % interval != start_time.hour % interval:
                    continue
                
                forecast = WeatherData(
                    elaboration_time=time,
                    temperature=entry.get('temperature'),
                    precipitation=entry.get('precipitation'),
                    wind_speed=entry.get('wind_speed'),
                    wind_direction=entry.get('wind_direction'),
                    precipitation_probability=entry.get('precipitation_probability'),
                    thunder_probability=entry.get('thunder_probability'),
                    symbol=entry.get('symbol', 'clearsky_day'),
                    block_duration=timedelta(hours=interval)
                )
                forecasts.append(forecast)
            
            return forecasts
        except Exception as e:
            self.error(f"Failed to parse weather data: {e}")
            return []