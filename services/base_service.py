"""Base class for weather services."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
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
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data for a location."""
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
        """Get weather data from service."""
        try:
            # Calculate time range for fetching data
            now = datetime.now(self.utc_tz)
            hours_ahead = (end_time - now).total_seconds() / 3600
            interval = self.get_block_size(hours_ahead)
            
            # Align start and end times to block boundaries
            base_time = start_time.replace(minute=0, second=0, microsecond=0)
            fetch_end_time = end_time.replace(minute=0, second=0, microsecond=0)
            if end_time.minute > 0 or end_time.second > 0:
                fetch_end_time += timedelta(hours=1)
            
            self.debug(
                "Using forecast interval",
                hours_ahead=hours_ahead,
                interval=interval,
                aligned_start=base_time.isoformat(),
                aligned_end=fetch_end_time.isoformat()
            )
            
            # Check cache for response
            cached_response = self.cache.get_response(
                service_type=self.service_type,
                latitude=lat,
                longitude=lon,
                start_time=base_time,
                end_time=fetch_end_time
            )
            
            if cached_response:
                self.info(
                    "Using cached response",
                    location=cached_response['location'],
                    time_range=f"{base_time.isoformat()} to {fetch_end_time.isoformat()}",
                    interval=interval
                )
                return self._parse_response(cached_response['response'], base_time, fetch_end_time, interval)
            
            # If not in cache, fetch from API
            self.info(
                "Fetching new data from API",
                coords=(lat, lon),
                time_range=f"{base_time.isoformat()} to {fetch_end_time.isoformat()}",
                interval=interval
            )
            
            # Fetch data for the full forecast range
            response_data = self._fetch_forecasts(lat, lon, base_time, fetch_end_time)
            if not response_data:
                self.warning("No forecasts found for requested time range")
                return None
            
            # Store the full response in cache
            self.cache.store_response(
                service_type=self.service_type,
                latitude=lat,
                longitude=lon,
                response_data=response_data,
                forecast_start=base_time,
                forecast_end=fetch_end_time,
                expires=datetime.now(self.utc_tz) + timedelta(hours=1)
            )
            
            # Parse and return just the requested time range
            return self._parse_response(response_data, base_time, fetch_end_time, interval)
            
        except Exception as e:
            self.error("Failed to get weather data", exc_info=e)
            return None

    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from service."""
        try:
            raise NotImplementedError("_fetch_forecasts must be implemented by subclass")
        except Exception as e:
            self.error("Failed to fetch forecasts", exc_info=e)
            return None

    def _parse_response(
        self,
        response_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        interval: int
    ) -> Optional[WeatherResponse]:
        """Parse raw API response into WeatherData objects."""
        try:
            raise NotImplementedError("_parse_response must be implemented by subclass")
        except Exception as e:
            self.error("Failed to parse response", exc_info=e)
            return None

    def covers_location(self, lat: float, lon: float) -> bool:
        """Check if service covers a location."""
        try:
            # Default implementation - override in subclass if needed
            return True
        except Exception as e:
            self.error("Failed to check location coverage", exc_info=e)
            return False

    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size in hours based on how far ahead we're looking."""
        try:
            if hours_ahead <= self.HOURLY_RANGE:
                return 1  # Hourly forecasts for first 48 hours
            elif hours_ahead <= self.SIX_HOURLY_RANGE:
                return 6  # 6-hourly forecasts for next 2 days
            else:
                return 24  # Daily forecasts beyond that
        except Exception as e:
            self.error("Failed to get block size", exc_info=e)
            return 1  # Default to hourly blocks 