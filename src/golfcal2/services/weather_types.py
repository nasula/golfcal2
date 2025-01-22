"""Weather service types and base classes."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Union, Iterator, cast, TypeVar, Callable, overload
from zoneinfo import ZoneInfo
import requests

from golfcal2.exceptions import ErrorCode, GolfCalError, handle_errors

class WeatherCode(str, Enum):
    """Standard weather codes used across all weather services."""
    CLEARSKY_DAY = 'clearsky_day'
    CLEARSKY_NIGHT = 'clearsky_night'
    FAIR_DAY = 'fair_day'
    FAIR_NIGHT = 'fair_night'
    PARTLYCLOUDY_DAY = 'partlycloudy_day'
    PARTLYCLOUDY_NIGHT = 'partlycloudy_night'
    CLOUDY = 'cloudy'
    FOG = 'fog'
    LIGHTRAIN = 'lightrain'
    RAIN = 'rain'
    HEAVYRAIN = 'heavyrain'
    LIGHTRAINSHOWERS_DAY = 'lightrainshowers_day'
    LIGHTRAINSHOWERS_NIGHT = 'lightrainshowers_night'
    RAINSHOWERS_DAY = 'rainshowers_day'
    RAINSHOWERS_NIGHT = 'rainshowers_night'
    HEAVYRAINSHOWERS_DAY = 'heavyrainshowers_day'
    HEAVYRAINSHOWERS_NIGHT = 'heavyrainshowers_night'
    LIGHTSLEET = 'lightsleet'
    SLEET = 'sleet'
    HEAVYSLEET = 'heavysleet'
    LIGHTSLEETSHOWERS_DAY = 'lightsleetshowers_day'
    LIGHTSLEETSHOWERS_NIGHT = 'lightsleetshowers_night'
    SLEETSHOWERS_DAY = 'sleetshowers_day'
    SLEETSHOWERS_NIGHT = 'sleetshowers_night'
    HEAVYSLEETSHOWERS_DAY = 'heavysleetshowers_day'
    HEAVYSLEETSHOWERS_NIGHT = 'heavysleetshowers_night'
    LIGHTSNOW = 'lightsnow'
    SNOW = 'snow'
    HEAVYSNOW = 'heavysnow'
    LIGHTSNOWSHOWERS_DAY = 'lightsnowshowers_day'
    LIGHTSNOWSHOWERS_NIGHT = 'lightsnowshowers_night'
    SNOWSHOWERS_DAY = 'snowshowers_day'
    SNOWSHOWERS_NIGHT = 'snowshowers_night'
    HEAVYSNOWSHOWERS_DAY = 'heavysnowshowers_day'
    HEAVYSNOWSHOWERS_NIGHT = 'heavysnowshowers_night'
    THUNDER = 'thunder'
    LIGHTRAINANDTHUNDER = 'lightrainandthunder'
    RAINANDTHUNDER = 'rainandthunder'
    HEAVYRAINANDTHUNDER = 'heavyrainandthunder'
    LIGHTSLEETANDTHUNDER = 'lightsleetandthunder'
    SLEETANDTHUNDER = 'sleetandthunder'
    HEAVYSLEETANDTHUNDER = 'heavysleetandthunder'
    LIGHTSNOWANDTHUNDER = 'lightsnowandthunder'
    SNOWANDTHUNDER = 'snowandthunder'
    HEAVYSNOWANDTHUNDER = 'heavysnowandthunder'
    LIGHTRAINSHOWERSANDTHUNDER_DAY = 'lightrainshowersandthunder_day'
    LIGHTRAINSHOWERSANDTHUNDER_NIGHT = 'lightrainshowersandthunder_night'
    RAINSHOWERSANDTHUNDER_DAY = 'rainshowersandthunder_day'
    RAINSHOWERSANDTHUNDER_NIGHT = 'rainshowersandthunder_night'
    HEAVYRAINSHOWERSANDTHUNDER_DAY = 'heavyrainshowersandthunder_day'
    HEAVYRAINSHOWERSANDTHUNDER_NIGHT = 'heavyrainshowersandthunder_night'
    LIGHTSLEETSHOWERSANDTHUNDER_DAY = 'lightsleetshowersandthunder_day'
    LIGHTSLEETSHOWERSANDTHUNDER_NIGHT = 'lightsleetshowersandthunder_night'
    SLEETSHOWERSANDTHUNDER_DAY = 'sleetshowersandthunder_day'
    SLEETSHOWERSANDTHUNDER_NIGHT = 'sleetshowersandthunder_night'
    HEAVYSLEETSHOWERSANDTHUNDER_DAY = 'heavysleetshowersandthunder_day'
    HEAVYSLEETSHOWERSANDTHUNDER_NIGHT = 'heavysleetshowersandthunder_night'
    LIGHTSNOWSHOWERSANDTHUNDER_DAY = 'lightsnowshowersandthunder_day'
    LIGHTSNOWSHOWERSANDTHUNDER_NIGHT = 'lightsnowshowersandthunder_night'
    SNOWSHOWERSANDTHUNDER_DAY = 'snowshowersandthunder_day'
    SNOWSHOWERSANDTHUNDER_NIGHT = 'snowshowersandthunder_night'
    HEAVYSNOWSHOWERSANDTHUNDER_DAY = 'heavysnowshowersandthunder_day'
    HEAVYSNOWSHOWERSANDTHUNDER_NIGHT = 'heavysnowshowersandthunder_night'
    UNKNOWN = 'unknown'

def get_weather_symbol(symbol_code: str) -> str:
    """Map weather symbol codes to emojis."""
    emoji_map = {
        # Clear and cloudy conditions
        'clearsky_day': '☀️',
        'clearsky_night': '🌙',
        'fair_day': '🌤️',
        'fair_night': '🌤️',
        'partlycloudy_day': '⛅',
        'partlycloudy_night': '⛅',
        'cloudy': '☁️',
        'fog': '🌫️',
        
        # Rain
        'lightrain': '🌧️',
        'rain': '🌧️',
        'heavyrain': '🌧️',
        'lightrainshowers_day': '🌦️',
        'lightrainshowers_night': '🌦️',
        'rainshowers_day': '🌦️',
        'rainshowers_night': '🌦️',
        'heavyrainshowers_day': '🌦️',
        'heavyrainshowers_night': '🌦️',
        
        # Sleet
        'lightsleet': '🌨️',
        'sleet': '🌨️',
        'heavysleet': '🌨️',
        'lightsleetshowers_day': '🌨️',
        'lightsleetshowers_night': '🌨️',
        'sleetshowers_day': '🌨️',
        'sleetshowers_night': '🌨️',
        'heavysleetshowers_day': '🌨️',
        'heavysleetshowers_night': '🌨️',
        
        # Snow
        'lightsnow': '🌨️',
        'snow': '🌨️',
        'heavysnow': '🌨️',
        'lightsnowshowers_day': '🌨️',
        'lightsnowshowers_night': '🌨️',
        'snowshowers_day': '🌨️',
        'snowshowers_night': '🌨️',
        'heavysnowshowers_day': '🌨️',
        'heavysnowshowers_night': '🌨️',
        
        # Thunder
        'thunder': '⛈️',
        'lightrainandthunder': '⛈️',
        'rainandthunder': '⛈️',
        'heavyrainandthunder': '⛈️',
        'lightsleetandthunder': '⛈️',
        'sleetandthunder': '⛈️',
        'heavysleetandthunder': '⛈️',
        'lightsnowandthunder': '⛈️',
        'snowandthunder': '⛈️',
        'heavysnowandthunder': '⛈️',
        'lightrainshowersandthunder_day': '⛈️',
        'lightrainshowersandthunder_night': '⛈️',
        'rainshowersandthunder_day': '⛈️',
        'rainshowersandthunder_night': '⛈️',
        'heavyrainshowersandthunder_day': '⛈️',
        'heavyrainshowersandthunder_night': '⛈️',
        'lightsleetshowersandthunder_day': '⛈️',
        'lightsleetshowersandthunder_night': '⛈️',
        'sleetshowersandthunder_day': '⛈️',
        'sleetshowersandthunder_night': '⛈️',
        'heavysleetshowersandthunder_day': '⛈️',
        'heavysleetshowersandthunder_night': '⛈️',
        'lightsnowshowersandthunder_day': '⛈️',
        'lightsnowshowersandthunder_night': '⛈️',
        'snowshowersandthunder_day': '⛈️',
        'snowshowersandthunder_night': '⛈️',
        'heavysnowshowersandthunder_day': '⛈️',
        'heavysnowshowersandthunder_night': '⛈️',
        'unknown': '☁️'
    }
    return emoji_map.get(symbol_code, '☁️')  # Default to cloudy if code not found

@dataclass
class Location:
    """Location data container."""
    id: str
    name: str
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    region: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert location data to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "region": self.region,
            "country": self.country,
            "timezone": self.timezone,
            "metadata": self.metadata
        }

@dataclass
class WeatherData:
    """Container for weather data."""
    elaboration_time: datetime
    temperature: Optional[float] = None
    precipitation: Optional[float] = None
    precipitation_probability: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    weather_code: Union[WeatherCode, str] = WeatherCode.UNKNOWN
    weather_description: str = ''  # Human-readable description
    thunder_probability: Optional[float] = None
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    symbol_time_range: Optional[str] = None  # Time range for the weather symbol (e.g. "10:00-11:00")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Convert string values to appropriate types."""
        if isinstance(self.temperature, str):
            self.temperature = float(self.temperature)
        if isinstance(self.precipitation, str):
            self.precipitation = float(self.precipitation)
        if isinstance(self.precipitation_probability, str):
            self.precipitation_probability = float(self.precipitation_probability)
        if isinstance(self.wind_speed, str):
            self.wind_speed = float(self.wind_speed)
        if isinstance(self.wind_direction, str):
            try:
                self.wind_direction = float(self.wind_direction)
            except (ValueError, TypeError):
                self.wind_direction = 0.0
        if isinstance(self.thunder_probability, str):
            self.thunder_probability = float(self.thunder_probability)
        if isinstance(self.weather_code, str):
            try:
                self.weather_code = WeatherCode(self.weather_code)
            except ValueError:
                self.weather_code = WeatherCode.UNKNOWN
        
        # Set min/max temperatures
        self.temperature_min = self._convert_to_float(self.temperature_min, self.temperature)
        self.temperature_max = self._convert_to_float(self.temperature_max, self.temperature)

    def _convert_to_float(self, value: Optional[Union[float, str]], default: Optional[float] = None) -> Optional[float]:
        """Convert string value to float."""
        if value is None:
            return default
        if isinstance(value, float):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @property
    def symbol(self) -> str:
        """Get weather symbol."""
        if isinstance(self.weather_code, str):
            return self.weather_code
        return get_weather_symbol(self.weather_code)

    def __str__(self) -> str:
        """Return string representation of weather data."""
        return (
            f"WeatherData("
            f"time={self.elaboration_time.isoformat()}, "
            f"temp={self.temperature}°C, "
            f"precip={self.precipitation}mm, "
            f"wind={self.wind_speed}m/s@{self.wind_direction}°"
            f")"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'elaboration_time': self.elaboration_time.isoformat(),
            'temperature': self.temperature,
            'precipitation': self.precipitation,
            'precipitation_probability': self.precipitation_probability,
            'wind_speed': self.wind_speed,
            'wind_direction': self.wind_direction,
            'weather_code': self.weather_code.value if isinstance(self.weather_code, WeatherCode) else self.weather_code,
            'weather_description': self.weather_description,
            'thunder_probability': self.thunder_probability,
            'temperature_min': self.temperature_min,
            'temperature_max': self.temperature_max,
            'symbol_time_range': self.symbol_time_range,
            'metadata': self.metadata
        }

