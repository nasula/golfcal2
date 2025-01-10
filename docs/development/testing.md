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
│   │   ├── test_weather_service.py
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
pytest tests/unit/services/test_weather_service.py

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
from golfcal2.services.weather_service import WeatherManager

def test_weather_manager_initialization():
    """Test WeatherManager initialization."""
    config = {
        'weather': {
            'met': {'user_agent': 'Test/1.0'},
            'openweather': {'api_key': 'test-key'}
        }
    }
    manager = WeatherManager(config)
    assert manager.services['met'] is not None
    assert manager.services['openweather'] is not None

@pytest.mark.parametrize('coordinates,expected', [
    ({'lat': 60.1699, 'lon': 24.9384}, True),
    ({'lat': 91.0, 'lon': 181.0}, False)
])
def test_validate_coordinates(coordinates, expected):
    """Test coordinate validation."""
    manager = WeatherManager({})
    assert manager.validate_coordinates(coordinates) == expected
```

### Integration Tests

```python
import pytest
from golfcal2.services import WeatherManager, CalendarService

@pytest.mark.integration
def test_weather_calendar_integration(config):
    """Test weather integration with calendar service."""
    weather_manager = WeatherManager(config)
    calendar_service = CalendarService(config)
    
    # Create test reservation
    reservation = create_test_reservation()
    
    # Process reservation
    event = calendar_service.process_reservation(reservation)
    
    # Verify weather data
    assert event.weather is not None
    assert 'temperature' in event.weather
    assert 'precipitation' in event.weather
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

@pytest.fixture
def config():
    """Provide test configuration."""
    with open('config.test.yaml') as f:
        return yaml.safe_load(f)

@pytest.fixture
def weather_manager(config):
    """Provide configured WeatherManager."""
    return WeatherManager(config)

@pytest.fixture
def calendar_service(config, weather_manager):
    """Provide configured CalendarService."""
    return CalendarService(config, weather_manager)
```

### Mock Services

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_weather_service():
    """Provide mock weather service."""
    service = Mock()
    service.get_weather.return_value = {
        'temperature': 20.0,
        'precipitation': 0.0,
        'wind_speed': 5.0
    }
    return service

@pytest.fixture
def mock_club_api():
    """Provide mock golf club API."""
    api = Mock()
    api.get_reservations.return_value = [
        {
            'date': '2024-01-10',
            'time': '10:00',
            'players': ['Test User']
        }
    ]
    return api
```

## Mocking

### API Responses

```python
@pytest.mark.unit
def test_weather_service_with_mock(mock_weather_service):
    """Test weather service with mocked API."""
    weather_data = mock_weather_service.get_weather(
        coordinates={'lat': 60.1699, 'lon': 24.9384},
        time='2024-01-10T10:00:00Z'
    )
    assert weather_data['temperature'] == 20.0
    assert weather_data['precipitation'] == 0.0
```

### External Services

```python
@pytest.mark.unit
@patch('golfcal2.services.weather_service.requests.get')
def test_weather_api_call(mock_get):
    """Test weather API call with mocked response."""
    mock_get.return_value.json.return_value = {
        'temperature': 20.0,
        'precipitation': 0.0
    }
    mock_get.return_value.status_code = 200
    
    manager = WeatherManager({})
    data = manager.get_weather(
        coordinates={'lat': 60.1699, 'lon': 24.9384}
    )
    assert data['temperature'] == 20.0
```

## Test Data

### Factory Fixtures

```python
import pytest
from datetime import datetime, timedelta

@pytest.fixture
def create_reservation():
    """Factory for creating test reservations."""
    def _create(
        start_time=None,
        duration_minutes=60,
        club_name="TestGolf",
        players=None
    ):
        if start_time is None:
            start_time = datetime.now()
        if players is None:
            players = ["Test User"]
            
        return {
            'start_time': start_time,
            'end_time': start_time + timedelta(minutes=duration_minutes),
            'club': club_name,
            'players': players
        }
    return _create
```

### Database Fixtures

```python
import pytest
import sqlite3

@pytest.fixture
def test_db():
    """Provide test database connection."""
    conn = sqlite3.connect(':memory:')
    yield conn
    conn.close()

@pytest.fixture
def weather_db(test_db):
    """Initialize weather database."""
    cursor = test_db.cursor()
    cursor.execute('''
        CREATE TABLE weather (
            id INTEGER PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            temperature REAL,
            precipitation REAL,
            timestamp TEXT
        )
    ''')
    test_db.commit()
    return test_db
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