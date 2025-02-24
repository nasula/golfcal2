"""Mock weather service implementation for testing."""

import math
from datetime import UTC, datetime, timedelta

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherResponse


class MockWeatherService(WeatherService):
    """Mock implementation of WeatherService for testing."""
    
    # Wind direction mapping (0-360 degrees to compass points)
    WIND_DIRECTIONS = {
        0: "N", 45: "NE", 90: "E", 135: "SE",
        180: "S", 225: "SW", 270: "W", 315: "NW"
    }
    
    def __init__(self, local_tz=UTC, utc_tz=UTC):
        super().__init__(local_tz, utc_tz)
        self.cache = {}  # Simple dict cache for testing
        
    def _get_cache_key(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> str:
        """Get cache key for weather data."""
        # Convert times to UTC for consistent caching
        start_utc = start_time.astimezone(UTC)
        end_utc = end_time.astimezone(UTC)
        return f"{lat:.4f}_{lon:.4f}_{start_utc.isoformat()}_{end_utc.isoformat()}"
        
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> WeatherResponse:
        """Get weather data with caching."""
        # Validate inputs
        if not isinstance(start_time, datetime) or not start_time.tzinfo:
            raise ValueError("start_time must be timezone-aware")
        if not isinstance(end_time, datetime) or not end_time.tzinfo:
            raise ValueError("end_time must be timezone-aware")
            
        if end_time <= start_time:
            raise ValueError("End time must be after start time")
            
        # Check cache
        cache_key = self._get_cache_key(lat, lon, start_time, end_time)
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if cached.expires > datetime.now(UTC):
                return cached
        
        # Get new data
        data = self._fetch_forecasts(lat, lon, start_time, end_time)
        response = WeatherResponse(data=data, expires=datetime.now(UTC) + timedelta(hours=1))
        
        # Cache the response
        self.cache[cache_key] = response
        return response

    def get_block_size(self, hours_ahead: float) -> int:
        """Get block size based on forecast range."""
        if hours_ahead <= 24:
            return 1  # Hourly for first day
        elif hours_ahead <= 72:
            return 3  # 3-hour blocks for 2-3 days
        else:
            return 6  # 6-hour blocks for longer range
        
    def _get_seasonal_temp(self, date: datetime, base_temp: float) -> float:
        """Calculate temperature adjusted for season."""
        # Day of year from 0 to 365
        day_of_year = date.timetuple().tm_yday
        # Convert to radians (0 to 2π)
        angle = (day_of_year - 172) * (2 * 3.14159 / 365)  # Peak at day 172 (summer solstice)
        # Seasonal variation (±5°C)
        variation = 5 * math.cos(angle)
        return base_temp + variation
        
    def _get_wind_direction(self, hour: int) -> str:
        """Get wind direction based on hour."""
        # Wind tends to rotate clockwise during the day
        degrees = (hour * 15) % 360  # Complete rotation over 24 hours
        # Find closest compass point
        closest = min(self.WIND_DIRECTIONS.keys(), key=lambda x: abs(x - degrees))
        return self.WIND_DIRECTIONS[closest]
        
    def _get_precipitation_data(self, hour: int, date: datetime) -> tuple[float, float, float]:
        """Calculate precipitation probability, amount, and thunder probability."""
        # Base values vary by season
        day_of_year = date.timetuple().tm_yday
        is_summer = 172 - 90 <= day_of_year <= 172 + 90
        
        # Precipitation more likely in afternoon
        base_prob = 20 + (hour - 12) ** 2 / 4  # Peak in afternoon
        if is_summer:
            base_prob += 20  # More precipitation in summer
            
        # Thunder more likely in summer afternoons
        thunder_prob = None
        if is_summer and 12 <= hour <= 18 and base_prob > 70:
            thunder_prob = base_prob - 30
            
        # Precipitation amount based on probability
        precip_amount = 0
        if base_prob > 80:
            precip_amount = (base_prob - 80) / 20  # 0-1mm per hour
            
        return base_prob, precip_amount, thunder_prob

    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> list[WeatherData]:
        """Mock implementation of forecast fetching."""
        if lat > 90 or lat < -90:
            raise ValueError("Invalid latitude")
            
        # Convert input times to service timezone (UTC)
        start_utc = start_time.astimezone(UTC)
        end_utc = end_time.astimezone(UTC)
        
        # Calculate block size based on forecast range
        hours_ahead = (end_utc - start_utc).total_seconds() / 3600
        block_size = self.get_block_size(hours_ahead)
        
        # Generate data at appropriate intervals
        data = []
        current = start_utc
        
        # Base temperature varies by latitude
        # - Equator: ~30°C
        # - Mid latitudes: ~20°C
        # - Poles: ~0°C
        base_temp = 30.0 - (abs(lat) * 30.0 / 90.0)  # Linear decrease from equator to poles
        temp_range = 6.0  # Temperature variation range (±3°C)
        base_wind = 5.5
        
        while current < end_utc:
            hour = current.hour
            # Temperature varies by hour and season
            base_temp_seasonal = self._get_seasonal_temp(current, base_temp)
            hour_rad = (hour - 12) * (2 * 3.14159 / 24)
            temp_variation = -temp_range * (hour_rad ** 2) / 36  # Parabolic curve peaking at noon
            
            # Wind varies throughout the day
            wind_variation = hour / 10  # Smaller wind variation
            wind_speed = base_wind + wind_variation
            wind_direction = self._get_wind_direction(hour)
            
            # Get precipitation data
            precip_prob, precip_amount, thunder_prob = self._get_precipitation_data(hour, current)

            # Determine weather symbol
            is_daytime = 6 <= hour < 18
            if thunder_prob is not None and thunder_prob > 0:
                weather_code = f"{'lightrainandthunder' if precip_amount < 0.5 else 'rainandthunder'}"
                if is_daytime:
                    weather_code += "_day"
                else:
                    weather_code += "_night"
            elif precip_amount > 0:
                weather_code = f"{'lightrain' if precip_amount < 0.5 else 'rain'}"
            else:
                weather_code = "clearsky_day" if is_daytime else "clearsky_night"
            
            data.append(WeatherData(
                temperature=base_temp_seasonal + temp_variation,
                precipitation=precip_amount,
                precipitation_probability=precip_prob,
                wind_speed=wind_speed,
                wind_direction=wind_direction,
                weather_code=weather_code,
                elaboration_time=current,
                thunder_probability=thunder_prob,
                block_duration=timedelta(hours=block_size)
            ))
            current += timedelta(hours=block_size)
            
        return data 