"""Tests for the weather service implementation."""

import pytest
import math
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherResponse
from typing import Dict, Optional, Any

class MockWeatherService(WeatherService):
    """Mock implementation of WeatherService for testing."""
    
    # Wind direction mapping (0-360 degrees to compass points)
    WIND_DIRECTIONS = {
        0: "N", 45: "NE", 90: "E", 135: "SE",
        180: "S", 225: "SW", 270: "W", 315: "NW"
    }
    
    def __init__(self, local_tz=timezone.utc, utc_tz=timezone.utc):
        super().__init__(local_tz, utc_tz)
        self.service_type = "mock"
        self._cache = {}  # Simple dict cache for testing
        
    def _get_cache_key(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> str:
        """Get cache key for weather data."""
        # Convert times to UTC for consistent caching
        start_utc = start_time.astimezone(timezone.utc)
        end_utc = end_time.astimezone(timezone.utc)
        return f"{lat:.4f}_{lon:.4f}_{start_utc.isoformat()}_{end_utc.isoformat()}"
        
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data with caching."""
        # Validate coordinates
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid latitude: {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid longitude: {lon}")
            
        # Validate inputs
        if not isinstance(start_time, datetime) or not start_time.tzinfo:
            raise ValueError("start_time must be timezone-aware")
        if not isinstance(end_time, datetime) or not end_time.tzinfo:
            raise ValueError("end_time must be timezone-aware")
            
        if end_time <= start_time:
            raise ValueError("End time must be after start time")
            
        # Check cache
        cache_key = self._get_cache_key(lat, lon, start_time, end_time)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.expires > datetime.now(timezone.utc):
                return cached
        
        # Get new data
        response = self._fetch_forecasts(lat, lon, start_time, end_time)
        
        # Cache the response
        if response:
            self._cache[cache_key] = response
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
        
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime):
        """Mock implementation of forecast fetching."""
        if lat > 90 or lat < -90:
            raise ValueError("Invalid latitude")
            
        # Convert input times to service timezone (UTC)
        start_utc = start_time.astimezone(timezone.utc)
        end_utc = end_time.astimezone(timezone.utc)
        
        # Calculate block size based on forecast range
        hours_ahead = (end_utc - start_utc).total_seconds() / 3600
        block_size = self.get_block_size(hours_ahead)
        block_duration = timedelta(hours=block_size)
        
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
                block_duration=block_duration
            ))
            current += block_duration
            
        return WeatherResponse(
            data=data,
            expires=self.get_expiry_time()
        )
        
    def _parse_response(self, response_data: Dict[str, Any], start_time: datetime, end_time: datetime, interval: int) -> Optional[WeatherResponse]:
        """Parse raw API response into WeatherResponse object."""
        if not response_data:
            return None
            
        if isinstance(response_data, WeatherResponse):
            return response_data
            
        if isinstance(response_data, list):
            data = []
            block_duration = timedelta(hours=interval)
            current = start_time
            
            for item in response_data:
                if isinstance(item, WeatherData):
                    data.append(item)
                else:
                    data.append(WeatherData(
                        temperature=item.get('temperature', 0.0),
                        precipitation=item.get('precipitation', 0.0),
                        precipitation_probability=item.get('precipitation_probability', 0.0),
                        wind_speed=item.get('wind_speed', 0.0),
                        wind_direction=item.get('wind_direction', 0.0),
                        weather_code=item.get('weather_code', 'cloudy'),
                        elaboration_time=current,
                        thunder_probability=item.get('thunder_probability', 0.0),
                        block_duration=block_duration
                    ))
                current += block_duration
                
            return WeatherResponse(
                data=data,
                expires=self.get_expiry_time()
            )
            
        return None

@pytest.fixture
def mock_weather_service():
    """Create a mock weather service instance for testing."""
    return MockWeatherService()

def test_get_weather_success(mock_weather_service):
    """Test successful weather data retrieval."""
    start_time = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)  # January (winter)
    end_time = start_time + timedelta(hours=2)
    
    response = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    assert isinstance(response, WeatherResponse)
    assert len(response.data) == 2  # Two hours of data
    
    # Check first hour's data
    first_hour = response.data[0]
    assert isinstance(first_hour, WeatherData)
    
    # At latitude 60.2°N in winter:
    # Base temp = 30 - (60.2 * 30/90) ≈ 10°C
    # Winter adjustment = -5°C (cos(angle) ≈ -1 in January)
    # So expected base is around 5°C
    base_lat_temp = 30.0 - (abs(60.2) * 30.0 / 90.0)  # ≈ 10°C
    winter_adjustment = -5  # -5°C in winter
    expected_base = base_lat_temp + winter_adjustment
    
    # Temperature should be within ±3°C of expected base
    assert expected_base - 3 <= first_hour.temperature <= expected_base + 3
    
    # Other checks
    assert 0 <= first_hour.precipitation_probability <= 100
    assert first_hour.precipitation >= 0
    assert 5 <= first_hour.wind_speed <= 7  # Base wind ± variation
    assert first_hour.wind_direction in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    assert first_hour.elaboration_time == start_time
    assert first_hour.symbol == "clearsky_day"  # At noon

    # Check second hour's data
    second_hour = response.data[1]
    assert second_hour.elaboration_time == start_time + timedelta(hours=1)
    # Second hour should be slightly colder (afternoon in winter)
    assert second_hour.temperature < first_hour.temperature

def test_get_weather_with_local_timezone(mock_weather_service):
    """Test weather data retrieval with local timezone."""
    helsinki_tz = ZoneInfo("Europe/Helsinki")
    mock_weather_service.local_tz = helsinki_tz
    
    # Create times in Helsinki timezone
    start_time = datetime(2024, 1, 10, 14, tzinfo=helsinki_tz)  # 12:00 UTC
    end_time = start_time + timedelta(hours=2)
    
    response = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    assert len(response.data) == 2
    
    # Verify times are correct
    first_hour = response.data[0]
    assert first_hour.elaboration_time.astimezone(helsinki_tz).hour == 14
    assert first_hour.symbol == "clearsky_day"  # 14:00 local time is daytime

def test_get_weather_24h_cycle(mock_weather_service):
    """Test weather data over a full 24-hour cycle."""
    start_time = datetime(2024, 1, 10, 0, tzinfo=timezone.utc)
    end_time = start_time + timedelta(days=1)
    
    response = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    assert len(response.data) == 24  # 24 hours of data
    
    # Check day/night cycle in symbols
    for hour, data in enumerate(response.data):
        is_daytime = 6 <= hour < 18
        expected_symbol = "clearsky_day" if is_daytime else "clearsky_night"
        assert data.symbol == expected_symbol, f"Hour {hour} should be {'day' if is_daytime else 'night'}"
    
    # Check temperature variation
    temps = [hour.temperature for hour in response.data]
    min_temp = min(temps)
    max_temp = max(temps)
    
    # Temperature should be:
    # - Coldest at midnight (hour 0)
    # - Warmest at noon (hour 12)
    # - Symmetric around noon
    assert temps[0] == min_temp, "Should be coldest at midnight"
    assert temps[12] == max_temp, "Should be warmest at noon"
    assert abs(temps[11] - temps[13]) < 0.1, "Temperature should be symmetric around noon"
    assert temps[6] < temps[12], "Morning should be cooler than noon"
    assert temps[18] < temps[12], "Evening should be cooler than noon"

def test_get_weather_invalid_coordinates(mock_weather_service):
    """Test handling of invalid coordinates."""
    with pytest.raises(ValueError) as exc_info:
        mock_weather_service.get_weather(
            lat=91.0,  # Invalid latitude (>90)
            lon=24.9,
            start_time=datetime(2024, 1, 10, 12, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 10, 14, tzinfo=timezone.utc)
        )
    
    assert "Invalid latitude" in str(exc_info.value)

def test_weather_caching(mock_weather_service, monkeypatch):
    """Test that weather data is properly cached."""
    # Mock _fetch_forecasts to track calls
    call_count = 0
    original_fetch = mock_weather_service._fetch_forecasts
    
    def mock_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_fetch(*args, **kwargs)
    
    monkeypatch.setattr(mock_weather_service, '_fetch_forecasts', mock_fetch)
    
    # Test times
    start_time = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    
    # First call should hit the API
    response1 = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    # Second call with same parameters should use cache
    response2 = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    # Call with different timezone but same UTC time should use cache
    response3 = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time.astimezone(ZoneInfo("Europe/Helsinki")),
        end_time=end_time.astimezone(ZoneInfo("Europe/Helsinki"))
    )
    
    # Verify all responses are identical
    assert response1.data[0].temperature == response2.data[0].temperature == response3.data[0].temperature
    assert response1.data[0].precipitation_probability == response2.data[0].precipitation_probability == response3.data[0].precipitation_probability
    
    # Verify _fetch_forecasts was only called once
    assert call_count == 1 

def test_get_weather_invalid_time_range(mock_weather_service):
    """Test handling of invalid time ranges."""
    # End time before start time
    with pytest.raises(ValueError) as exc_info:
        mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=datetime(2024, 1, 10, 12, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 10, 10, tzinfo=timezone.utc)  # 2 hours before start
        )
    assert "End time must be after start time" in str(exc_info.value)
    
    # Zero duration
    with pytest.raises(ValueError) as exc_info:
        mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=datetime(2024, 1, 10, 12, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 10, 12, tzinfo=timezone.utc)  # Same as start
        )
    assert "End time must be after start time" in str(exc_info.value)  # Both cases use same error message

def test_get_weather_extreme_coordinates(mock_weather_service):
    """Test handling of extreme but valid coordinates."""
    start_time = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    
    # Test poles
    north_pole = mock_weather_service.get_weather(
        lat=90.0,
        lon=0.0,
        start_time=start_time,
        end_time=end_time
    )
    assert len(north_pole.data) == 2
    
    south_pole = mock_weather_service.get_weather(
        lat=-90.0,
        lon=0.0,
        start_time=start_time,
        end_time=end_time
    )
    assert len(south_pole.data) == 2
    
    # Test international date line
    date_line_east = mock_weather_service.get_weather(
        lat=0.0,
        lon=180.0,
        start_time=start_time,
        end_time=end_time
    )
    assert len(date_line_east.data) == 2
    
    date_line_west = mock_weather_service.get_weather(
        lat=0.0,
        lon=-180.0,
        start_time=start_time,
        end_time=end_time
    )
    assert len(date_line_west.data) == 2
    
    # Temperatures should be colder at poles
    equator = mock_weather_service.get_weather(
        lat=0.0,
        lon=0.0,
        start_time=start_time,
        end_time=end_time
    )
    assert north_pole.data[0].temperature < equator.data[0].temperature
    assert south_pole.data[0].temperature < equator.data[0].temperature

def test_get_weather_cross_day_range(mock_weather_service):
    """Test weather data retrieval across day boundaries."""
    # Start at 23:00 and end at 01:00 next day
    start_time = datetime(2024, 1, 10, 23, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    
    response = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    assert len(response.data) == 2
    
    # Check day/night symbols across midnight
    assert response.data[0].symbol == "clearsky_night"  # 23:00
    assert response.data[1].symbol == "clearsky_night"  # 00:00
    
    # Temperature should decrease across midnight
    assert response.data[1].temperature < response.data[0].temperature

def test_get_weather_cache_expiry_behavior(mock_weather_service, monkeypatch):
    """Test detailed cache expiry behavior."""
    start_time = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    
    # Create a class to hold the current time
    class MockTime:
        def __init__(self):
            self.current = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)
        
        def now(self, tz=None):
            return self.current.replace(tzinfo=tz or timezone.utc)
    
    mock_time = MockTime()
    monkeypatch.setattr('datetime.datetime', type('MockDateTime', (), {
        'now': mock_time.now,
        'fromtimestamp': datetime.fromtimestamp,
        'fromisoformat': datetime.fromisoformat,
    }))
    
    # Initial call to populate cache
    response1 = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    initial_expiry = response1.expires
    
    # Verify cache hit with current time
    response2 = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    assert response1.data[0].temperature == response2.data[0].temperature
    
    # Move time forward past expiry
    mock_time.current += timedelta(hours=2)
    
    # Should get new data after expiry
    response3 = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    assert response3.expires > mock_time.current

def test_get_weather_with_naive_datetime(mock_weather_service):
    """Test handling of naive datetime inputs."""
    naive_start = datetime(2024, 1, 10, 12)  # No timezone
    naive_end = naive_start + timedelta(hours=2)
    
    with pytest.raises(ValueError) as exc_info:
        mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=naive_start,
            end_time=naive_end
        )
    assert "timezone" in str(exc_info.value).lower() 

def test_get_weather_wind_patterns(mock_weather_service):
    """Test wind direction and speed patterns."""
    # Test a full day to see wind patterns
    start_time = datetime(2024, 1, 10, 0, tzinfo=timezone.utc)
    end_time = start_time + timedelta(days=1)
    
    response = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    # Wind should vary throughout the day
    winds = [(data.wind_speed, data.wind_direction) for data in response.data]
    
    # Check wind speeds follow expected pattern
    for hour, (speed, direction) in enumerate(winds):
        # Wind should be within reasonable bounds
        assert 0 <= speed <= 30, f"Wind speed at hour {hour} should be between 0 and 30 m/s"
        # Direction should be a valid compass point
        assert direction in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

def test_get_weather_precipitation_patterns(mock_weather_service):
    """Test precipitation probability and amount patterns."""
    # Test a rainy period
    start_time = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=6)
    
    response = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    # Check precipitation data
    for hour, data in enumerate(response.data):
        # Probability should be between 0 and 100
        assert 0 <= data.precipitation_probability <= 100
        # Precipitation amount should be non-negative
        assert data.precipitation >= 0
        # If high probability, should have some precipitation
        if data.precipitation_probability > 80:
            assert data.precipitation > 0
        # If zero probability, should have no precipitation
        if data.precipitation_probability == 0:
            assert data.precipitation == 0

def test_get_weather_block_size(mock_weather_service):
    """Test weather data block size calculations."""
    # Test different forecast ranges
    test_ranges = [
        (timedelta(hours=6), 1),    # Short-term: hourly blocks
        (timedelta(days=3), 3),     # Medium-term: 3-hour blocks
        (timedelta(days=7), 6),     # Long-term: 6-hour blocks
    ]
    
    start_time = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)
    
    for duration, expected_block_size in test_ranges:
        end_time = start_time + duration
        hours_ahead = duration.total_seconds() / 3600
        
        block_size = mock_weather_service.get_block_size(hours_ahead)
        assert block_size == expected_block_size, f"Expected {expected_block_size}h blocks for {hours_ahead}h forecast"
        
        # Verify data is returned in correct block sizes
        response = mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=start_time,
            end_time=end_time
        )
        
        # Check that data points are at correct intervals
        for i in range(1, len(response.data)):
            time_diff = response.data[i].elaboration_time - response.data[i-1].elaboration_time
            assert time_diff == timedelta(hours=block_size)

def test_get_weather_thunder_probability(mock_weather_service):
    """Test thunder probability calculations."""
    # Test during summer afternoon (when thunder is more likely)
    start_time = datetime(2024, 7, 10, 14, tzinfo=timezone.utc)  # 2 PM
    end_time = start_time + timedelta(hours=4)
    
    response = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    for hour, data in enumerate(response.data):
        # Thunder probability should be between 0 and 100
        assert data.thunder_probability is None or 0 <= data.thunder_probability <= 100
        
        # If there's high precipitation probability, thunder might be more likely
        if data.precipitation_probability > 70:
            assert data.thunder_probability is not None
            assert data.thunder_probability > 0
            # Symbol should reflect thunder conditions
            assert "thunder" in data.symbol.lower()

def test_get_weather_seasonal_variations(mock_weather_service):
    """Test weather variations across seasons."""
    # Test same location at different times of year
    test_dates = [
        (datetime(2024, 1, 10, 12, tzinfo=timezone.utc), "winter"),
        (datetime(2024, 4, 10, 12, tzinfo=timezone.utc), "spring"),
        (datetime(2024, 7, 10, 12, tzinfo=timezone.utc), "summer"),
        (datetime(2024, 10, 10, 12, tzinfo=timezone.utc), "fall")
    ]
    
    responses = {}
    for date, season in test_dates:
        response = mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=date,
            end_time=date + timedelta(hours=24)
        )
        responses[season] = response
    
    # Summer should be warmer than winter
    assert (responses["summer"].data[12].temperature > 
            responses["winter"].data[12].temperature)
    
    # Spring and fall should be between summer and winter
    winter_temp = responses["winter"].data[12].temperature
    summer_temp = responses["summer"].data[12].temperature
    spring_temp = responses["spring"].data[12].temperature
    fall_temp = responses["fall"].data[12].temperature
    
    assert winter_temp < spring_temp < summer_temp
    assert winter_temp < fall_temp < summer_temp

def test_get_weather_error_handling(mock_weather_service):
    """Test error handling in weather service."""
    start_time = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    
    # Test with non-datetime objects
    with pytest.raises(ValueError):
        mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time="2024-01-10 12:00",  # String instead of datetime
            end_time=end_time
        )
    
    # Test with invalid timezone
    with pytest.raises(ValueError):
        mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=start_time.replace(tzinfo=None),  # Remove timezone
            end_time=end_time
        )

def test_get_weather_service_configuration(mock_weather_service):
    """Test weather service configuration and initialization."""
    # Test with custom timezones
    helsinki_tz = ZoneInfo("Europe/Helsinki")
    custom_service = MockWeatherService(
        local_tz=helsinki_tz,
        utc_tz=timezone.utc
    )
    
    assert custom_service.local_tz == helsinki_tz
    assert custom_service.utc_tz == timezone.utc
    
    # Test timezone conversion
    local_time = datetime(2024, 1, 10, 14, tzinfo=helsinki_tz)  # 14:00 Helsinki time
    utc_time = local_time.astimezone(timezone.utc)  # Should be 12:00 UTC
    
    response = custom_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=local_time,
        end_time=local_time + timedelta(hours=1)
    )
    
    assert response.data[0].elaboration_time == utc_time

def test_get_weather_cache_operations(mock_weather_service):
    """Test detailed cache operations."""
    start_time = datetime(2024, 1, 10, 12, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)
    
    # Initial call to populate cache
    response1 = mock_weather_service.get_weather(
        lat=60.2,
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    
    # Verify cache key generation
    cache_key = mock_weather_service._get_cache_key(60.2, 24.9, start_time, end_time)
    assert cache_key in mock_weather_service._cache
    
    # Verify cache contents
    cached_response = mock_weather_service._cache[cache_key]
    assert isinstance(cached_response, WeatherResponse)
    assert len(cached_response.data) == len(response1.data)
    assert cached_response.data[0].temperature == response1.data[0].temperature
    
    # Test cache with slightly different coordinates (should not hit cache)
    response2 = mock_weather_service.get_weather(
        lat=60.21,  # Slightly different latitude
        lon=24.9,
        start_time=start_time,
        end_time=end_time
    )
    assert response2.data[0].temperature != response1.data[0].temperature
