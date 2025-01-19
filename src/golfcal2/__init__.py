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
    WeatherError,
    CalendarError,
    CalendarWriteError,
    CalendarEventError
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
    'CalendarError',
    'CalendarWriteError',
    'CalendarEventError'
]
