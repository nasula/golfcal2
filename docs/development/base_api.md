# Base API Documentation

## Overview

The `BaseAPI` class provides a foundation for implementing API clients in GolfCal2. It handles common functionality such as request management, error handling, rate limiting, and authentication. The class is designed to be extended by specific service implementations, including weather service strategies.

## Core Components

### BaseAPI Class

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import requests
from requests.exceptions import RequestException
from golfcal2.utils.logging import get_logger
from golfcal2.utils.errors import APIError, RateLimitError

class BaseAPI(ABC):
    """Base class for API implementations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)
        self._setup_rate_limiting()
    
    @abstractmethod
    def _setup_rate_limiting(self) -> None:
        """Configure rate limiting for the API."""
        pass
    
    def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """Make HTTP request with error handling and rate limiting."""
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                **kwargs
            )
            
            if response.status_code == 429:
                raise RateLimitError(
                    f"Rate limit exceeded for {self.__class__.__name__}"
                )
            
            response.raise_for_status()
            return response.json()
            
        except RequestException as e:
            self.logger.error(f"API request failed: {str(e)}")
            raise APIError(f"Request failed: {str(e)}")
```

## Error Handling

### Error Classes

```python
class APIError(Exception):
    """Base class for API-related errors."""
    pass

class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    pass

class AuthenticationError(APIError):
    """Raised for authentication/authorization failures."""
    pass

class ValidationError(APIError):
    """Raised for invalid request parameters."""
    pass
```

### Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| 1000 | Generic API Error | 500 |
| 1001 | Rate Limit Exceeded | 429 |
| 1002 | Authentication Failed | 401 |
| 1003 | Invalid Parameters | 400 |
| 1004 | Resource Not Found | 404 |
| 1005 | Service Unavailable | 503 |

## Implementation Example

### Weather Strategy Implementation

```python
from golfcal2.services.base_api import BaseAPI
from golfcal2.services.weather_types import WeatherContext, WeatherResponse

class MetWeatherStrategy(BaseAPI):
    """Met.no weather service implementation."""
    
    def __init__(self, context: WeatherContext):
        super().__init__(context.config)
        self.context = context
        self.base_url = "https://api.met.no/weatherapi/locationforecast/2.0"
    
    def _setup_rate_limiting(self) -> None:
        """Configure rate limiting for Met.no API."""
        self.requests_per_minute = 60
        self.min_request_interval = 1.0  # seconds
    
    def get_weather(self) -> WeatherResponse:
        """Fetch weather data from Met.no."""
        params = {
            'lat': self.context.lat,
            'lon': self.context.lon
        }
        
        headers = {
            'User-Agent': 'GolfCal2/1.0'
        }
        
        try:
            data = self._make_request(
                method='GET',
                url=f"{self.base_url}/compact",
                params=params,
                headers=headers
            )
            return self._parse_response(data)
            
        except APIError as e:
            self.logger.error(f"Failed to fetch Met.no weather: {str(e)}")
            raise
```

## Best Practices

### Request Handling

1. Always use the `_make_request` method from `BaseAPI` for HTTP requests
2. Include appropriate error handling and logging
3. Respect rate limits and implement backoff strategies
4. Use type hints and docstrings for better code clarity

### Error Management

1. Use appropriate error classes for different failure scenarios
2. Include relevant context in error messages
3. Log errors with sufficient detail for debugging
4. Handle rate limiting gracefully with retries when appropriate

### Logging

1. Use the logger from `BaseAPI` for consistent logging
2. Include request/response details at DEBUG level
3. Log errors with stack traces at ERROR level
4. Add correlation IDs for request tracking

### Authentication

1. Use environment variables for API keys
2. Implement token refresh mechanisms when needed
3. Handle authentication errors appropriately
4. Log authentication failures securely

## Testing

```python
import pytest
from unittest.mock import Mock, patch
from golfcal2.services.base_api import BaseAPI

class TestAPI(BaseAPI):
    """Test implementation of BaseAPI."""
    def _setup_rate_limiting(self):
        self.requests_per_minute = 60

def test_rate_limiting():
    """Test rate limiting functionality."""
    api = TestAPI({})
    assert api.requests_per_minute == 60

@pytest.mark.integration
def test_api_request():
    """Test API request handling."""
    api = TestAPI({})
    with patch('requests.request') as mock_request:
        mock_request.return_value.json.return_value = {'data': 'test'}
        mock_request.return_value.status_code = 200
        
        response = api._make_request('GET', 'https://api.test.com')
        assert response == {'data': 'test'}
``` 