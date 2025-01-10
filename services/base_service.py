"""Base class for weather services."""

from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo
from golfcal2.utils.logging_utils import EnhancedLoggerMixin, log_execution
from golfcal2.services.weather_types import WeatherData, WeatherResponse

class WeatherService(EnhancedLoggerMixin):
    """Base class for weather services."""
    
    def __init__(self, local_tz, utc_tz):
        """Initialize service."""
        super().__init__()
        # Ensure we have proper ZoneInfo objects
        if isinstance(local_tz, str):
            local_tz = ZoneInfo(local_tz)
        if isinstance(utc_tz, str):
            utc_tz = ZoneInfo(utc_tz)
        self.local_tz = local_tz
        self.utc_tz = utc_tz
    
    def get_expiry_time(self) -> datetime:
        """Get expiry time for current weather data.
        
        Each service should implement this based on their update schedule.
        Default implementation is 1 hour from now.
        """
        return datetime.now(self.utc_tz) + timedelta(hours=1)
    
    @log_execution(level='DEBUG')
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> WeatherResponse:
        """Get weather data for location and time range.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time
            end_time: End time
            
        Returns:
            WeatherResponse with data and expiry time
        """
        data = self._fetch_forecasts(lat, lon, start_time, end_time)
        return WeatherResponse(data=data, expires=self.get_expiry_time())

    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch forecasts from weather service."""
        raise NotImplementedError("Subclasses must implement _fetch_forecasts")

    def get_block_size(self, hours_ahead: float) -> int:
        """Get the block size in hours for grouping forecasts based on how far ahead they are.
        
        Args:
            hours_ahead: Number of hours ahead of current time the forecast is for.
            
        Returns:
            int: Block size in hours (e.g., 1 for hourly forecasts, 6 for 6-hour blocks).
        """
        raise NotImplementedError("Subclasses must implement get_block_size") 