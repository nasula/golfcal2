from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from golfcal2.utils.logging_utils import EnhancedLoggerMixin
from golfcal2.services.base_service import WeatherService
from golfcal2.services.met_weather_service import MetWeatherService
from golfcal2.services.open_meteo_service import OpenMeteoService
from golfcal2.services.weather_types import (
    WeatherResponse, WeatherError, WeatherServiceUnavailable,
    WeatherServiceTimeout, WeatherServiceRateLimited
)

class WeatherManager(EnhancedLoggerMixin):
    """Manager class for weather services."""

    def __init__(
        self,
        local_tz: Union[str, ZoneInfo],
        utc_tz: Union[str, ZoneInfo],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize weather manager.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Optional configuration dictionary
        """
        super().__init__()
        self.config = config or {}
        self.local_tz = local_tz if isinstance(local_tz, ZoneInfo) else ZoneInfo(local_tz)
        self.utc_tz = utc_tz if isinstance(utc_tz, ZoneInfo) else ZoneInfo(utc_tz)
        
        # Initialize services
        self.services: List[WeatherService] = []
        self._init_services()
        
    def _init_services(self) -> None:
        """Initialize weather services based on configuration."""
        # Initialize Met service if configured
        if "met" in self.config:
            try:
                met_service = MetWeatherService(self.local_tz, self.utc_tz)
                self.services.append(met_service)
            except Exception as e:
                self.error("Failed to initialize Met service", exc_info=e)
        
        # Initialize OpenMeteo service if configured
        if "openmeteo" in self.config:
            try:
                openmeteo_service = OpenMeteoService(self.local_tz, self.utc_tz)
                self.services.append(openmeteo_service)
            except Exception as e:
                self.error("Failed to initialize OpenMeteo service", exc_info=e)
                
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
        for service in self.services:
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
            for service in self.services:
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