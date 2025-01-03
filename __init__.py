"""
Golf calendar application package.
"""

__package__ = 'golfcal2'
__version__ = '1.0.0'

from golfcal2.exceptions import (
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

def verify_package():
    """Verify that we're running under the correct package."""
    import sys
    module = sys.modules[__name__]
    if module.__package__ != 'golfcal2':
        raise ImportError(f"Package is running as '{module.__package__}' instead of 'golfcal2'")
    return True
