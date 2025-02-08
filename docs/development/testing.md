# Testing Guide

## Overview

GolfCal2 uses pytest for testing and includes unit tests, integration tests, and end-to-end tests. This guide explains how to write and run tests effectively.

## Test Structure

```
tests/
├── unit/
│   ├── services/
│   │   ├── test_calendar_service.py
│   │   ├── test_reservation_service.py
│   │   ├── test_weather/
│   │   │   ├── test_weather_service.py
│   │   │   ├── test_met_strategy.py
│   │   │   └── test_openmeteo_strategy.py
│   │   └── test_auth_service.py
│   ├── models/
│   │   ├── test_reservation.py
│   │   ├── test_club.py
│   │   └── test_user.py
│   └── utils/
│       ├── test_logging.py
│       └── test_config.py
├── integration/
│   ├── test_weather_integration.py
│   ├── test_club_integration.py
│   └── test_calendar_integration.py
└── e2e/
    ├── test_reservation_flow.py
    └── test_calendar_flow.py
```

## Running Tests

### Basic Usage

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/services/test_weather/test_weather_service.py

# Run tests matching pattern
pytest -k "weather"

# Run with coverage
pytest --cov=golfcal2

# Generate coverage report
pytest --cov=golfcal2 --cov-report=html
```

### Test Configuration

Create `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --verbose --tb=short --cov=golfcal2
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
```

## Writing Tests

### Unit Tests

```python
import pytest
from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_types import WeatherContext

def test_weather_service_initialization():
    """Test WeatherService initialization."""
    config = {
        'timezone': 'Europe/Oslo',
        'dev_mode': False
    }
    service = WeatherService(config)
    assert 'met' in service._strategies
    assert 'openmeteo' in service._strategies

@pytest.mark.parametrize('coordinates,expected_service', [
    ((60.1699, 24.9384), 'met'),  # Helsinki (Nordic)
    ((41.8789, 2.7649), 'openmeteo')  # Barcelona (Other)
])
def test_service_selection(coordinates, expected_service):
    """Test weather service selection based on location."""
    service = WeatherService({})
    lat, lon = coordinates
    selected = service._select_service_for_location(lat, lon)
    assert selected == expected_service

def test_weather_strategy_block_sizes():
    """Test block size calculations for different ranges."""
    context = WeatherContext(
        lat=60.1699,
        lon=24.9384,
        start_time=datetime.now(ZoneInfo('UTC')),
        end_time=datetime.now(ZoneInfo('UTC')) + timedelta(hours=24),
        local_tz=ZoneInfo('Europe/Helsinki'),
        utc_tz=ZoneInfo('UTC'),
        config={}
    )
    
    met_strategy = MetWeatherStrategy(context)
    assert met_strategy.get_block_size(24) == 1  # Short range
    assert met_strategy.get_block_size(72) == 6  # Medium range
    assert met_strategy.get_block_size(192) == 12  # Long range
```

### Integration Tests

```python
import pytest
from golfcal2.services import WeatherService, CalendarService

@pytest.mark.integration
def test_weather_calendar_integration(config):
    """Test weather integration with calendar service."""
    weather_service = WeatherService(config)
    calendar_service = CalendarService(config)
    
    # Create test reservation
    reservation = create_test_reservation()
    
    # Process reservation
    event = calendar_service.process_reservation(reservation)
    
    # Verify weather data
    assert event.weather is not None
    assert hasattr(event.weather[0], 'temperature')
    assert hasattr(event.weather[0], 'precipitation')
```

### End-to-End Tests

```python
import pytest
from golfcal2.cli import main

@pytest.mark.e2e
def test_reservation_list_flow():
    """Test end-to-end reservation listing flow."""
    result = main(['list', 'reservations', '-u', 'test_user'])
    assert result.exit_code == 0
    assert 'Reservations for test_user' in result.output
    assert 'Weather:' in result.output
```

## Test Fixtures

### Configuration Fixture

```python
import pytest
import yaml
from zoneinfo import ZoneInfo

@pytest.fixture
def config():
    """Provide test configuration."""
    return {
        'timezone': 'Europe/Oslo',
        'dev_mode': True,
        'directories': {
            'cache': 'tests/data/cache'
        }
    }

@pytest.fixture
def weather_service(config):
    """Provide configured WeatherService."""
    return WeatherService(config)

@pytest.fixture
def weather_context():
    """Provide test WeatherContext."""
    return WeatherContext(
        lat=59.8940,
        lon=10.8282,
        start_time=datetime.now(ZoneInfo('UTC')),
        end_time=datetime.now(ZoneInfo('UTC')) + timedelta(hours=24),
        local_tz=ZoneInfo('Europe/Oslo'),
        utc_tz=ZoneInfo('UTC'),
        config={}
    )
```

### Mock Services

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_weather_strategy():
    """Provide mock weather strategy."""
    strategy = Mock()
    strategy.get_weather.return_value = WeatherResponse(
        data=[
            WeatherData(
                temperature=20.0,
                precipitation=0.0,
                precipitation_probability=0.0,
                wind_speed=5.0,
                wind_direction='N',
                weather_code=WeatherCode.CLEARSKY_DAY,
                time=datetime.now(ZoneInfo('UTC')),
                block_duration=timedelta(hours=1)
            )
        ],
        expires=datetime.now(ZoneInfo('UTC')) + timedelta(hours=1)
    )
    return strategy
```

## Test Data

### Test Events

```python
@pytest.fixture
def test_events():
    """Provide test events for different ranges and regions."""
    return [
        {
            'name': 'Oslo GC Tomorrow',
            'location': 'Oslo Golf Club',
            'coordinates': {'lat': 59.8940, 'lon': 10.8282},
            'start_time': 'tomorrow 10:00',
            'end_time': 'tomorrow 14:00',
            'timezone': 'Europe/Oslo'
        },
        {
            'name': 'PGA Catalunya 4 Days',
            'location': 'PGA Catalunya',
            'coordinates': {'lat': 41.8789, 'lon': 2.7649},
            'start_time': '4 days 09:30',
            'end_time': '4 days 14:30',
            'timezone': 'Europe/Madrid'
        }
    ]
```

## Best Practices

1. **Test Organization**
   - Group related tests
   - Use descriptive names
   - Follow test hierarchy
   - Keep tests focused

2. **Test Coverage**
   - Aim for high coverage
   - Test edge cases
   - Test error conditions
   - Test integrations

3. **Test Performance**
   - Use appropriate fixtures
   - Mock external services
   - Optimize test data
   - Clean up resources

4. **Test Maintenance**
   - Keep tests up to date
   - Refactor when needed
   - Document test requirements
   - Review test failures

## Related Documentation

- [Development Setup](setup.md)
- [Contributing Guidelines](contributing.md)
- [API Documentation](../api/README.md)
``` 