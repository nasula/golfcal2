"""Tests for the Portuguese Weather Service (IPMA API integration)."""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import Mock, patch
import json

from golfcal2.services.portuguese_weather_service import PortugueseWeatherService
from golfcal2.services.weather_types import WeatherData
from golfcal2.exceptions import WeatherError, APIResponseError
from golfcal2.config.types import AppConfig
from golfcal2.config.error_aggregator import init_error_aggregator
from golfcal2.config.logging_config import ErrorAggregationConfig

pytestmark = pytest.mark.skip(reason="Portuguese weather service is currently disabled")

@pytest.fixture
def mock_config():
    return AppConfig(
        clubs={},  # Empty clubs config
        users={},  # Empty users config
        global_config={
            'api_keys': {
                'weather': {
                    'ipma': 'test_key'  # Mock API key for IPMA
                }
            },
            'cache': {
                'weather_location': {'max_size': 100}
            }
        },
        api_keys={}  # Empty API keys config
    )

@pytest.fixture(autouse=True)
def setup_error_aggregator():
    """Set up error aggregator for tests."""
    config = ErrorAggregationConfig(
        enabled=True,
        report_interval=60,
        error_threshold=5,
        time_threshold=300,
        categorize_by=["service", "message", "stack_trace"]
    )
    init_error_aggregator(config)
    yield
    # Clean up after tests
    _error_aggregator = None

@pytest.fixture
def weather_service(mock_config):
    local_tz = ZoneInfo("Europe/Lisbon")
    utc_tz = ZoneInfo("UTC")
    return PortugueseWeatherService(local_tz, utc_tz, mock_config)

def test_haversine_distance(weather_service):
    """Test distance calculation between two points."""
    # Lisbon coordinates
    lat1, lon1 = 38.7223, -9.1393
    # Porto coordinates
    lat2, lon2 = 41.1579, -8.6291
    
    distance = weather_service._haversine_distance(lat1, lon1, lat2, lon2)
    assert 274 <= distance <= 275  # ~274.5 km between Lisbon and Porto

def test_wind_class_to_speed(weather_service):
    """Test wind class to speed conversion."""
    assert weather_service._wind_class_to_speed(1) == 2.8   # Weak (< 15 km/h)
    assert weather_service._wind_class_to_speed(2) == 6.9   # Moderate (15-35 km/h)
    assert weather_service._wind_class_to_speed(3) == 12.5  # Strong (35-55 km/h)
    assert weather_service._wind_class_to_speed(4) == 18.1  # Very strong (> 55 km/h)
    assert weather_service._wind_class_to_speed(5) == 0.0   # Invalid class defaults to 0

def test_get_wind_direction(weather_service):
    """Test wind direction mapping."""
    assert weather_service._get_wind_direction("N") == "N"
    assert weather_service._get_wind_direction("NE") == "NE"
    assert weather_service._get_wind_direction(None) is None
    assert weather_service._get_wind_direction("invalid") is None

def test_map_ipma_code(weather_service):
    """Test weather code mapping."""
    # Test day conditions (hour = 12)
    assert weather_service._map_ipma_code(1, 12) == "clearsky_day"  # Clear sky
    assert weather_service._map_ipma_code(2, 12) == "partlycloudy_day"  # Partly cloudy
    assert weather_service._map_ipma_code(4, 12) == "cloudy"  # Cloudy
    
    # Test night conditions (hour = 0)
    assert weather_service._map_ipma_code(1, 0) == "clearsky_night"
    assert weather_service._map_ipma_code(2, 0) == "partlycloudy_night"

def test_get_block_size(weather_service):
    """Test forecast block size calculation."""
    assert weather_service.get_block_size(5) == 1  # First 24 hours
    assert weather_service.get_block_size(25) == 3  # Beyond 24 hours
    assert weather_service.get_block_size(49) == 3  # Beyond 48 hours

def test_convert_cached_data(weather_service):
    """Test conversion of cached weather data."""
    time_str = '2024-01-10T12:00:00+00:00'
    location = '38.7223,-9.1393'
    cached_data = {
        time_str: {
            'air_temperature': 18.5,
            'precipitation_amount': 0.2,
            'probability_of_precipitation': 20.0,
            'wind_speed': 6.9,
            'wind_from_direction': 'NW',
            'summary_code': 'cloudy',
            'probability_of_thunder': 0.0
        }
    }

    result = weather_service._convert_cached_data(cached_data)
    
    assert isinstance(result, list)
    assert len(result) == 1
    forecast = result[0]
    assert forecast.temperature == 18.5
    assert forecast.precipitation == 0.2
    assert forecast.precipitation_probability == 20.0
    assert forecast.wind_speed == 6.9
    assert forecast.wind_direction == 'NW'
    assert forecast.symbol == 'cloudy'
    assert forecast.thunder_probability == 0.0

def test_invalid_wind_class(weather_service):
    """Test handling of invalid wind class values."""
    assert weather_service._wind_class_to_speed(0) == 0  # Invalid/calm
    assert weather_service._wind_class_to_speed(10) == 0  # Invalid high value
    assert weather_service._wind_class_to_speed(-1) == 0  # Invalid negative value

