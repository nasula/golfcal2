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

class WeatherManager:
    """Manager for weather services."""

    def __init__(self, timezone: ZoneInfo, utc: ZoneInfo, config: Dict[str, Any]):
        """Initialize weather manager.
        
        Args:
            timezone: Local timezone
            utc: UTC timezone
            config: Service configuration
        """
        self.timezone = timezone
        self.utc = utc
        self.config = config
        
        # Initialize shared caches
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
        self.location_cache = WeatherLocationCache(os.path.join(data_dir, 'weather_locations.db'))
        
        # Initialize core services
        self.services = {
            'met': MetWeatherService(timezone, utc, config),
            'open_meteo': OpenMeteoService(timezone, utc, config),
        }
        
        # Add OpenWeather if API key exists
        if config.get('api_keys', {}).get('weather', {}).get('openweather'):
            self.services['openweather'] = OpenWeatherService(timezone, utc, config)
        
        # Set default service
        self.default_service = self.services.get('met')  # MET.no as default (no API key needed)
        
        # Attach caches to services after initialization
        for service in self.services.values():
            service.cache = self.cache
            service.location_cache = self.location_cache

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
            responsible_service = next((s for s in self.services.values() if isinstance(s, MetWeatherService)), None)
        # Use OpenMeteo for all other regions (including Iberia)
        else:
            responsible_service = next((s for s in self.services.values() if isinstance(s, OpenMeteoService)), None)

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
                fallback = next((s for s in self.services.values() if isinstance(s, OpenWeatherService)), None)
                if fallback:
                    try:
                        response = fallback.get_weather(lat, lon, start_time, end_time, club)
                        if response:
                            return response
                    except WeatherError as e2:
                        aggregate_error(str(e2), "weather_manager", e2.__traceback__)
        
        return None