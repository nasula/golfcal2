"""
Unified weather service with improved caching and error handling.
"""

import os
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from typing import Any
from typing import Protocol
from typing import cast
from typing import runtime_checkable
from zoneinfo import ZoneInfo

from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.services.weather_cache import WeatherLocationCache
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_types import WeatherResponse
from golfcal2.utils.logging_utils import LoggerMixin


class WeatherContext:
    """Context for weather data retrieval."""
    
    def __init__(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        local_tz: ZoneInfo,
        utc_tz: ZoneInfo,
        config: dict[str, Any]
    ):
        self.lat = lat
        self.lon = lon
        self.start_time = start_time
        self.end_time = end_time
        self.local_tz = local_tz
        self.utc_tz = utc_tz
        self.config = config

@runtime_checkable
class WeatherStrategyProtocol(Protocol):
    """Protocol for weather strategies."""
    service_type: str
    
    def __init__(self, context: WeatherContext) -> None: ...
    def get_weather(self) -> WeatherResponse | None: ...
    def get_expiry_time(self) -> datetime: ...
    def get_block_size(self, hours_ahead: float) -> int: ...

class WeatherStrategy(ABC, LoggerMixin):
    """Base strategy for weather services."""
    
    service_type: str = "base"  # Should be overridden by subclasses
    
    def __init__(self, context: WeatherContext):
        """Initialize strategy."""
        LoggerMixin.__init__(self)  # Initialize LoggerMixin explicitly
        self.context = context
        self.set_log_context(service=self.__class__.__name__.lower())
    
    @abstractmethod
    def get_weather(self) -> WeatherResponse | None:
        """Get weather data for the given context."""
        pass
    
    @abstractmethod
    def get_expiry_time(self) -> datetime:
        """Get expiry time for cached weather data."""
        pass

    @abstractmethod
    def get_block_size(self, hours_ahead: float) -> int:
        """Get block size for forecast range.
        
        Each weather service must implement its own block size pattern
        based on how it provides forecast data.
        
        Args:
            hours_ahead: Number of hours ahead in the forecast
            
        Returns:
            Block size in hours for the given forecast range
        """
        pass

class WeatherService:
    """Unified weather service."""
    
    def __init__(self, config: dict[str, Any]):
        """Initialize service."""
        self.config = config
        self.local_tz = ZoneInfo(config.get('timezone', 'UTC'))
        self.utc_tz = ZoneInfo('UTC')
        
        # Initialize caches
        cache_dir = config.get('directories', {}).get('cache', os.path.expanduser('~/.cache/golfcal2'))
        os.makedirs(cache_dir, exist_ok=True)
        
        self.location_cache = WeatherLocationCache(config)  # type: ignore[no-untyped-call]
        self.response_cache = WeatherResponseCache(os.path.join(cache_dir, 'weather_responses.db'))
        
        # Initialize strategies
        self._strategies: dict[str, type[WeatherStrategyProtocol]] = {}
        
        # Register default strategies
        from golfcal2.services.met_weather_strategy import MetWeatherStrategy
        from golfcal2.services.mock_weather_strategy import MockWeatherStrategy
        from golfcal2.services.open_meteo_strategy import OpenMeteoStrategy
        
        self.register_strategy('met', cast(type[WeatherStrategyProtocol], MetWeatherStrategy))
        self.register_strategy('openmeteo', cast(type[WeatherStrategyProtocol], OpenMeteoStrategy))
        if config.get('dev_mode', False):
            self.register_strategy('mock', cast(type[WeatherStrategyProtocol], MockWeatherStrategy))
    
    def register_strategy(self, service_type: str, strategy_class: type[WeatherStrategyProtocol]) -> None:
        """Register a new weather strategy."""
        self._strategies[service_type] = strategy_class
    
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        service_type: str | None = None
    ) -> WeatherResponse | None:
        """Get weather data using appropriate strategy."""
        try:
            # Create context
            context = WeatherContext(
                lat=lat,
                lon=lon,
                start_time=start_time,
                end_time=end_time,
                local_tz=self.local_tz,
                utc_tz=self.utc_tz,
                config=self.config
            )
            
            # Try cache first
            cached_response = self.response_cache.get_response(
                service_type or self._select_service_for_location(lat, lon),
                lat,
                lon,
                start_time,
                end_time
            )
            if cached_response:
                return WeatherResponse.from_dict(cached_response)
            
            # Select strategy
            if not service_type:
                service_type = self._select_service_for_location(lat, lon)
            
            strategy_class = self._strategies.get(service_type)
            if not strategy_class:
                raise ValueError(f"No strategy registered for service type: {service_type}")
            
            # Get weather data
            strategy = strategy_class(context)
            response = strategy.get_weather()
            
            # If OpenMeteo fails, try Met as fallback
            if not response and service_type == 'openmeteo':
                met_strategy = self._strategies['met'](context)
                response = met_strategy.get_weather()
                if response:
                    service_type = 'met'  # Update service type for caching
            
            # Cache response if successful
            if response:
                self.response_cache.store_response(
                    service_type=service_type,
                    latitude=lat,
                    longitude=lon,
                    forecast_start=start_time,
                    forecast_end=end_time,
                    response_data=response.to_dict(),
                    expires=strategy.get_expiry_time()
                )
            
            return response
            
        except Exception as e:
            aggregate_error(str(e), "weather_service", str(e.__traceback__))
            return None
    
    def _select_service_for_location(self, lat: float, lon: float) -> str:
        """Select appropriate weather service based on coordinates."""
        # Nordic countries (roughly)
        if 55 <= lat <= 71 and 4 <= lon <= 32:
            # Finland, Sweden, Norway, Denmark
            return 'met'
            
        # Baltic countries (roughly)
        if 53 <= lat <= 59 and 21 <= lon <= 28:
            # Estonia, Latvia, Lithuania
            return 'met'
            
        # Default to OpenMeteo for all other locations
        return 'openmeteo'
    
    def clear_cache(self) -> None:
        """Clear all cached weather responses."""
        self.response_cache.clear()
    
    def list_cache(self) -> list[dict[str, Any]]:
        """List all cached weather responses."""
        return self.response_cache.list_all()