def test_get_expiry_time(weather_service):
    """Test cache expiry time calculation."""
    expiry = weather_service.get_expiry_time()
    assert isinstance(expiry, datetime)
    # IPMA updates twice daily at 10:00 and 20:00 UTC
    assert expiry > datetime.now(ZoneInfo("UTC"))

@pytest.mark.asyncio
async def test_get_weather_location_cached(weather_service):
    """Test weather fetching with cached location."""
    lat, lon = 38.7223, -9.1393  # Lisbon
    start_time = datetime.now(ZoneInfo("UTC"))
    end_time = start_time + timedelta(hours=24)
    
    # Mock cached location
    cached_location = {
        'code': '1110600',
        'name': 'Lisboa',
        'loc_lat': lat,
        'loc_lon': lon,
        'distance': 0.5
    }
    weather_service.location_cache.get_ipma_location = Mock(return_value=cached_location)
    
    # Mock API response
    mock_forecast_data = {
        'data': [
            {
                'precipitaProb': 10,
                'tMin': 15,
                'tMax': 25,
                'predWindDir': 'N',
                'idWeatherType': 1,
                'classWindSpeed': 2,
                'forecastDate': start_time.strftime('%Y-%m-%d')
            }
        ]
    }
    
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_forecast_data
        mock_response.content = json.dumps(mock_forecast_data).encode()
        mock_response.headers = {'content-type': 'application/json'}
        mock_get.return_value = mock_response
        
        result = weather_service.get_weather(lat, lon, start_time, end_time)
        
        assert result is not None
        assert len(result) > 0
        assert 15 <= result[0].temperature <= 25
        assert result[0].precipitation_probability == 10
        assert result[0].wind_direction == 'N'

@pytest.mark.asyncio
async def test_get_weather_api_error(weather_service):
    """Test handling of API errors."""
    lat, lon = 38.7223, -9.1393
    start_time = datetime.now(ZoneInfo("UTC"))
    end_time = start_time + timedelta(hours=24)
    
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.content = b'Internal Server Error'
        mock_response.headers = {'content-type': 'text/plain'}
        mock_get.return_value = mock_response
        
        result = weather_service.get_weather(lat, lon, start_time, end_time)
        assert result is None

@pytest.mark.asyncio
async def test_get_weather_no_cached_location(weather_service):
    """Test weather fetching without cached location."""
    lat, lon = 38.7223, -9.1393
    start_time = datetime.now(ZoneInfo("UTC"))
    end_time = start_time + timedelta(hours=24)
    
    # Mock no cached location
    weather_service.location_cache.get_ipma_location = Mock(return_value=None)
    
    # Mock API responses
    locations_data = {
        'data': [
            {
                'local': 'Lisboa',
                'globalIdLocal': '1110600',
                'latitude': str(lat),
                'longitude': str(lon)
            }
        ]
    }
    
    forecast_data = {
        'data': [
            {
                'precipitaProb': 0,
                'tMin': 18,
                'tMax': 28,
                'predWindDir': 'S',
                'idWeatherType': 2,
                'classWindSpeed': 1,
                'forecastDate': start_time.strftime('%Y-%m-%d')
            }
        ]
    }
    
    with patch('requests.get') as mock_get:
        def mock_response(*args, **kwargs):
            response = Mock()
            response.status_code = 200
            if 'forecast' in args[0]:
                response.json.return_value = forecast_data
                response.content = json.dumps(forecast_data).encode()
            else:
                response.json.return_value = locations_data
                response.content = json.dumps(locations_data).encode()
            response.headers = {'content-type': 'application/json'}
            return response
        
        mock_get.side_effect = mock_response
        
        result = weather_service.get_weather(lat, lon, start_time, end_time)
        
        assert result is not None
        assert len(result) > 0
        assert 18 <= result[0].temperature <= 28
        assert result[0].precipitation_probability == 0
        assert result[0].wind_direction == 'S'

@pytest.mark.asyncio
async def test_get_weather_invalid_coordinates(weather_service):
    """Test handling of invalid coordinates."""
    lat, lon = 91.0, -9.1393  # Invalid latitude
    start_time = datetime.now(ZoneInfo("UTC"))
    end_time = start_time + timedelta(hours=24)
    
    result = weather_service.get_weather(lat, lon, start_time, end_time)
    assert result is None

@pytest.mark.asyncio
async def test_get_weather_rate_limiting(weather_service):
    """Test rate limiting behavior."""
    lat, lon = 38.7223, -9.1393
    start_time = datetime.now(ZoneInfo("UTC"))
    end_time = start_time + timedelta(hours=24)
    
    # Mock API response
    mock_forecast_data = {
        'data': [
            {
                'precipitaProb': 10,
                'tMin': 15,
                'tMax': 25,
                'predWindDir': 'N',
                'idWeatherType': 1,
                'classWindSpeed': 2,
                'forecastDate': start_time.strftime('%Y-%m-%d')
            }
        ]
    }
    
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_forecast_data
        mock_response.content = json.dumps(mock_forecast_data).encode()
        mock_response.headers = {'content-type': 'application/json'}
        mock_get.return_value = mock_response
        
        # Make two requests in quick succession
        result1 = weather_service.get_weather(lat, lon, start_time, end_time)
        result2 = weather_service.get_weather(lat, lon, start_time, end_time)
        
        assert result1 is not None
        assert result2 is not None
        assert len(result1) > 0
        assert len(result2) > 0 