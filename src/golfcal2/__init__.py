"""
Golf calendar application.
"""

__version__ = '0.6.0'

from .exceptions import APIError
from .exceptions import APIRateLimitError
from .exceptions import APIResponseError
from .exceptions import APITimeoutError
from .exceptions import AuthError
from .exceptions import CalendarError
from .exceptions import CalendarEventError
from .exceptions import CalendarWriteError
from .exceptions import ConfigError
from .exceptions import GolfCalError
from .exceptions import ValidationError
from .services.weather_types import WeatherAuthError
from .services.weather_types import WeatherError
from .services.weather_types import WeatherLocationError
from .services.weather_types import WeatherServiceError
from .services.weather_types import WeatherServiceInvalidResponse
from .services.weather_types import WeatherServiceRateLimited
from .services.weather_types import WeatherServiceTimeout
from .services.weather_types import WeatherServiceUnavailable
from .services.weather_types import WeatherValidationError


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