T = TypeVar('T', bound='WeatherData')

@dataclass
class WeatherResponse:
    """Container for weather service responses."""
    data: Union[WeatherData, List[WeatherData]]
    elaboration_time: datetime
    expires: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.data, list):
            self.data = [self.data]

    def __len__(self) -> int:
        return len(self.data)  # Now data is always a list

    def __iter__(self) -> Iterator[WeatherData]:
        return iter(self.data)  # Now data is always a list

    def __getitem__(self, idx: int) -> WeatherData:
        return self.data[idx]  # Now data is always a list

    def to_dict(self) -> Dict[str, Any]:
        return {
            'data': [d.to_dict() for d in self.data],
            'elaboration_time': self.elaboration_time.isoformat(),
            'expires': self.expires.isoformat() if self.expires else None,
            'metadata': self.metadata
        }

    def __str__(self) -> str:
        return f"WeatherResponse(data={self.data}, elaboration_time={self.elaboration_time}, expires={self.expires})"

class WeatherError(GolfCalError):
    """Base class for weather service errors."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.WEATHER_ERROR, 
                 traceback: Optional[str] = None) -> None:
        """Initialize weather error."""
        super().__init__(message, error_code, traceback)

class WeatherServiceError(WeatherError):
    """Error raised when weather service fails."""
    def __init__(self, message: str, traceback: Optional[str] = None) -> None:
        """Initialize weather service error."""
        super().__init__(message, ErrorCode.WEATHER_SERVICE_ERROR, traceback)

class WeatherParseError(WeatherError):
    """Error raised when parsing weather data fails."""
    def __init__(self, message: str, traceback: Optional[str] = None) -> None:
        """Initialize weather parse error."""
        super().__init__(message, ErrorCode.WEATHER_PARSE_ERROR, traceback)

class WeatherRequestError(WeatherError):
    """Error raised when weather request fails."""
    def __init__(self, message: str, traceback: Optional[str] = None) -> None:
        """Initialize weather request error."""
        super().__init__(message, ErrorCode.WEATHER_REQUEST_ERROR, traceback)

class WeatherTimeoutError(WeatherError):
    """Error raised when weather request times out."""
    def __init__(self, message: str, traceback: Optional[str] = None) -> None:
        """Initialize weather timeout error."""
        super().__init__(message, ErrorCode.WEATHER_TIMEOUT_ERROR, traceback)

class WeatherAuthError(WeatherError):
    """Error raised when weather service authentication fails."""
    def __init__(self, message: str, traceback: Optional[str] = None) -> None:
        """Initialize weather auth error."""
        super().__init__(message, ErrorCode.WEATHER_AUTH_ERROR, traceback)

class WeatherLocationError(WeatherError):
    """Error raised when location data is invalid or missing."""
    def __init__(self, message: str, traceback: Optional[str] = None) -> None:
        """Initialize weather location error."""
        super().__init__(message, ErrorCode.WEATHER_LOCATION_ERROR, traceback)

@handle_errors(GolfCalError, service="weather", operation="base")
class WeatherService:
    """Base class for weather services."""
    utc: ZoneInfo = field(default_factory=lambda: ZoneInfo('UTC'))
    config: Dict[str, Any] = field(default_factory=dict)

    def get_weather(self, latitude: float, longitude: float, start_time: datetime, end_time: datetime) -> Optional[WeatherResponse]:
        """Get weather data for a location and time range.
        
        Args:
            latitude: The latitude of the location.
            longitude: The longitude of the location.
            start_time: The start time of the forecast.
            end_time: The end time of the forecast.
        
        Returns:
            WeatherResponse object containing the weather data, or None if no data is available.
        """
        try:
            response_data = self._fetch_forecasts(latitude, longitude, start_time, end_time)
            if response_data is None:
                return None
            return self._parse_response(response_data)
        except Exception as e:
            self._handle_errors(ErrorCode.WEATHER_ERROR, str(e))
            return None

    def _fetch_forecasts(self, latitude: float, longitude: float, start_time: datetime, end_time: datetime) -> Optional[Dict[str, Any]]:
        """Fetch forecasts from the weather service.
        
        Args:
            latitude: The latitude of the location.
            longitude: The longitude of the location.
            start_time: The start time of the forecast.
            end_time: The end time of the forecast.
        
        Returns:
            Dictionary containing the forecast data, or None if no data is available.
        """
        raise NotImplementedError("Subclasses must implement _fetch_forecasts")

    def _parse_response(self, response_data: Dict[str, Any]) -> Optional[WeatherResponse]:
        """Parse the response from the weather service.
        
        Args:
            response_data: The response data from the weather service.
        
        Returns:
            WeatherResponse object containing the weather data, or None if no data is available.
        """
        raise NotImplementedError("Subclasses must implement _parse_response")

    def _create_response(self, data: Union[WeatherData, List[WeatherData]], elaboration_time: datetime, expires: Optional[datetime] = None) -> WeatherResponse:
        """Create a weather response object.
        
        Args:
            data: The weather data to include in the response.
            elaboration_time: The time the forecast was elaborated.
            expires: Optional expiration time for the forecast.
        
        Returns:
            WeatherResponse object containing the weather data.
        """
        return WeatherResponse(data=data, elaboration_time=elaboration_time, expires=expires)

    def _handle_errors(self, error_code: ErrorCode, message: str, traceback: Optional[str] = None, recovery_func: Optional[Callable[[], Iterator[Any]]] = None) -> None:
        """Handle errors and attempt recovery if possible.
        
        Args:
            error_code: The error code to use.
            message: The error message.
            traceback: Optional traceback information.
            recovery_func: Optional function to call for recovery.
        """
        try:
            if recovery_func:
                return next(recovery_func())
        except Exception as e:
            message = f"{message} (Recovery failed: {str(e)})"
        aggregate_error(error_code, message, traceback)

def handle_errors(
    error_class: type[GolfCalError],
    service: str = "",
    operation: str = "",
    recovery_func: Optional[Callable[[], Iterator[Any]]] = None
) -> Callable[[Any], Any]:
    """Decorator for handling errors in weather services.
    
    Args:
        error_class: The error class to use for the error.
        service: The service name for error context.
        operation: The operation name for error context.
        recovery_func: Optional function to call for recovery.
    
    Returns:
        Decorator function that handles errors.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except error_class as e:
                if recovery_func:
                    try:
                        return recovery_func()
                    except Exception as recovery_error:
                        aggregate_error(
                            error_class,
                            f"Recovery failed for {service}.{operation}",
                            str(recovery_error)
                        )
                aggregate_error(
                    error_class,
                    f"Error in {service}.{operation}",
                    str(e)
                )
                return None
            except Exception as e:
                aggregate_error(
                    error_class,
                    f"Unexpected error in {service}.{operation}",
                    str(e)
                )
                return None
        return wrapper
    return decorator 