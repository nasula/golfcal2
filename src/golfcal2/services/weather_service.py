"""Weather service base class and manager."""

import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Any, Union
from zoneinfo import ZoneInfo

from golfcal2.services.weather_types import WeatherData, WeatherResponse
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.utils.logging_utils import EnhancedLoggerMixin, get_logger
from golfcal2.exceptions import (
    WeatherError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.services.base_service import WeatherService
from golfcal2.services.met_weather_service import MetWeatherService
from golfcal2.services.open_meteo_service import OpenMeteoService
from golfcal2.services.open_weather_service import OpenWeatherService

@lru_cache(maxsize=32)
def get_timezone(tz_name: str) -> ZoneInfo:
    """Get cached timezone instance using Python's lru_cache.
    
    Args:
        tz_name: Name of the timezone
        
    Returns:
        Cached ZoneInfo instance
    """
    return ZoneInfo(tz_name)

class WeatherManager(EnhancedLoggerMixin):
    """Manager for weather services with lazy loading."""

    def __init__(self, local_tz: Union[str, ZoneInfo], utc_tz: Union[str, ZoneInfo], service_config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize weather manager.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            service_config: Optional service configuration
        """
        super().__init__()
        self.local_tz = local_tz if isinstance(local_tz, ZoneInfo) else ZoneInfo(local_tz)
        self.utc_tz = utc_tz if isinstance(utc_tz, ZoneInfo) else ZoneInfo(utc_tz)
        self._service_config = service_config or {}
        self._data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self._data_dir, exist_ok=True)
        self._cache: Optional[WeatherResponseCache] = None
        self._location_cache: Optional[WeatherLocationCache] = None
        self.services: List[WeatherService] = []

    @property
    def cache(self) -> WeatherResponseCache:
        """Lazy initialization of weather cache."""
        if self._cache is None:
            self._cache = WeatherResponseCache(os.path.join(self._data_dir, 'weather_cache.db'))
        return self._cache

    @property
    def location_cache(self) -> WeatherLocationCache:
        """Lazy initialization of location cache."""
        if self._location_cache is None:
            self._location_cache = WeatherLocationCache(os.path.join(self._data_dir, 'weather_locations.db'))
        return self._location_cache

    def _create_service(self, service_name: str) -> Optional[WeatherService]:
        """Create a weather service instance only when needed.
        
        Args:
            service_name: Name of the service to create
            
        Returns:
            Initialized weather service or None if service cannot be created
        """
        service_map = {
            'met': lambda: MetWeatherService(self.local_tz, self.utc_tz, self._service_config),
            'open_meteo': lambda: OpenMeteoService(self.local_tz, self.utc_tz, self._service_config),
            'openweather': lambda: OpenWeatherService(self.local_tz, self.utc_tz, self._service_config) 
                if self._service_config.get('api_keys', {}).get('weather', {}).get('openweather') 
                else None
        }
        
        service_creator = service_map.get(service_name)
        if not service_creator:
            return None
            
        service = service_creator()
        if service:
            service.cache = self.cache
            service.location_cache = self.location_cache
            
        return service

    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: str = None
    ) -> Optional[WeatherResponse]:
        """Get weather data from the appropriate service based on location.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecasts
            end_time: End time for forecasts
            club: Optional club identifier for region-specific services
            
        Returns:
            WeatherResponse object with data from the appropriate service
        """
        # First, find which service is responsible for this location
        responsible_service = None
        
        # Check MET.no (Nordic region)
        if 55 <= lat <= 72 and 4 <= lon <= 32:  # Nordic region
            responsible_service = self._create_service('met')
        # Use OpenMeteo for all other regions (including Iberia)
        else:
            responsible_service = self._create_service('open_meteo')

        if responsible_service:
            try:
                response = responsible_service.get_weather(lat, lon, start_time, end_time, club)
                if response:
                    # If response is already a WeatherResponse, return it directly
                    if isinstance(response, WeatherResponse):
                        return response
                    # If response is a list of WeatherData, wrap it in WeatherResponse
                    if isinstance(response, list):
                        return WeatherResponse(
                            data=response,
                            elaboration_time=datetime.now(self.utc_tz),
                            expires=datetime.now(self.utc_tz) + timedelta(hours=1)
                        )
                    return None
            except WeatherError as e:
                aggregate_error(str(e), "weather_manager", e.__traceback__)
                # Try OpenWeather as fallback
                fallback = self._create_service('openweather')
                if fallback:
                    try:
                        response = fallback.get_weather(lat, lon, start_time, end_time, club)
                        if response:
                            return response
                    except WeatherError as e2:
                        aggregate_error(str(e2), "weather_manager", e2.__traceback__)

        return None