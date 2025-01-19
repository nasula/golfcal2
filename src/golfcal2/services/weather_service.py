"""Weather service implementation."""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo
import os
from functools import lru_cache

from golfcal2.exceptions import (
    WeatherError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherResponse
from golfcal2.services.open_weather_service import OpenWeatherService
from golfcal2.services.met_weather_service import MetWeatherService
from golfcal2.services.open_meteo_service import OpenMeteoService
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.cache.location_cache import WeatherLocationCache

@lru_cache(maxsize=32)
def get_timezone(tz_name: str) -> ZoneInfo:
    """Get cached timezone instance using Python's lru_cache.
    
    Args:
        tz_name: Name of the timezone
        
    Returns:
        Cached ZoneInfo instance
    """
    return ZoneInfo(tz_name)

class WeatherManager:
    """Manager for weather services with lazy loading."""

    def __init__(self, timezone: ZoneInfo, utc: ZoneInfo, config: Dict[str, Any]):
        """Initialize weather manager.
        
        Args:
            timezone: Local timezone
            utc: UTC timezone
            config: Service configuration
        """
        # Use cached timezones
        self.utc = get_timezone('UTC')
        self.timezone = get_timezone(timezone) if isinstance(timezone, str) else timezone
        
        # Store minimal config needed for service creation
        self._service_config = {
            'timezone': self.timezone,
            'api_keys': config.get('api_keys', {}),
            'weather': config.get('weather', {})
        }
        
        # Initialize shared caches lazily
        self._cache = None
        self._location_cache = None
        self._services = {}
        
        # Cache paths
        self._data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self._data_dir, exist_ok=True)

    @property
    def cache(self) -> WeatherResponseCache:
        """Lazy initialization of weather response cache."""
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
            'met': lambda: MetWeatherService(self.timezone, self.utc, self._service_config),
            'open_meteo': lambda: OpenMeteoService(self.timezone, self.utc, self._service_config),
            'openweather': lambda: OpenWeatherService(self.timezone, self.utc, self._service_config) 
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

    def _get_service(self, service_name: str) -> Optional[WeatherService]:
        """Get or create a weather service instance lazily.
        
        Args:
            service_name: Name of the service to get
            
        Returns:
            Weather service instance or None if service cannot be created
        """
        if service_name not in self._services:
            service = self._create_service(service_name)
            if service:
                self._services[service_name] = service
        return self._services.get(service_name)

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
            responsible_service = self._get_service('met')
        # Use OpenMeteo for all other regions (including Iberia)
        else:
            responsible_service = self._get_service('open_meteo')

        if responsible_service:
            try:
                response = responsible_service.get_weather(lat, lon, start_time, end_time, club)
                if response:
                    if isinstance(response, list):
                        # Service returned a list of WeatherData
                        return WeatherResponse(
                            data=response,
                            expires=datetime.now(self.utc) + timedelta(hours=1)
                        )
                    # Service returned a WeatherResponse
                    return response
            except WeatherError as e:
                aggregate_error(str(e), "weather_manager", e.__traceback__)
                # Try OpenWeather as fallback
                fallback = self._get_service('openweather')
                if fallback:
                    try:
                        response = fallback.get_weather(lat, lon, start_time, end_time, club)
                        if response:
                            return response
                    except WeatherError as e2:
                        aggregate_error(str(e2), "weather_manager", e2.__traceback__)
        
        return None