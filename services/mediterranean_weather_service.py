"""Mediterranean weather service implementation."""

import os
import json
import time
import sqlite3
import pytz
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import requests

from golfcal.utils.logging_utils import LoggerMixin
from golfcal.services.weather_service import WeatherService, WeatherCode

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
    
    def get_weather(
        self,
        lat: float,
        lon: float,
        teetime: datetime,
        duration_minutes: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get weather data for given coordinates and date."""
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
            
            response = requests.get(
                forecast_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_openweather_data(data, teetime, duration_minutes)
            else:
                self.logger.error(f"OpenWeather API request failed: {response.status_code}")
                self.logger.debug(f"Response content: {response.text}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error in get_weather: {e}")
            return None
    
    def _parse_openweather_data(self, data: Dict[str, Any], teetime: datetime, duration_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Parse OpenWeather data."""
        try:
            # Get all 3-hour forecasts
            forecasts = data.get('list', [])
            if not forecasts:
                return None
            
            # Calculate event duration
            event_duration = duration_minutes or 180  # Default to 3 hours
            event_end = teetime + timedelta(minutes=event_duration)
            
            # Find forecasts within the event duration
            event_forecasts = []
            
            # Create a list of target 3-hour blocks we want forecasts for
            target_hours = []
            current_time = teetime
            while current_time <= event_end:
                # Round to nearest 3-hour block
                rounded_hour = (current_time.hour // 3) * 3
                target_time = current_time.replace(hour=rounded_hour, minute=0)
                if target_time not in target_hours:
                    target_hours.append(target_time)
                current_time += timedelta(hours=3)
            
            # Find the closest forecast for each target hour
            for target_time in target_hours:
                closest_forecast = min(
                    forecasts,
                    key=lambda x: abs(
                        datetime.fromtimestamp(x['dt'], tz=self.utc_tz).astimezone(teetime.tzinfo) - target_time
                    )
                )
                
                weather = closest_forecast['weather'][0]
                rain_3h = closest_forecast.get('rain', {}).get('3h', 0)
                
                forecast_data = {
                    'time': target_time,
                    'data_type': 'next_3_hours',
                    'symbol_code': self._convert_openweather_code(weather['id'], target_time.hour),
                    'air_temperature': closest_forecast['main']['temp'],
                    'precipitation_amount': rain_3h,  # Use 3h rain data directly
                    'wind_speed': closest_forecast['wind']['speed'],
                    'wind_from_direction': closest_forecast['wind']['deg'],
                    'probability_of_precipitation': closest_forecast.get('pop', 0) * 100,  # Convert to percentage
                    'probability_of_thunder': 0.0  # OpenWeather doesn't provide this directly
                }
                event_forecasts.append(forecast_data)
            
            if not event_forecasts:
                # If no forecasts found, use the first available forecast
                closest_forecast = min(
                    forecasts,
                    key=lambda x: abs(
                        datetime.fromtimestamp(x['dt'], tz=self.utc_tz).astimezone(teetime.tzinfo) - teetime
                    )
                )
                weather = closest_forecast['weather'][0]
                rain_3h = closest_forecast.get('rain', {}).get('3h', 0)
                
                return {
                    'symbol_code': self._convert_openweather_code(weather['id'], teetime.hour),
                    'air_temperature': closest_forecast['main']['temp'],
                    'precipitation_amount': rain_3h,  # Use 3h rain data directly
                    'wind_speed': closest_forecast['wind']['speed'],
                    'wind_from_direction': closest_forecast['wind']['deg'],
                    'probability_of_precipitation': closest_forecast.get('pop', 0) * 100,  # Convert to percentage
                    'probability_of_thunder': 0.0  # OpenWeather doesn't provide this directly
                }
            
            # Return the first forecast's data as the main weather data
            first_forecast = event_forecasts[0]
            result = {
                'forecasts': event_forecasts,
                'symbol_code': first_forecast['symbol_code'],
                'air_temperature': first_forecast['air_temperature'],
                'precipitation_amount': first_forecast['precipitation_amount'],
                'wind_speed': first_forecast['wind_speed'],
                'wind_from_direction': first_forecast['wind_from_direction'],
                'probability_of_precipitation': first_forecast['probability_of_precipitation'],
                'probability_of_thunder': first_forecast['probability_of_thunder']
            }
            return result
            
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