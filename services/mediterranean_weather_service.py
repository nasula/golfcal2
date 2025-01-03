"""Mediterranean weather service implementation."""

import os
import json
import time
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import requests

from golfcal2.utils.logging_utils import EnhancedLoggerMixin, log_execution
from golfcal2.services.weather_types import WeatherService, WeatherData, WeatherCode
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import MEDITERRANEAN_SCHEMA

class MediterraneanWeatherService(WeatherService):
    """Weather service using OpenWeather API."""
    
    def __init__(self, local_tz, utc_tz):
        """Initialize service with API endpoints and credentials."""
        super().__init__(local_tz, utc_tz)
        
        # OpenWeather API configuration
        self.api_key = os.getenv('OPENWEATHER_API_KEY', '92577a95d8e413ac11ed1c1d54b23e60')
        self.endpoint = 'https://api.openweathermap.org/data/2.5'  # Use free 5-day forecast API
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)',
        }
        
        # Initialize database
        self.db = WeatherDatabase('mediterranean_weather', MEDITERRANEAN_SCHEMA)
        
        # Rate limiting configuration
        self._last_api_call = None
        self._min_call_interval = timedelta(seconds=1)
        
        self.set_log_context(service="Mediterranean")
    
    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch forecasts from OpenWeather API."""
        try:
            if not self.api_key:
                self.error("OpenWeather API key not configured")
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
            
            response = requests.get(
                forecast_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            self._last_api_call = datetime.now()
            
            if response.status_code != 200:
                self.error(
                    "OpenWeather API request failed",
                    status_code=response.status_code,
                    response=response.text
                )
                return []

            data = response.json()
            if not data or 'list' not in data:
                self.error("Invalid response format from OpenWeather API")
                return []

            forecasts = []
            for forecast in data['list']:
                try:
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
                        self.warning(
                            "Failed to map weather code",
                            code=weather_id,
                            hour=hour,
                            exc_info=str(e)
                        )
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
                    
                except (KeyError, ValueError) as e:
                    self.warning(f"Failed to parse forecast: {e}")
                    continue

            return forecasts
            
        except Exception as e:
            self.error(
                "Failed to fetch OpenWeather data",
                exc_info=e
            )
            return []
    
    def _get_wind_direction(self, degrees: Optional[float]) -> Optional[str]:
        """Convert wind direction from degrees to cardinal direction."""
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
            '314': 'heavyrainshowers_day' if is_day else 'heavyrainshowers_night',
            '321': 'rainshowers_day' if is_day else 'rainshowers_night',
            
            # Atmosphere
            '701': 'fog',
            '711': 'fog',
            '721': 'fog',
            '731': 'fog',
            '741': 'fog',
            '751': 'fog',
            '761': 'fog',
            '762': 'fog',
            '771': 'fog',
            '781': 'fog',
        }
        
        return code_map.get(code, 'cloudy')  # Default to cloudy if code not found