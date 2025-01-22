"""Weather service base class and manager."""

import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Any, Union
from zoneinfo import ZoneInfo
from pathlib import Path

from golfcal2.services.weather_types import (
    WeatherData, WeatherResponse, WeatherError,
    WeatherServiceUnavailable, WeatherServiceTimeout,
    WeatherServiceRateLimited
)
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.utils.logging_utils import EnhancedLoggerMixin, get_logger
from golfcal2.exceptions import (
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.services.base_service import WeatherService
from golfcal2.services.met_weather_service import MetWeatherService
from golfcal2.services.open_meteo_service import OpenMeteoService

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
        self._service_config = service_config or {}
        
        # Convert timezone strings to ZoneInfo objects
        self.local_tz = get_timezone(local_tz) if isinstance(local_tz, str) else local_tz
        self.utc_tz = get_timezone(utc_tz) if isinstance(utc_tz, str) else utc_tz
        
        # Initialize service factories
        self._service_factories = {
            'met': lambda: MetWeatherService(self.local_tz, self.utc_tz, self._service_config),
            'openmeteo': lambda: OpenMeteoService(self.local_tz, self.utc_tz, self._service_config)
        }
        
        # Initialize services dict
        self._services: Dict[str, Optional[WeatherService]] = {}
        
        # Get cache directory from config or use default
        cache_dir = self._service_config.get('directories', {}).get('cache', os.path.expanduser('~/.cache/golfcal2'))
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize caches
        self._response_cache = WeatherResponseCache(os.path.join(cache_dir, 'weather_responses.db'))
        self._location_cache = WeatherLocationCache()
        
        # Set up logging
        self.set_log_context(service="weather_manager")

    def _create_service(self, service_name: str) -> Optional[WeatherService]:
        """Create a weather service instance.
        
        Args:
            service_name: Name of the service to create
            
        Returns:
            Weather service instance or None if creation fails
        """
        if service_name not in self._service_factories:
            return None
            
        try:
            service = self._service_factories[service_name]()
            self._services[service_name] = service
            return service
        except Exception as e:
            self.error(f"Failed to create {service_name} service", exc_info=e)
            self._services[service_name] = None
            return None

    def get_service(self, service_name: str) -> Optional[WeatherService]:
        """Get a weather service instance.
        
        Args:
            service_name: Name of the service to get
            
        Returns:
            Weather service instance or None if not available
        """
        if service_name not in self._services:
            return self._create_service(service_name)
        return self._services[service_name]

    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        service_name: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data for a location.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time (UTC)
            end_time: End time (UTC)
            service_name: Optional service name to use
            
        Returns:
            Weather response or None if no data available
        """
        # Try to get from cache first
        cache_key = f"{lat:.4f}_{lon:.4f}_{start_time.isoformat()}_{end_time.isoformat()}"
        primary_service = service_name or 'met'
        cached = self._response_cache.get_response(
            service_type=primary_service,
            latitude=lat,
            longitude=lon,
            start_time=start_time,
            end_time=end_time
        )
        if cached:
            return WeatherResponse.from_dict(cached['response'])

        # Try primary service first
        service = self.get_service(primary_service)
        
        if service:
            try:
                response = service.get_weather(lat, lon, start_time, end_time)
                if response:
                    self._response_cache.store_response(
                        service_type=primary_service,
                        latitude=lat,
                        longitude=lon,
                        forecast_start=start_time,
                        forecast_end=end_time,
                        response_data=response.to_dict(),
                        expires=service.get_expiry_time()
                    )
                    return response
            except WeatherError as e:
                self.error(f"Primary service {primary_service} failed", exc_info=e)
                aggregate_error(str(e), "weather_manager", e.__traceback__)

        # Try OpenMeteo as fallback if not already using it
        if primary_service != 'openmeteo':
            fallback = self._create_service('openmeteo')
            if fallback:
                try:
                    response = fallback.get_weather(lat, lon, start_time, end_time)
                    if response:
                        self._response_cache.store_response(
                            service_type='openmeteo',
                            latitude=lat,
                            longitude=lon,
                            forecast_start=start_time,
                            forecast_end=end_time,
                            response_data=response.to_dict(),
                            expires=fallback.get_expiry_time()
                        )
                        return response
                except WeatherError as e2:
                    aggregate_error(str(e2), "weather_manager", e2.__traceback__)
        
        return None