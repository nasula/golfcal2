"""
Golf calendar application.
"""

__version__ = '0.6.0'

from .exceptions import (
    GolfCalError,
    APIError,
    APITimeoutError,
    APIRateLimitError,
    APIResponseError,
    AuthError,
    ConfigError,
    ValidationError,
    CalendarError,
    CalendarWriteError,
    CalendarEventError
)

from .services.weather_types import (
    WeatherError,
    WeatherServiceError,
    WeatherServiceUnavailable,
    WeatherServiceTimeout,
    WeatherServiceRateLimited,
    WeatherServiceInvalidResponse,
    WeatherAuthError,
    WeatherValidationError,
    WeatherLocationError
)

__all__ = [
    'GolfCalError',
    'APIError',
    'APITimeoutError',
    'APIRateLimitError',
    'APIResponseError',
    'AuthError',
    'ConfigError',
    'ValidationError',
    'WeatherError',
    'WeatherServiceError',
    'WeatherServiceUnavailable',
    'WeatherServiceTimeout',
    'WeatherServiceRateLimited',
    'WeatherServiceInvalidResponse',
    'WeatherAuthError',
    'WeatherValidationError',
    'WeatherLocationError',
    'CalendarError',
    'CalendarWriteError',
    'CalendarEventError'
]
