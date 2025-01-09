"""Weather service implementation."""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

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
from golfcal2.services.iberian_weather_service import IberianWeatherService
from golfcal2.services.portuguese_weather_service import PortugueseWeatherService

class WeatherManager(WeatherService):
    """Weather service manager."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        """Initialize weather service manager.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Application configuration
        """
        # Initialize parent class with timezones
        super().__init__(local_tz, utc_tz)
        
        # Store config
        self.config = config
        
        # Initialize weather services
        self.services = [
            # Regional specialized services
            MetWeatherService(local_tz, utc_tz, config),
            IberianWeatherService(local_tz, utc_tz, config),
            PortugueseWeatherService(local_tz, utc_tz, config),
            # Global OpenWeather service (fallback)
            OpenWeatherService(local_tz, utc_tz, config, region="global")
        ]
        
        self.set_log_context(service="WeatherManager")
    
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
        
        # Check if location is in Canary Islands
        is_canary = 27 <= lat <= 29.5 and -18.5 <= lon <= -13
        # Check if location is in Iberian Peninsula
        is_iberian = 35 <= lat <= 44 and -10 <= lon <= 5
        
        # Check MET.no (Nordic region)
        if 55 <= lat <= 72 and 4 <= lon <= 32:  # Nordic region
            responsible_service = next((s for s in self.services if isinstance(s, MetWeatherService)), None)
        # Check Portuguese service (before Iberian)
        elif 36.5 <= lat <= 42.5 and -10 <= lon <= -6:  # Portugal
            responsible_service = next((s for s in self.services if isinstance(s, PortugueseWeatherService)), None)
        # Check Iberian service (Spain + Canary Islands)
        elif is_canary or is_iberian:
            responsible_service = next((s for s in self.services if isinstance(s, IberianWeatherService)), None)
        # OpenWeather for other regions
        else:
            responsible_service = next((s for s in self.services if isinstance(s, OpenWeatherService)), None)
        
        if responsible_service:
            try:
                response = responsible_service.get_weather(lat, lon, start_time, end_time, club)
                if response:
                    if isinstance(response, list):
                        # Service returned a list of WeatherData
                        return WeatherResponse(
                            data=response,
                            expires=datetime.now(self.utc_tz) + timedelta(hours=1)
                        )
                    # Service returned a WeatherResponse
                    return response
            except WeatherError as e:
                aggregate_error(str(e), "weather_manager", e.__traceback__)
        
        return None