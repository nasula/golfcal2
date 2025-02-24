"""Tests for the mock weather service implementation."""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from golfcal2.services.weather_types import WeatherData
from golfcal2.services.weather_types import WeatherResponse
from tests.services.mock_weather_service import MockWeatherService


@pytest.fixture
def mock_weather_service():
    """Create a mock weather service instance for testing."""
    return MockWeatherService()

class TestMockWeatherService:
    """Test cases for MockWeatherService."""

    def test_get_weather_success(self, mock_weather_service):
        """Test successful weather data retrieval."""
        start_time = datetime(2024, 1, 10, 12, tzinfo=UTC)  # January (winter)
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

    def test_get_weather_with_local_timezone(self, mock_weather_service):
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

    def test_get_weather_24h_cycle(self, mock_weather_service):
        """Test weather data over a full 24-hour cycle."""
        start_time = datetime(2024, 1, 10, 0, tzinfo=UTC)
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

    def test_get_weather_invalid_coordinates(self, mock_weather_service):
        """Test handling of invalid coordinates."""
        with pytest.raises(ValueError) as exc_info:
            mock_weather_service.get_weather(
                lat=91.0,  # Invalid latitude (>90)
                lon=24.9,
                start_time=datetime(2024, 1, 10, 12, tzinfo=UTC),
                end_time=datetime(2024, 1, 10, 14, tzinfo=UTC)
            )
        
        assert "Invalid latitude" in str(exc_info.value)

    def test_weather_caching(self, mock_weather_service, monkeypatch):
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
        start_time = datetime(2024, 1, 10, 12, tzinfo=UTC)
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

    def test_get_weather_invalid_time_range(self, mock_weather_service):
        """Test handling of invalid time ranges."""
        # End time before start time
        with pytest.raises(ValueError) as exc_info:
            mock_weather_service.get_weather(
                lat=60.2,
                lon=24.9,
                start_time=datetime(2024, 1, 10, 12, tzinfo=UTC),
                end_time=datetime(2024, 1, 10, 10, tzinfo=UTC)  # 2 hours before start
            )
        assert "End time must be after start time" in str(exc_info.value)
        
        # Zero duration
        with pytest.raises(ValueError) as exc_info:
            mock_weather_service.get_weather(
                lat=60.2,
                lon=24.9,
                start_time=datetime(2024, 1, 10, 12, tzinfo=UTC),
                end_time=datetime(2024, 1, 10, 12, tzinfo=UTC)  # Same as start
            )
        assert "End time must be after start time" in str(exc_info.value)  # Both cases use same error message

    def test_get_weather_extreme_coordinates(self, mock_weather_service):
        """Test handling of extreme but valid coordinates."""
        start_time = datetime(2024, 1, 10, 12, tzinfo=UTC)
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

    def test_get_weather_cross_day_range(self, mock_weather_service):
        """Test weather data retrieval across day boundaries."""
        # Start at 23:00 and end at 01:00 next day
        start_time = datetime(2024, 1, 10, 23, tzinfo=UTC)
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

    def test_get_weather_cache_expiry_behavior(self, mock_weather_service, monkeypatch):
        """Test detailed cache expiry behavior."""
        start_time = datetime(2024, 1, 10, 12, tzinfo=UTC)
        end_time = start_time + timedelta(hours=2)
        
        # Create a class to hold the current time
        class MockTime:
            def __init__(self):
                self.current = datetime(2024, 1, 10, 12, tzinfo=UTC)
            
            def now(self, tz=None):
                return self.current.replace(tzinfo=tz or UTC)
        
        mock_time = MockTime()
        monkeypatch.setattr('datetime.datetime', type('MockDateTime', (), {
            'now': mock_time.now,
            'fromtimestamp': datetime.fromtimestamp,
            'fromisoformat': datetime.fromisoformat,
        }))
        
        # Initial call to populate cache
        mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=start_time,
            end_time=end_time
        )

        # Verify cache hit with current time
        mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=start_time,
            end_time=end_time
        )
        
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

    def test_get_weather_with_naive_datetime(self, mock_weather_service):
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

    def test_get_weather_wind_patterns(self, mock_weather_service):
        """Test wind direction and speed patterns."""
        # Test a full day to see wind patterns
        start_time = datetime(2024, 1, 10, 0, tzinfo=UTC)
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

    def test_get_weather_precipitation_patterns(self, mock_weather_service):
        """Test precipitation probability and amount patterns."""
        # Test a rainy period
        start_time = datetime(2024, 7, 10, 14, tzinfo=UTC)  # 2 PM
        end_time = start_time + timedelta(hours=4)
        
        response = mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=start_time,
            end_time=end_time
        )
        
        # Check precipitation data
        for _hour, data in enumerate(response.data):
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

    def test_get_weather_block_size(self, mock_weather_service):
        """Test weather data block size calculations."""
        # Test different forecast ranges
        test_ranges = [
            (timedelta(hours=6), 1),    # Short-term: hourly blocks
            (timedelta(days=3), 3),     # Medium-term: 3-hour blocks
            (timedelta(days=7), 6),     # Long-term: 6-hour blocks
        ]
        
        start_time = datetime(2024, 1, 10, 12, tzinfo=UTC)
        
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

    def test_get_weather_thunder_probability(self, mock_weather_service):
        """Test thunder probability calculations."""
        # Test during summer afternoon (when thunder is more likely)
        start_time = datetime(2024, 7, 10, 14, tzinfo=UTC)  # 2 PM
        end_time = start_time + timedelta(hours=4)
        
        response = mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=start_time,
            end_time=end_time
        )
        
        for _hour, data in enumerate(response.data):
            # Thunder probability should be between 0 and 100
            assert data.thunder_probability is None or 0 <= data.thunder_probability <= 100
            
            # If there's high precipitation probability, thunder might be more likely
            if data.precipitation_probability > 70:
                assert data.thunder_probability is not None
                assert data.thunder_probability > 0
                # Symbol should reflect thunder conditions
                assert "thunder" in data.symbol.lower()

    def test_get_weather_seasonal_variations(self, mock_weather_service):
        """Test weather variations across seasons."""
        # Test same location at different times of year
        test_dates = [
            (datetime(2024, 1, 10, 12, tzinfo=UTC), "winter"),
            (datetime(2024, 4, 10, 12, tzinfo=UTC), "spring"),
            (datetime(2024, 7, 10, 12, tzinfo=UTC), "summer"),
            (datetime(2024, 10, 10, 12, tzinfo=UTC), "fall")
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

    def test_get_weather_error_handling(self, mock_weather_service):
        """Test error handling in weather service."""
        start_time = datetime(2024, 1, 10, 12, tzinfo=UTC)
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

    def test_get_weather_service_configuration(self, mock_weather_service):
        """Test weather service configuration and initialization."""
        # Test with custom timezones
        helsinki_tz = ZoneInfo("Europe/Helsinki")
        custom_service = MockWeatherService(
            local_tz=helsinki_tz,
            utc_tz=UTC
        )
        
        assert custom_service.local_tz == helsinki_tz
        assert custom_service.utc_tz == UTC
        
        # Test timezone conversion
        local_time = datetime(2024, 1, 10, 14, tzinfo=helsinki_tz)  # 14:00 Helsinki time
        utc_time = local_time.astimezone(UTC)  # Should be 12:00 UTC
        
        response = custom_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=local_time,
            end_time=local_time + timedelta(hours=1)
        )
        
        assert response.data[0].elaboration_time == utc_time

    def test_get_weather_cache_operations(self, mock_weather_service):
        """Test detailed cache operations."""
        start_time = datetime(2024, 1, 10, 12, tzinfo=UTC)
        end_time = start_time + timedelta(hours=2)
        
        # Initial call to populate cache
        mock_weather_service.get_weather(
            lat=60.2,
            lon=24.9,
            start_time=start_time,
            end_time=end_time
        )
        
        # Verify cache key generation
        cache_key = mock_weather_service._get_cache_key(60.2, 24.9, start_time, end_time)
        assert cache_key in mock_weather_service.cache
        
        # Verify cache contents
        cached_response = mock_weather_service.cache[cache_key]
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

    def _parse_response(self, response_data: dict[str, Any], start_time: datetime, end_time: datetime, interval: int) -> WeatherResponse | None:
        # Implementation of _parse_response method
        pass 