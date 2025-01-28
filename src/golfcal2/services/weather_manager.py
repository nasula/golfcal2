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
        for service in self.services.values():
            if service is None:
                continue
            try:
                response = service.get_weather(lat, lon, start_time, end_time, club)
                if response is not None:
                    return response
            except WeatherServiceUnavailable as e:
                self.warning(f"Service {service.service_type} unavailable", exc_info=e)
                errors.append(e)
            except WeatherServiceTimeout as e:
                self.warning(f"Service {service.service_type} timeout", exc_info=e)
                errors.append(e)
            except WeatherServiceRateLimited as e:
                self.warning(f"Service {service.service_type} rate limited", exc_info=e)
                errors.append(e)
            except WeatherError as e:
                self.error(f"Service {service.service_type} error", exc_info=e)
                errors.append(e)
            except Exception as e:
                self.error(f"Unexpected error in service {service.service_type}", exc_info=e)
                errors.append(e)
                
        if errors:
            self.error(
                "All weather services failed",
                error_count=len(errors),
                coords=(lat, lon),
                time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
            )
            
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