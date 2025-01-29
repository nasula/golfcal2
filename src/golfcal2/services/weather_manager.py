from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from golfcal2.utils.logging_utils import EnhancedLoggerMixin
from golfcal2.services.base_service import WeatherService
from golfcal2.services.met_weather_service import MetWeatherService
from golfcal2.services.open_meteo_service import OpenMeteoService
from golfcal2.services.weather_types import (
    WeatherResponse, WeatherError, WeatherServiceUnavailable,
    WeatherServiceTimeout, WeatherServiceRateLimited
)
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.services.mock_weather_service import MockWeatherService

class WeatherManager(EnhancedLoggerMixin):
    """Weather service manager."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        """Initialize manager."""
        super().__init__()
        self.local_tz = local_tz
        self.utc_tz = utc_tz
        self.config = config
        self.set_log_context(service="weather_manager")
        
        # Initialize services
        self._service_factories = {
            'met': lambda: MetWeatherService(self.local_tz, self.utc_tz, self.config),
            'mock': lambda: MockWeatherService(self.local_tz, self.utc_tz, self.config),
            'openmeteo': lambda: OpenMeteoService(self.local_tz, self.utc_tz, self.config)
        }
        
        # Initialize services dict
        self.services: Dict[str, Optional[WeatherService]] = {}
        
        # Set primary service
        primary_name = config.get('weather_service', 'met')
        self.primary_service = self._create_service(primary_name)
        if not self.primary_service:
            self.primary_service = self._create_service('met')  # Fallback to MET
        
        # Initialize cache paths
        self._cache_dir = config.get('directories', {}).get('cache', os.path.expanduser('~/.cache/golfcal2'))
        os.makedirs(self._cache_dir, exist_ok=True)
        
        # Initialize caches
        self._response_cache: Optional[WeatherResponseCache] = None

    @property
    def response_cache(self) -> WeatherResponseCache:
        """Get response cache, initializing if needed.
        
        Returns:
            WeatherResponseCache instance
        """
        if self._response_cache is None:
            self._response_cache = WeatherResponseCache(os.path.join(self._cache_dir, 'weather_responses.db'))
        return self._response_cache

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
            self.services[service_name] = service
            return service
        except Exception as e:
            self.error(f"Failed to create {service_name} service", exc_info=e)
            self.services[service_name] = None
            return None

    def get_service(self, service_name: str) -> Optional[WeatherService]:
        """Get a weather service instance.
        
        Args:
            service_name: Name of the service to get
            
        Returns:
            Weather service instance or None if not available
        """
        if service_name not in self.services:
            return self._create_service(service_name)
        return self.services[service_name]

    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data from available services.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecast
            end_time: End time for forecast
            club: Optional club name for caching
            
        Returns:
            WeatherResponse object or None if no data available
        """
        if not self.services:
            self.error("No weather services configured")
            return None
            
        errors: List[Exception] = []
        
        # Select primary service based on location
        if 55 <= lat <= 72 and 4 <= lon <= 32:  # Nordic region
            primary_service = 'met'
            fallback_services = ['openmeteo', 'openweather']
        else:
            primary_service = 'openmeteo'
            fallback_services = ['openweather']
            
        self.debug(
            "Selected weather service",
            primary=primary_service,
            fallbacks=fallback_services,
            coords=(lat, lon)
        )
        
        # Try primary service
        service = self.services.get(primary_service)
        if service:
            try:
                response = service.get_weather(lat, lon, start_time, end_time, club)
                if response:
                    return response
            except WeatherError as e:
                self.warning(f"Primary service {primary_service} failed", exc_info=e)
                errors.append(e)
        
        # Try fallback services
        for service_name in fallback_services:
            service = self.services.get(service_name)
            if service:
                try:
                    response = service.get_weather(lat, lon, start_time, end_time, club)
                    if response:
                        return response
                except WeatherError as e:
                    self.warning(f"Fallback service {service_name} failed", exc_info=e)
                    errors.append(e)
        
        # All services failed
        if errors:
            self.error(
                "All weather services failed",
                error_count=len(errors),
                coords=(lat, lon),
                time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
            )
            for e in errors:
                self.error(f"Service error: {str(e)}", exc_info=e)
                
        return None

    def _get_services_for_location(
        self,
        lat: float,
        lon: float
    ) -> List[WeatherService]:
        """Get list of weather services that cover a location."""
        try:
            services = []
            for service in self.services.values():
                if service is None:
                    continue
                try:
                    if service.covers_location(lat, lon):
                        services.append(service)
                except Exception as e:
                    self.warning(
                        "Failed to check service coverage",
                        exc_info=e,
                        service=service.__class__.__name__
                    )
                    continue
            
            if services:
                self.debug(
                    "Found weather services for location",
                    latitude=lat,
                    longitude=lon,
                    services=[s.__class__.__name__ for s in services]
                )
            else:
                self.warning(
                    "No weather services found for location",
                    latitude=lat,
                    longitude=lon
                )
                
            return services
            
        except Exception as e:
            self.error("Failed to get services for location", exc_info=e)
            return []

    def clear_cache(self) -> None:
        """Clear all cached weather responses."""
        self.response_cache.clear()
    
    def list_cache(self) -> List[Dict[str, Any]]:
        """List all cached weather responses.
        
        Returns:
            List of cached responses with metadata
        """
        return self.response_cache.list_entries()
    
    def cleanup_cache(self) -> int:
        """Clean up expired cache entries.
        
        Returns:
            Number of entries removed
        """
        return self.response_cache.cleanup_expired() 