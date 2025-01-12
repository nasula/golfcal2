"""Weather service manager implementation."""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

from golfcal2.exceptions import (
    WeatherError,
    WeatherServiceUnavailable,
    WeatherDataError,
    ErrorCode,
    handle_errors,
    aggregate_error
)
from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherResponse
from golfcal2.services.open_weather_service import OpenWeatherService
from golfcal2.services.met_weather_service import MetWeatherService
from golfcal2.services.iberian_weather_service import IberianWeatherService

class WeatherServiceManager(WeatherService):
    """Manager for handling multiple weather services."""
    
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
            # Global OpenWeather service (fallback)
            OpenWeatherService(local_tz, utc_tz, config, region="global"),
            # Mediterranean OpenWeather service (specialized configuration)
            OpenWeatherService(local_tz, utc_tz, config, region="mediterranean"),
            # Regional specialized services
            MetWeatherService(local_tz, utc_tz, config),
            IberianWeatherService(local_tz, utc_tz, config)
        ]
        
        self.set_log_context(service="WeatherManager")
    
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> WeatherResponse:
        """Get weather data from all available services.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecasts
            end_time: End time for forecasts
            
        Returns:
            WeatherResponse object with combined data
        """
        all_data = []
        latest_expiry = None
        
        for service in self.services:
            try:
                response = service.get_weather(lat, lon, start_time, end_time)
                if response and response.data:
                    all_data.extend(response.data)
                    
                    if latest_expiry is None or (
                        response.expires is not None and response.expires > latest_expiry
                    ):
                        latest_expiry = response.expires
                    
            except WeatherError as e:
                aggregate_error(str(e), "weather_manager", e.__traceback__)
                continue
        
        # Sort data by time
        all_data.sort(key=lambda x: x.elaboration_time)
        
        # Use default expiry if none found
        if latest_expiry is None:
            latest_expiry = datetime.now(self.utc_tz) + timedelta(hours=1)
        
        return WeatherResponse(data=all_data, expires=latest_expiry) 