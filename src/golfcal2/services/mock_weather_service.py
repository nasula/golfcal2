"""Mock weather service for testing."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, cast
from zoneinfo import ZoneInfo

from ..services.base_service import WeatherService
from ..services.weather_types import WeatherData, WeatherResponse, WeatherCache

class MockWeatherService(WeatherService):
    """Mock weather service for testing."""
    
    def __init__(self, timezone: ZoneInfo, utc: ZoneInfo, config: Dict[str, Any]):
        """Initialize mock weather service."""
        super().__init__(timezone, utc)  # Don't pass config to base class
        self.service_type = "mock"
        self._cache: Dict[str, WeatherCache] = {}  # Raw response data cache
        
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data for a location."""
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
        response = self._fetch_forecasts(lat, lon, start_time, end_time)
        if response:
            return self._parse_response(response, start_time, end_time)
        
        self.warning("No weather data found")
        return None
        
    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Generate mock forecast data."""
        try:
            current = start_time
            forecasts = []
            
            while current < end_time:
                # Determine weather code based on time of day
                hour = current.hour
                if hour >= 6 and hour <= 18:  # Daytime
                    weather_code = 1  # Clear
                else:
                    weather_code = 3  # Cloudy
                
                # Add some precipitation in the afternoon
                if hour >= 14 and hour <= 16:
                    weather_code = 61  # Light rain
                
                block_size = self.get_block_size((current - start_time).total_seconds() / 3600)
                block_duration = timedelta(hours=block_size)
                
                forecast = {
                    "time": current.isoformat(),
                    "duration": block_duration.total_seconds() / 3600,  # Convert to hours
                    "temperature": 20.0,
                    "wind_speed": 10.0,
                    "wind_direction": 180.0,
                    "precipitation": 0.0,
                    "weather_code": weather_code
                }
                forecasts.append(forecast)
                current += block_duration
            
            return {"forecasts": forecasts}
            
        except Exception as e:
            self.error("Failed to generate mock forecasts", exc_info=e)
            return None
            
    def _parse_response(
        self,
        response_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        interval: int = 1
    ) -> Optional[WeatherResponse]:
        """Parse raw API response into WeatherData objects."""
        try:
            if not response_data or "forecasts" not in response_data:
                return None
                
            weather_data = []
            for forecast in response_data["forecasts"]:
                data = WeatherData(
                    time=datetime.fromisoformat(forecast["time"]),
                    duration=forecast["duration"],
                    temperature=forecast["temperature"],
                    wind_speed=forecast["wind_speed"],
                    wind_direction=forecast["wind_direction"],
                    precipitation=forecast["precipitation"],
                    weather_code=forecast["weather_code"]
                )
                weather_data.append(data)
                
            return WeatherResponse(
                data=weather_data,
                elaboration_time=start_time,
                interval=interval
            )
            
        except Exception as e:
            self.error("Failed to parse mock response", exc_info=e)
            return None 