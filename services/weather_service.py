"""Weather service implementation."""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo
import os

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
from golfcal2.services.cache.weather_cache import WeatherResponseCache
from golfcal2.services.cache.location_cache import WeatherLocationCache

# Module-level timezone caching
DEFAULT_UTC = ZoneInfo('UTC')
_DEFAULT_LOCAL_TZ = None
_TZ_CACHE: Dict[str, ZoneInfo] = {}

def get_timezone(tz_name: str) -> ZoneInfo:
    """Get cached timezone instance.
    
    Args:
        tz_name: Name of the timezone
        
    Returns:
        Cached ZoneInfo instance
    """
    if tz_name not in _TZ_CACHE:
        _TZ_CACHE[tz_name] = ZoneInfo(tz_name)
    return _TZ_CACHE[tz_name]

class WeatherManager:
    """Manager for weather services."""

    def __init__(self, timezone: ZoneInfo, utc: ZoneInfo, config: Dict[str, Any]):
        """Initialize weather manager.
        
        Args:
            timezone: Local timezone
            utc: UTC timezone
            config: Service configuration
        """
        global _DEFAULT_LOCAL_TZ
        
        # Use cached timezones
        self.utc = DEFAULT_UTC
        if isinstance(timezone, str):
            self.timezone = get_timezone(timezone)
        else:
            self.timezone = timezone
            
        if _DEFAULT_LOCAL_TZ is None:
            _DEFAULT_LOCAL_TZ = self.timezone
            
        self.config = config
        self._services = {}
        
        # Initialize shared caches
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
        self.location_cache = WeatherLocationCache(os.path.join(data_dir, 'weather_locations.db'))

    def _create_service(self, service_name: str) -> WeatherService:
        """Create a weather service instance.
        
        Args:
            service_name: Name of the service to create
            
        Returns:
            Initialized weather service
        """
        service = None
        if service_name == 'met':
            service = MetWeatherService(self.timezone, self.utc, self.config)
        elif service_name == 'open_meteo':
            service = OpenMeteoService(self.timezone, self.utc, self.config)
        elif service_name == 'openweather' and self.config.get('api_keys', {}).get('weather', {}).get('openweather'):
            service = OpenWeatherService(self.timezone, self.utc, self.config)
            
        if service:
            service.cache = self.cache
            service.location_cache = self.location_cache
            
        return service

    def _get_service(self, service_name: str) -> Optional[WeatherService]:
        """Get or create a weather service instance.
        
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