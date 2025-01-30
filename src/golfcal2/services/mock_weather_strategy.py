"""
Mock weather service strategy implementation for development mode.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import random

from golfcal2.services.weather_service import WeatherStrategy
from golfcal2.services.weather_types import WeatherResponse, WeatherData

class MockWeatherStrategy(WeatherStrategy):
    """Mock weather strategy for development and testing."""
    
    service_type: str = "mock"
    HOURLY_RANGE: int = 168  # 7 days
    MAX_FORECAST_RANGE: int = 168  # 7 days
    
    def get_weather(self) -> Optional[WeatherResponse]:
        """Get mock weather data."""
        try:
            weather_data: List[WeatherData] = []
            current_time = self.context.start_time
            
            while current_time <= self.context.end_time:
                # Generate random weather data
                temp = random.uniform(15, 25)  # Temperature between 15-25°C
                precip = random.uniform(0, 5)  # Precipitation 0-5mm
                wind = random.uniform(0, 10)  # Wind speed 0-10 m/s
                wind_dir = random.randint(0, 359)  # Wind direction 0-359°
                
                weather_data.append(WeatherData(
                    time=current_time,
                    temperature=temp,
                    precipitation=precip,
                    wind_speed=wind,
                    wind_direction=wind_dir,
                    precipitation_probability=random.randint(0, 100),
                    thunder_probability=random.randint(0, 100),
                    weather_code="MOCK_WEATHER"
                ))
                
                current_time += timedelta(hours=1)
            
            return WeatherResponse(
                data=weather_data,
                expires=self.get_expiry_time()
            )
            
        except Exception as e:
            self.error("Failed to generate mock weather data", exc_info=e)
            return None
    
    def get_expiry_time(self) -> datetime:
        """Get expiry time for mock weather data."""
        # Mock data expires in 1 hour
        return datetime.now(self.context.utc_tz) + timedelta(hours=1) 