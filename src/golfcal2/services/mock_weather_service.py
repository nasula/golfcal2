"""Mock weather service for testing."""

import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_types import WeatherCode, WeatherData, WeatherResponse


class MockWeatherService(WeatherService):
    """Mock weather service for testing."""
    
    service_type: str = "mock"
    HOURLY_RANGE: int = 48  # 2 days
    SIX_HOURLY_RANGE: int = 240  # 10 days
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: dict[str, Any]):
        """Initialize service."""
        super().__init__(local_tz, utc_tz, config)
        
        # Initialize database and cache
        data_dir = config.get('directories', {}).get('data', 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
        
        # Initialize mock data
        self._cache: dict[str, dict[str, Any]] = {}
        
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: str | None = None
    ) -> WeatherResponse | None:
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
            return self._parse_response(response)
        
        self.warning("No weather data found")
        return None
        
    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> dict[str, Any] | None:
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
            
    def _parse_response(self, response_data: dict[str, Any]) -> WeatherResponse | None:
        """Parse mock weather response."""
        try:
            start_time = datetime.fromisoformat(response_data['start_time'])
            end_time = datetime.fromisoformat(response_data['end_time'])
            interval = response_data.get('interval', 60)
            
            weather_data: list[WeatherData] = []
            current_time = start_time
            
            while current_time <= end_time:
                weather_data.append(
                    WeatherData(
                        time=current_time,
                        temperature=20.0,
                        precipitation=0.0,
                        precipitation_probability=0.0,
                        wind_speed=5.0,
                        wind_direction=180.0,
                        weather_code=WeatherCode.CLEARSKY_DAY,
                        humidity=50.0,
                        cloud_cover=0.0
                    )
                )
                current_time += timedelta(minutes=interval)
            
            return WeatherResponse(
                data=weather_data,
                elaboration_time=datetime.now(ZoneInfo('UTC'))
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse mock weather response: {e}")
            return None 