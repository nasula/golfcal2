"""Base class for weather services."""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from zoneinfo import ZoneInfo
from golfcal2.utils.logging_utils import EnhancedLoggerMixin, log_execution
from golfcal2.services.weather_types import (
    WeatherData, WeatherResponse, WeatherError, WeatherServiceUnavailable,
    WeatherServiceInvalidResponse, WeatherServiceTimeout, WeatherServiceRateLimited,
    WeatherAuthError, WeatherValidationError, WeatherServiceError, WeatherLocationError
)
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.error_codes import ErrorCode

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
        if error_code == ErrorCode.SERVICE_UNAVAILABLE:
            raise WeatherServiceUnavailable(message, self.service_type)
        elif error_code == ErrorCode.INVALID_RESPONSE:
            raise WeatherServiceInvalidResponse(message, self.service_type)
        elif error_code == ErrorCode.TIMEOUT:
            raise WeatherServiceTimeout(message, self.service_type)
        elif error_code == ErrorCode.RATE_LIMITED:
            raise WeatherServiceRateLimited(message, self.service_type)
        elif error_code == ErrorCode.AUTH_FAILED:
            raise WeatherAuthError(message, self.service_type)
        elif error_code == ErrorCode.VALIDATION_FAILED:
            raise WeatherValidationError(message, self.service_type)
        else:
            raise WeatherServiceError(message, self.service_type)
    
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
        """Get weather data for a location and time range.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecast
            end_time: End time for forecast
            club: Optional club name for caching
            
        Returns:
            WeatherResponse object or None if no data available
        """
        try:
            # Validate inputs
            if not (-90 <= lat <= 90):
                raise WeatherLocationError(f"Invalid latitude: {lat}", self.service_type)
            if not (-180 <= lon <= 180):
                raise WeatherLocationError(f"Invalid longitude: {lon}", self.service_type)
            if start_time > end_time:
                raise WeatherValidationError("Start time must be before end time", self.service_type)
            
            # Try to get from cache first
            if self.cache is not None and club is not None:
                cached_response = self.cache.get_response(
                    self.service_type,
                    lat,
                    lon,
                    start_time,
                    end_time
                )
                if cached_response is not None:
                    return self._parse_response(cached_response)
            
            # Fetch and parse data
            response_data = self._fetch_forecasts(lat, lon, start_time, end_time)
            if response_data is None:
                return None
                
            weather_response = self._parse_response(response_data)
            
            # Cache the response if possible
            if weather_response is not None and self.cache is not None and club is not None:
                expiry_time = self.get_expiry_time()
                self.cache.store_response(
                    self.service_type,
                    lat,
                    lon,
                    start_time,
                    end_time,
                    response_data,
                    expiry_time
                )
            
            return weather_response
            
        except WeatherError:
            raise
        except Exception as e:
            self.error("Error in get_weather", exc_info=e)
            return None
            
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> Optional[Dict[str, Any]]:
        """Fetch forecasts from the weather service.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecast
            end_time: End time for forecast
            
        Returns:
            Dictionary containing the forecast data or None if no data available
            
        Raises:
            WeatherError: If there is an error fetching the forecasts
        """
        raise NotImplementedError("Subclasses must implement _fetch_forecasts")
        
    def _parse_response(self, response_data: Dict[str, Any]) -> Optional[WeatherResponse]:
        """Parse the response data into a WeatherResponse object.
        
        Args:
            response_data: Dictionary containing the forecast data
            
        Returns:
            WeatherResponse object or None if parsing fails
            
        Raises:
            WeatherError: If there is an error parsing the response
        """
        raise NotImplementedError("Subclasses must implement _parse_response")

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