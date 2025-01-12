"""
Weather service implementation for Norwegian Meteorological Institute (MET).
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

import requests

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.services.weather_types import WeatherData, WeatherResponse
from golfcal2.utils.logging_utils import get_logger

class MetWeatherService(WeatherService):
    """Weather service implementation for Norwegian Meteorological Institute (MET)."""

    def __init__(self, timezone: ZoneInfo, utc: ZoneInfo, config: Dict[str, Any]):
        """Initialize the service."""
        super().__init__(timezone, utc)
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
        self.location_cache = WeatherLocationCache(os.path.join(data_dir, 'weather_locations.db'))
        self.config = config
        self.set_log_context(service="met_weather")

    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, club: Optional[str] = None) -> Optional[WeatherResponse]:
        """Get weather data from MET."""
        # Check cache first
        cached_response = self.cache.get_response(
            service_type='met',
            latitude=lat,
            longitude=lon,
            start_time=start_time,
            end_time=end_time
        )
        
        if cached_response:
            self.info(
                "Cache hit for MET forecast",
                extra={
                    'coords': (lat, lon),
                    'time_range': f"{start_time.isoformat()} to {end_time.isoformat()}"
                }
            )
            return self._parse_response(cached_response['response'], start_time, end_time, 'hourly')
        
        self.info(
            "Cache miss for MET forecast",
            extra={
                'coords': (lat, lon),
                'time_range': f"{start_time.isoformat()} to {end_time.isoformat()}"
            }
        )
        
        try:
            # Fetch new data
            response = self._fetch_forecast(lat, lon, start_time, end_time)
            if not response:
                return None
                
            # Store in cache
            self.cache.store_response(
                service_type='met',
                latitude=lat,
                longitude=lon,
                response_data=response,
                forecast_start=start_time,
                forecast_end=end_time,
                expires=datetime.now(self.utc_tz) + timedelta(hours=6)
            )
            
            return self._parse_response(response, start_time, end_time, 'hourly')
            
        except Exception as e:
            self.error("Failed to get MET forecast", exc_info=e)
            return None

    def _fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from MET API."""
        try:
            url = f"https://api.met.no/weatherapi/locationforecast/2.0/complete"
            params = {
                'lat': latitude,
                'lon': longitude
            }
            headers = {
                'User-Agent': 'golfcal2/1.0 https://github.com/jahonen/golfcal2'
            }
            
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.error("Failed to fetch MET forecast", exc_info=e)
            return None

    def _parse_response(
        self,
        response: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        interval: str
    ) -> Optional[WeatherResponse]:
        """Parse API response into WeatherResponse object."""
        try:
            forecasts = []
            timeseries = response.get('properties', {}).get('timeseries', [])
            
            # Convert interval to integer
            interval_hours = 1 if interval == 'hourly' else 6
            
            for entry in timeseries:
                time_str = entry.get('time')
                if not time_str:
                    continue
                
                time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                if time < start_time or time > end_time:
                    continue
                
                instant = entry.get('data', {}).get('instant', {}).get('details', {})
                next_hour = entry.get('data', {}).get('next_1_hours', {}).get('details', {})
                next_six_hours = entry.get('data', {}).get('next_6_hours', {}).get('details', {})
                
                if interval == 'hourly' and not next_hour:
                    continue
                if interval == 'six_hourly' and not next_six_hours:
                    continue
                    
                forecast = WeatherData(
                    elaboration_time=time,
                    block_duration=timedelta(hours=interval_hours),
                    temperature=instant.get('air_temperature'),
                    precipitation=next_hour.get('precipitation_amount') if interval == 'hourly' else next_six_hours.get('precipitation_amount'),
                    wind_speed=instant.get('wind_speed'),
                    wind_direction=instant.get('wind_from_direction'),
                    precipitation_probability=next_hour.get('probability_of_precipitation') if interval == 'hourly' else next_six_hours.get('probability_of_precipitation'),
                    thunder_probability=0.0,  # MET doesn't provide this
                    weather_code='cloudy',  # Default to cloudy since MET uses different codes
                    weather_description=''  # MET doesn't provide this
                )
                forecasts.append(forecast)
            
            if not forecasts:
                return None
                
            return WeatherResponse(
                data=forecasts,
                expires=datetime.now(self.utc_tz) + timedelta(hours=6)
            )
        
        except Exception as e:
            self.error("Failed to parse MET response", exc_info=e)
            return None