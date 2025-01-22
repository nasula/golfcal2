"""Base class for weather services."""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from zoneinfo import ZoneInfo
from golfcal2.utils.logging_utils import EnhancedLoggerMixin, log_execution
from golfcal2.services.weather_types import WeatherData, WeatherResponse
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.exceptions import WeatherError, ErrorCode

class WeatherService(EnhancedLoggerMixin):
    """Base class for weather services."""
    
    service_type: str = "base"  # Should be overridden by subclasses
    HOURLY_RANGE: int = 48  # Default hourly forecast range in hours
    SIX_HOURLY_RANGE: int = 240  # Default 6-hourly forecast range in hours
    
    def __init__(self, local_tz: Union[str, ZoneInfo], utc_tz: Union[str, ZoneInfo]) -> None:
        """Initialize service.
        
        Args:
            local_tz: Local timezone as string or ZoneInfo
            utc_tz: UTC timezone as string or ZoneInfo
        """
        super().__init__()
        # Ensure we have proper ZoneInfo objects
        if isinstance(local_tz, str):
            local_tz = ZoneInfo(local_tz)
        if isinstance(utc_tz, str):
            utc_tz = ZoneInfo(utc_tz)
        self.local_tz: ZoneInfo = local_tz
        self.utc_tz: ZoneInfo = utc_tz
        
        # Initialize caches as None - they will be set by the manager
        self.cache: Optional[WeatherResponseCache] = None
        self.location_cache: Optional[WeatherLocationCache] = None
    
    def _handle_errors(self, error_code: ErrorCode, message: str) -> None:
        """Handle errors by logging and raising appropriate exceptions.
        
        Args:
            error_code: The error code from ErrorCode enum
            message: Error message to log
            
        Raises:
            WeatherError: With the given error code and message
        """
        self.error(f"Weather service error: {message}", error_code=error_code)
        raise WeatherError(error_code, message)
    
    def get_expiry_time(self) -> datetime:
        """Get expiry time for current weather data.
        
        Each service should implement this based on their update schedule.
        Default implementation is 1 hour from now.
        
        Returns:
            datetime: Expiry time in UTC
        """
        return datetime.now(self.utc_tz) + timedelta(hours=1)
    
    @log_execution(level='DEBUG')
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data for a location.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecast
            end_time: End time for forecast
            club: Optional club identifier for caching
            
        Returns:
            Optional[WeatherResponse]: Weather data if available
        """
        try:
            # Validate input
            if not (-90 <= lat <= 90):
                raise ValueError(f"Invalid latitude: {lat}")
            if not (-180 <= lon <= 180):
                raise ValueError(f"Invalid longitude: {lon}")
            
            # Convert times to UTC
            start_time = start_time.astimezone(self.utc_tz)
            end_time = end_time.astimezone(self.utc_tz)
            
            # Validate time range
            if start_time > end_time:
                raise ValueError("Start time must be before end time")
            
            # Check if location is covered
            if not self.covers_location(lat, lon):
                self.warning(
                    "Location not covered by service",
                    latitude=lat,
                    longitude=lon
                )
                return None
            
            # Get weather data
            try:
                response = self._get_weather(lat, lon, start_time, end_time, club)
                if response and response.data:
                    self.info(
                        "Got weather data",
                        coords=(lat, lon),
                        time_range=f"{start_time.isoformat()} to {end_time.isoformat()}",
                        forecast_count=len(response.data)
                    )
                    return response
                
                self.warning("No weather data found")
                return None
                
            except Exception as e:
                self.error("Failed to get weather data", exc_info=e)
                return None
                
        except Exception as e:
            self.error("Error in get_weather", exc_info=e)
            return None

    def _get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Internal method to get weather data.
        
        This should be implemented by subclasses.
        """
        raise NotImplementedError

    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from the weather service.
        
        This should be implemented by subclasses.
        """
        raise NotImplementedError

    def _parse_response(
        self,
        response_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        interval: int
    ) -> Optional[List[WeatherData]]:
        """Parse response data into weather data objects.
        
        This should be implemented by subclasses.
        
        Args:
            response_data: Raw response data from weather service
            start_time: Start time for forecast
            end_time: End time for forecast
            interval: Time interval in hours
            
        Returns:
            Optional[List[WeatherData]]: List of weather data objects if parsing successful
        """
        raise NotImplementedError

    def covers_location(self, lat: float, lon: float) -> bool:
        """Check if service covers given location.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            bool: True if location is covered
        """
        return True  # Default implementation covers all locations

    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size in hours based on how far ahead we're looking.
        
        Args:
            hours_ahead: Hours ahead from current time
            
        Returns:
            int: Block size in hours (1 or 6)
        """
        if hours_ahead <= self.HOURLY_RANGE:
            return 1
        elif hours_ahead <= self.SIX_HOURLY_RANGE:
            return 6
        else:
            return 6  # Default to 6-hour blocks for long-range forecasts 