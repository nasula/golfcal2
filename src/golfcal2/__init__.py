"""
Golf calendar application.
"""

__version__ = '0.6.0'

from .exceptions import (
    APIError,
    APIRateLimitError,
    APIResponseError,
    APITimeoutError,
    AuthError,
    CalendarError,
    CalendarEventError,
    CalendarWriteError,
    ConfigError,
    GolfCalError,
    ValidationError,
)
from .services.weather_types import (
    WeatherAuthError,
    WeatherError,
    WeatherLocationError,
    WeatherServiceError,
    WeatherServiceInvalidResponse,
    WeatherServiceRateLimited,
    WeatherServiceTimeout,
    WeatherServiceUnavailable,
    WeatherValidationError,
)

__all__ = [
    'APIError',
    'APIRateLimitError',
    'APIResponseError',
    'APITimeoutError',
    'AuthError',
    'CalendarError',
    'CalendarEventError',
    'CalendarWriteError',
    'ConfigError',
    'GolfCalError',
    'ValidationError',
    'WeatherAuthError',
    'WeatherError',
    'WeatherLocationError',
    'WeatherServiceError',
    'WeatherServiceInvalidResponse',
    'WeatherServiceRateLimited',
    'WeatherServiceTimeout',
    'WeatherServiceUnavailable',
    'WeatherValidationError'
]
