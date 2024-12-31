"""Mediterranean weather service implementation."""

import os
import json
import time
import pytz
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import requests

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService, WeatherCode
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import MEDITERRANEAN_SCHEMA

class MediterraneanWeatherService(WeatherService, LoggerMixin):
    """Weather service using OpenWeather API."""
    
    def __init__(self, local_tz, utc_tz):
        """Initialize service with API endpoints and credentials."""
        WeatherService.__init__(self)
        LoggerMixin.__init__(self)
        
        # OpenWeather API configuration
        self.api_key = os.getenv('OPENWEATHER_API_KEY', '92577a95d8e413ac11ed1c1d54b23e60')
        self.endpoint = 'https://api.openweathermap.org/data/2.5'  # Use free 5-day forecast API
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'GolfCal/1.0 github.com/jahonen/golfcal jarkko.ahonen@iki.fi',
        }
        
        # Timezone settings
        self.utc_tz = utc_tz
        self.local_tz = local_tz
        
        # Track API calls
        self._last_api_call = None
        self._min_call_interval = timedelta(seconds=1)

        # Initialize database
        self.db = WeatherDatabase('mediterranean_weather', MEDITERRANEAN_SCHEMA)

    def _calculate_openweather_expiry(self) -> str:
        """Calculate expiry time for OpenWeather data.
        
        OpenWeather 5-day forecast API:
        - Updates every 3 hours
        - Minimum recommended cache time is 10 minutes
        - We'll use 2 hours to be conservative and ensure data freshness
        """
        return (datetime.utcnow() + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')

    def get_weather(self, lat: float, lon: float, date: datetime, duration_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get weather data for location and time."""
        try:
            # Calculate time range
            start_time = date.replace(minute=0, second=0, microsecond=0)
            if duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
            else:
                end_time = start_time + timedelta(hours=4)  # Default to 4 hours

            # Generate list of hours to fetch
            target_hours = []
            current = start_time
            while current <= end_time:
                target_hours.append(current)
                current += timedelta(hours=1)

            # Try to get from cache first
            times_to_fetch = [t.strftime('%Y-%m-%dT%H:%M:%SZ') for t in target_hours]
            location = f"{lat},{lon}"
            fields = [
                'air_temperature', 'precipitation_amount', 'wind_speed',
                'wind_from_direction', 'probability_of_precipitation',
                'probability_of_thunder', 'summary_code'
            ]
            
            weather_data = self.db.get_weather_data(location, times_to_fetch, 'next_1_hours', fields)
            
            if not weather_data:
                # Fetch from API if not in cache
                api_data = self._fetch_from_api(lat, lon, start_time)
                if not api_data:
                    return None
                
                # Parse and store in cache
                parsed_data = self._parse_openweather_data(api_data, start_time, duration_minutes)
                if not parsed_data:
                    return None
                
                # Convert to database format and store
                db_entries = []
                for time_str, data in parsed_data.items():
                    if isinstance(data, list):
                        data = data[0] if data else None
                    if data:
                        entry = {
                            'location': location,
                            'time': time_str,
                            'data_type': 'next_1_hours',
                            'air_temperature': data.get('air_temperature'),
                            'precipitation_amount': data.get('precipitation_amount'),
                            'wind_speed': data.get('wind_speed'),
                            'wind_from_direction': data.get('wind_from_direction'),
                            'probability_of_precipitation': data.get('probability_of_precipitation'),
                            'probability_of_thunder': data.get('probability_of_thunder'),
                            'summary_code': data.get('symbol_code')
                        }
                        db_entries.append(entry)
                
                # Store in cache with calculated expiry
                expires = self._calculate_openweather_expiry()
                self.db.store_weather_data(db_entries, expires=expires)
                
                weather_data = parsed_data

            # Convert cached data to forecast format
            forecasts = []
            for target_time in target_hours:
                time_str = target_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                if time_str in weather_data:
                    data = weather_data[time_str]
                    if isinstance(data, list):
                        data = data[0] if data else None
                    if data:
                        forecast = {
                            'time': target_time,
                            'data_type': 'next_1_hours',
                            'symbol_code': data.get('summary_code'),
                            'air_temperature': data.get('air_temperature'),
                            'precipitation_amount': data.get('precipitation_amount'),
                            'wind_speed': data.get('wind_speed'),
                            'wind_from_direction': data.get('wind_from_direction'),
                            'probability_of_precipitation': data.get('probability_of_precipitation'),
                            'probability_of_thunder': data.get('probability_of_thunder')
                        }
                        forecasts.append(forecast)

            if not forecasts:
                return None

            # Return first forecast's data as the main weather data
            first_forecast = forecasts[0]
            return {
                'forecasts': forecasts,
                'symbol_code': first_forecast['symbol_code'],
                'air_temperature': first_forecast['air_temperature'],
                'precipitation_amount': first_forecast['precipitation_amount'],
                'wind_speed': first_forecast['wind_speed'],
                'wind_from_direction': first_forecast['wind_from_direction'],
                'probability_of_precipitation': first_forecast['probability_of_precipitation'],
                'probability_of_thunder': first_forecast['probability_of_thunder']
            }

        except Exception as e:
            self.logger.error(f"Failed to get Mediterranean weather for {lat},{lon}: {e}", exc_info=True)
            return None

    def _parse_openweather_data(self, data: Dict[str, Any], start_time: datetime, duration_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Parse OpenWeather API response into our format."""
        try:
            if not data or 'list' not in data:
                return None
            
            # Calculate end time
            if duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
            else:
                end_time = start_time + timedelta(hours=4)  # Default to 4 hours
            
            # Parse each forecast
            parsed_data = {}
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
                    symbol_code = self._map_openweather_code(weather_id)
                    
                    parsed_data[forecast_time.strftime('%Y-%m-%dT%H:%M:%SZ')] = {
                        'air_temperature': main.get('temp'),
                        'precipitation_amount': rain.get('3h', 0.0) / 3.0,  # Convert 3h to 1h
                        'wind_speed': wind.get('speed'),
                        'wind_from_direction': wind.get('deg'),
                        'probability_of_precipitation': forecast.get('pop', 0.0) * 100,  # Convert to percentage
                        'probability_of_thunder': 0.0,  # OpenWeather doesn't provide this
                        'symbol_code': symbol_code
                    }
                    
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Failed to parse forecast: {e}")
                    continue
            
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"Failed to parse OpenWeather data: {e}")
            return None

    def _convert_openweather_code(self, code: int, hour: int) -> str:
        """Convert OpenWeather codes to standard codes."""
        is_day = 6 <= hour <= 18
        
        # Group codes based on OpenWeather's ID system
        # https://openweathermap.org/weather-conditions
        code_map = {
            # Clear
            800: WeatherCode.CLEAR_DAY if is_day else WeatherCode.CLEAR_NIGHT,
            
            # Clouds
            801: WeatherCode.FAIR_DAY if is_day else WeatherCode.FAIR_NIGHT,  # few clouds
            802: WeatherCode.PARTLY_CLOUDY_DAY if is_day else WeatherCode.PARTLY_CLOUDY_NIGHT,  # scattered clouds
            803: WeatherCode.CLOUDY,  # broken clouds
            804: WeatherCode.CLOUDY,  # overcast clouds
            
            # Rain
            500: WeatherCode.LIGHT_RAIN,  # light rain
            501: WeatherCode.RAIN,  # moderate rain
            502: WeatherCode.HEAVY_RAIN,  # heavy rain
            503: WeatherCode.HEAVY_RAIN,  # very heavy rain
            504: WeatherCode.HEAVY_RAIN,  # extreme rain
            511: WeatherCode.LIGHT_SLEET,  # freezing rain
            520: WeatherCode.LIGHT_RAIN_SHOWERS_DAY if is_day else WeatherCode.LIGHT_RAIN_SHOWERS_NIGHT,  # light shower rain
            521: WeatherCode.RAIN_SHOWERS_DAY if is_day else WeatherCode.RAIN_SHOWERS_NIGHT,  # shower rain
            522: WeatherCode.HEAVY_RAIN_SHOWERS_DAY if is_day else WeatherCode.HEAVY_RAIN_SHOWERS_NIGHT,  # heavy shower rain
            
            # Thunderstorm
            200: WeatherCode.RAIN_AND_THUNDER,  # thunderstorm with light rain
            201: WeatherCode.RAIN_AND_THUNDER,  # thunderstorm with rain
            202: WeatherCode.HEAVY_RAIN_AND_THUNDER,  # thunderstorm with heavy rain
            
            # Snow
            600: WeatherCode.LIGHT_SNOW,  # light snow
            601: WeatherCode.SNOW,  # snow
            602: WeatherCode.HEAVY_SNOW,  # heavy snow
            
            # Atmosphere
            741: WeatherCode.FOG,  # fog
        }
        
        return code_map.get(code, WeatherCode.CLOUDY)  # Default to cloudy if code not found

    def _fetch_from_api(self, lat: float, lon: float, start_time: datetime) -> Optional[Dict[str, Any]]:
        """Fetch weather data from OpenWeather API.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecast
            
        Returns:
            Raw API response data or None if request failed
        """
        try:
            if not self.api_key:
                self.logger.error("OpenWeather API key not configured")
                return None

            # Get weather data from OpenWeather 5-day forecast API
            forecast_url = f"{self.endpoint}/forecast"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric',  # Use Celsius and meters/sec
            }
            
            self.logger.debug(f"OpenWeather URL: {forecast_url} (params: {params})")
            
            # Respect rate limits
            if self._last_api_call:
                time_since_last = datetime.now() - self._last_api_call
                if time_since_last < self._min_call_interval:
                    sleep_time = (self._min_call_interval - time_since_last).total_seconds()
                    self.logger.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
            
            response = requests.get(
                forecast_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            self._last_api_call = datetime.now()
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"OpenWeather API request failed: {response.status_code}")
                self.logger.debug(f"Response content: {response.text}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to fetch from OpenWeather API: {e}", exc_info=True)
            return None

    def _map_openweather_code(self, code: str) -> str:
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
        try:
            code_map = {
                # Clear conditions
                '800': 'clearsky_day',  # Clear sky
                '801': 'fair_day',      # Few clouds
                '802': 'partlycloudy_day',  # Scattered clouds
                '803': 'cloudy',        # Broken clouds
                '804': 'cloudy',        # Overcast clouds
                
                # Rain
                '500': 'lightrain',     # Light rain
                '501': 'rain',          # Moderate rain
                '502': 'heavyrain',     # Heavy rain
                '503': 'heavyrain',     # Very heavy rain
                '504': 'heavyrain',     # Extreme rain
                '511': 'sleet',         # Freezing rain
                '520': 'lightrainshowers_day',  # Light shower rain
                '521': 'rainshowers_day',       # Shower rain
                '522': 'heavyrainshowers_day',  # Heavy shower rain
                
                # Snow
                '600': 'lightsnow',     # Light snow
                '601': 'snow',          # Snow
                '602': 'heavysnow',     # Heavy snow
                '611': 'sleet',         # Sleet
                '612': 'lightsleet',    # Light shower sleet
                '613': 'heavysleet',    # Shower sleet
                '615': 'lightsleet',    # Light rain and snow
                '616': 'sleet',         # Rain and snow
                '620': 'lightsnowshowers_day',  # Light shower snow
                '621': 'snowshowers_day',       # Shower snow
                '622': 'heavysnow',             # Heavy shower snow
                
                # Thunderstorm
                '200': 'rainandthunder',        # Thunderstorm with light rain
                '201': 'rainandthunder',        # Thunderstorm with rain
                '202': 'heavyrainandthunder',   # Thunderstorm with heavy rain
                '210': 'rainandthunder',        # Light thunderstorm
                '211': 'rainandthunder',        # Thunderstorm
                '212': 'heavyrainandthunder',   # Heavy thunderstorm
                '221': 'heavyrainandthunder',   # Ragged thunderstorm
                '230': 'rainandthunder',        # Thunderstorm with light drizzle
                '231': 'rainandthunder',        # Thunderstorm with drizzle
                '232': 'heavyrainandthunder',   # Thunderstorm with heavy drizzle
                
                # Drizzle
                '300': 'lightrain',     # Light drizzle
                '301': 'rain',          # Drizzle
                '302': 'heavyrain',     # Heavy drizzle
                '310': 'lightrain',     # Light drizzle rain
                '311': 'rain',          # Drizzle rain
                '312': 'heavyrain',     # Heavy drizzle rain
                '313': 'rainshowers_day',  # Shower rain and drizzle
                '314': 'heavyrainshowers_day',  # Heavy shower rain and drizzle
                '321': 'rainshowers_day',  # Shower drizzle
                
                # Atmosphere
                '701': 'fog',           # Mist
                '711': 'fog',           # Smoke
                '721': 'fog',           # Haze
                '731': 'fog',           # Sand/dust whirls
                '741': 'fog',           # Fog
                '751': 'fog',           # Sand
                '761': 'fog',           # Dust
                '762': 'fog',           # Volcanic ash
                '771': 'fog',           # Squalls
                '781': 'fog',           # Tornado
            }
            
            return code_map.get(code, 'cloudy')  # Default to cloudy if code not found
            
        except Exception as e:
            self.logger.warning(f"Failed to map weather code {code}: {e}")
            return 'cloudy'  # Default to cloudy on error