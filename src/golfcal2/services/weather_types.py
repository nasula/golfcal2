"""Weather service types and base classes."""

import traceback
from abc import ABC
from abc import abstractmethod
from collections.abc import Iterable
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from enum import Enum
from typing import Any
from typing import TypeVar
from zoneinfo import ZoneInfo

import requests

from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.error_codes import ErrorCode
from golfcal2.exceptions import GolfCalError
from golfcal2.exceptions import handle_errors


class SupportsIter(Iterable[Any]):
    """Protocol for types that support iteration."""
    pass

class WeatherCode(Enum):
    """Weather codes."""
    UNKNOWN = "UNKNOWN"
    CLEARSKY_DAY = "CLEARSKY_DAY"
    CLEARSKY_NIGHT = "CLEARSKY_NIGHT"
    FAIR_DAY = "FAIR_DAY"
    FAIR_NIGHT = "FAIR_NIGHT"
    PARTLYCLOUDY_DAY = "PARTLYCLOUDY_DAY"
    PARTLYCLOUDY_NIGHT = "PARTLYCLOUDY_NIGHT"
    CLOUDY = "CLOUDY"
    RAINSHOWERS_DAY = "RAINSHOWERS_DAY"
    RAINSHOWERS_NIGHT = "RAINSHOWERS_NIGHT"
    LIGHTRAINSHOWERS_DAY = "LIGHTRAINSHOWERS_DAY"
    LIGHTRAINSHOWERS_NIGHT = "LIGHTRAINSHOWERS_NIGHT"
    HEAVYRAINSHOWERS_DAY = "HEAVYRAINSHOWERS_DAY"
    HEAVYRAINSHOWERS_NIGHT = "HEAVYRAINSHOWERS_NIGHT"
    LIGHTRAIN = "LIGHTRAIN"
    RAIN = "RAIN"
    HEAVYRAIN = "HEAVYRAIN"
    THUNDERSTORM = "THUNDERSTORM"
    THUNDER = "THUNDER"
    RAINANDTHUNDER = "RAINANDTHUNDER"
    HEAVYRAINANDTHUNDER = "HEAVYRAINANDTHUNDER"
    LIGHTSNOW = "LIGHTSNOW"
    SNOW = "SNOW"
    HEAVYSNOW = "HEAVYSNOW"
    LIGHTSNOWSHOWERS_DAY = "LIGHTSNOWSHOWERS_DAY"
    LIGHTSNOWSHOWERS_NIGHT = "LIGHTSNOWSHOWERS_NIGHT"
    SNOWSHOWERS_DAY = "SNOWSHOWERS_DAY"
    SNOWSHOWERS_NIGHT = "SNOWSHOWERS_NIGHT"
    HEAVYSNOWSHOWERS_DAY = "HEAVYSNOWSHOWERS_DAY"
    HEAVYSNOWSHOWERS_NIGHT = "HEAVYSNOWSHOWERS_NIGHT"
    LIGHTSLEET = "LIGHTSLEET"
    SLEET = "SLEET"
    HEAVYSLEET = "HEAVYSLEET"
    FOG = "FOG"

    @property
    def thunder_probability(self) -> float:
        """Get thunder probability based on weather code."""
        if self in (WeatherCode.THUNDERSTORM, WeatherCode.HEAVYRAINANDTHUNDER):
            return 0.8
        elif self in (WeatherCode.THUNDER, WeatherCode.RAINANDTHUNDER):
            return 0.5
        return 0.0

    @property
    def description(self) -> str:
        """Get human-readable description of the weather code."""
        return {
            WeatherCode.UNKNOWN: "Unknown",
            WeatherCode.CLEARSKY_DAY: "Clear sky",
            WeatherCode.CLEARSKY_NIGHT: "Clear sky",
            WeatherCode.FAIR_DAY: "Fair",
            WeatherCode.FAIR_NIGHT: "Fair",
            WeatherCode.PARTLYCLOUDY_DAY: "Partly cloudy",
            WeatherCode.PARTLYCLOUDY_NIGHT: "Partly cloudy",
            WeatherCode.CLOUDY: "Cloudy",
            WeatherCode.RAINSHOWERS_DAY: "Rain showers",
            WeatherCode.RAINSHOWERS_NIGHT: "Rain showers",
            WeatherCode.LIGHTRAINSHOWERS_DAY: "Light rain showers",
            WeatherCode.LIGHTRAINSHOWERS_NIGHT: "Light rain showers",
            WeatherCode.HEAVYRAINSHOWERS_DAY: "Heavy rain showers",
            WeatherCode.HEAVYRAINSHOWERS_NIGHT: "Heavy rain showers",
            WeatherCode.LIGHTRAIN: "Light rain",
            WeatherCode.RAIN: "Rain",
            WeatherCode.HEAVYRAIN: "Heavy rain",
            WeatherCode.THUNDERSTORM: "Thunderstorm",
            WeatherCode.THUNDER: "Thunder",
            WeatherCode.RAINANDTHUNDER: "Rain and thunder",
            WeatherCode.HEAVYRAINANDTHUNDER: "Heavy rain and thunder",
            WeatherCode.LIGHTSNOW: "Light snow",
            WeatherCode.SNOW: "Snow",
            WeatherCode.HEAVYSNOW: "Heavy snow",
            WeatherCode.LIGHTSNOWSHOWERS_DAY: "Light snow showers",
            WeatherCode.LIGHTSNOWSHOWERS_NIGHT: "Light snow showers",
            WeatherCode.SNOWSHOWERS_DAY: "Snow showers",
            WeatherCode.SNOWSHOWERS_NIGHT: "Snow showers",
            WeatherCode.HEAVYSNOWSHOWERS_DAY: "Heavy snow showers",
            WeatherCode.HEAVYSNOWSHOWERS_NIGHT: "Heavy snow showers",
            WeatherCode.LIGHTSLEET: "Light sleet",
            WeatherCode.SLEET: "Sleet",
            WeatherCode.HEAVYSLEET: "Heavy sleet",
            WeatherCode.FOG: "Fog"
        }[self]

    def __str__(self) -> str:
        """Return string representation of weather code."""
        return self.value

def get_weather_symbol(symbol_code: str) -> str:
    """Map weather symbol codes to emojis."""
    # Convert to lowercase for case-insensitive matching
    code = symbol_code.lower()
    
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
        
        # Thunder
        'thunder': '⛈️',
        'thunderstorm': '⛈️',
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
    return emoji_map.get(code, '☁️')  # Default to cloudy if code not found

@dataclass
class Location:
    """Location data container."""
    id: str
    name: str
    latitude: float
    longitude: float
    altitude: float | None = None
    region: str | None = None
    country: str | None = None
    timezone: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
    """Weather data class."""
    temperature: float  # Celsius
    precipitation: float  # mm/h
    precipitation_probability: float  # 0-100%
    wind_speed: float  # m/s
    wind_direction: float  # Degrees (0-360)
    weather_code: WeatherCode  # Internal weather code
    time: datetime  # UTC
    thunder_probability: float = 0.0  # 0-100%
    block_duration: timedelta = field(default_factory=lambda: timedelta(hours=1))  # Forecast block duration
    humidity: float = 0.0  # 0-100%
    cloud_cover: float = 0.0  # 0-100%

    def __post_init__(self) -> None:
        """Validate the weather data."""
        if not isinstance(self.time, datetime):
            raise ValueError("time must be a datetime object")
        if not isinstance(self.block_duration, timedelta):
            raise ValueError("block_duration must be a timedelta object")
        if not isinstance(self.weather_code, WeatherCode):
            raise ValueError("weather_code must be a WeatherCode enum value")
        
        # Ensure numeric fields are floats
        self.temperature = float(self.temperature)
        self.precipitation = float(self.precipitation)
        self.precipitation_probability = float(self.precipitation_probability)
        self.wind_speed = float(self.wind_speed)
        self.wind_direction = float(self.wind_direction)
        self.thunder_probability = float(self.thunder_probability)
        self.humidity = float(self.humidity)
        self.cloud_cover = float(self.cloud_cover)

        # Validate ranges
        if not (0 <= self.precipitation_probability <= 100):
            raise ValueError("precipitation_probability must be between 0 and 100")
        if not (0 <= self.thunder_probability <= 100):
            raise ValueError("thunder_probability must be between 0 and 100")
        if not (0 <= self.wind_direction <= 360):
            raise ValueError("wind_direction must be between 0 and 360")
        if not (0 <= self.humidity <= 100):
            raise ValueError("humidity must be between 0 and 100")
        if not (0 <= self.cloud_cover <= 100):
            raise ValueError("cloud_cover must be between 0 and 100")
        if self.wind_speed < 0:
            raise ValueError("wind_speed cannot be negative")
        if self.precipitation < 0:
            raise ValueError("precipitation cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'temperature': self.temperature,
            'precipitation': self.precipitation,
            'precipitation_probability': self.precipitation_probability,
            'wind_speed': self.wind_speed,
            'wind_direction': self.wind_direction,
            'weather_code': self.weather_code.value,
            'time': self.time.isoformat(),
            'thunder_probability': self.thunder_probability,
            'block_duration': self.block_duration.total_seconds(),
            'humidity': self.humidity,
            'cloud_cover': self.cloud_cover
        }

T = TypeVar('T', bound='WeatherData')

@dataclass
class WeatherResponse:
    """Weather response data class."""
    data: list[WeatherData]
    elaboration_time: datetime
    expires: datetime | None = None

    def __post_init__(self) -> None:
        """Validate the response data."""
        # Convert single WeatherData to list
        if isinstance(self.data, WeatherData):
            self.data = [self.data]
        elif not isinstance(self.data, list):
            raise ValueError("data must be WeatherData or List[WeatherData]")
            
        # Validate all items are WeatherData
        if not all(isinstance(item, WeatherData) for item in self.data):
            raise ValueError("All items in data must be WeatherData objects")
            
        # Validate elaboration_time
        if not isinstance(self.elaboration_time, datetime):
            raise ValueError("elaboration_time must be a datetime object")
            
        # Validate expires if provided
        if self.expires is not None and not isinstance(self.expires, datetime):
            raise ValueError("expires must be a datetime object if provided")

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[WeatherData]:
        return iter(self.data)

    def __getitem__(self, idx: int) -> WeatherData:
        return self.data[idx]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'data': [d.to_dict() for d in self.data],
            'elaboration_time': self.elaboration_time.isoformat(),
            'expires': self.expires.isoformat() if self.expires else None
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'WeatherResponse':
        """Create WeatherResponse from dictionary.
        
        Args:
            data: Dictionary containing weather response data
            
        Returns:
            WeatherResponse object
        """
        weather_data = []
        for item in data['data']:
            # Convert block_duration from seconds back to timedelta
            block_duration = timedelta(seconds=item['block_duration'])
            # Parse time from ISO format and ensure UTC
            time = datetime.fromisoformat(item['time'])
            if not time.tzinfo:
                time = time.replace(tzinfo=UTC)
            elif time.tzinfo != UTC:
                time = time.astimezone(UTC)
            
            # Create WeatherData object
            weather_data.append(WeatherData(
                temperature=item['temperature'],
                precipitation=item['precipitation'],
                precipitation_probability=item['precipitation_probability'],
                wind_speed=item['wind_speed'],
                wind_direction=item['wind_direction'],
                weather_code=WeatherCode(item['weather_code']),
                time=time,  # Now guaranteed to be in UTC
                thunder_probability=item.get('thunder_probability', 0.0),
                block_duration=block_duration,
                humidity=item.get('humidity', 0.0),
                cloud_cover=item.get('cloud_cover', 0.0)
            ))
        
        # Parse elaboration_time from ISO format and ensure UTC
        elaboration_time = datetime.fromisoformat(data['elaboration_time'])
        if not elaboration_time.tzinfo:
            elaboration_time = elaboration_time.replace(tzinfo=UTC)
        elif elaboration_time.tzinfo != UTC:
            elaboration_time = elaboration_time.astimezone(UTC)
        
        # Parse expires if present and ensure UTC
        expires = None
        if data.get('expires'):
            expires = datetime.fromisoformat(data['expires'])
            if not expires.tzinfo:
                expires = expires.replace(tzinfo=UTC)
            elif expires.tzinfo != UTC:
                expires = expires.astimezone(UTC)
        
        return cls(
            data=weather_data,
            elaboration_time=elaboration_time,
            expires=expires
        )

    def __str__(self) -> str:
        return f"WeatherResponse(data={self.data}, elaboration_time={self.elaboration_time})"

def _handle_weather_error(error: Exception, service: str, operation: str) -> dict[str, Any]:
    """Handle weather service error and return details."""
    details = {
        "service": service,
        "operation": operation,
        "error_type": type(error).__name__,
        "traceback": ''.join(traceback.format_tb(error.__traceback__)) if error.__traceback__ else ""
    }
    
    if isinstance(error, requests.exceptions.RequestException):
        response = getattr(error, "response", None)
        request = getattr(error, "request", None)
        if response is not None:
            details["status_code"] = response.status_code
        if request is not None:
            details["url"] = request.url
    
    return details

class WeatherError(GolfCalError):
    """Base class for weather service errors."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, code=ErrorCode.WEATHER_ERROR, details=details)

class WeatherServiceError(WeatherError):
    """Error in weather service operation."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherParseError(WeatherError):
    """Error parsing weather data."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherValidationError(WeatherError):
    """Error validating weather data."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherServiceUnavailable(WeatherError):
    """Error raised when weather service is unavailable."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherServiceTimeout(WeatherError):
    """Error raised when weather service times out."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherServiceRateLimited(WeatherError):
    """Error raised when weather service rate limit is exceeded."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherServiceInvalidResponse(WeatherError):
    """Error raised when weather service returns invalid response."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherRequestError(WeatherError):
    """Error raised when weather request fails."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherTimeoutError(WeatherError):
    """Error raised when weather request times out."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherAuthError(WeatherError):
    """Error raised when weather service authentication fails."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

class WeatherLocationError(WeatherError):
    """Error raised when location data is invalid or missing."""
    def __init__(self, message: str, service: str = "", operation: str = "", details: dict[str, Any] | None = None) -> None:
        details = details or {}
        details.update({
            "service": service,
            "operation": operation
        })
        super().__init__(message=message, service=service, operation=operation, details=details)

@handle_errors(GolfCalError, service="weather", operation="base")
class WeatherService(ABC):
    """Base class for weather services."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: dict[str, Any] | None = None) -> None:
        """Initialize weather service.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Optional configuration dictionary
        """
        self.local_tz = local_tz
        self.utc_tz = utc_tz
        self.config = config or {}

    def get_weather(self, latitude: float, longitude: float, start_time: datetime, end_time: datetime) -> WeatherResponse | None:
        """Get weather data for a location and time range.
        
        Args:
            latitude: The latitude of the location
            longitude: The longitude of the location
            start_time: The start time of the forecast
            end_time: The end time of the forecast
        
        Returns:
            WeatherResponse object containing the weather data, or None if no data is available
            
        Raises:
            WeatherError: If weather service fails
        """
        try:
            response_data = self._fetch_forecasts(latitude, longitude, start_time, end_time)
            if response_data is None:
                return None
            return self._parse_response(response_data)
        except Exception as e:
            self._handle_errors(ErrorCode.WEATHER_ERROR, str(e))
            return None

    @abstractmethod
    def _fetch_forecasts(self, latitude: float, longitude: float, start_time: datetime, end_time: datetime) -> dict[str, Any] | None:
        """Fetch forecasts from the weather service.
        
        Args:
            latitude: The latitude of the location
            longitude: The longitude of the location
            start_time: The start time of the forecast
            end_time: The end time of the forecast
        
        Returns:
            Dictionary containing the forecast data, or None if no data is available
            
        Raises:
            WeatherError: If weather service fails
        """
        pass

    @abstractmethod
    def _parse_response(self, response_data: dict[str, Any]) -> WeatherResponse | None:
        """Parse the response from the weather service.
        
        Args:
            response_data: The response data from the weather service
        
        Returns:
            WeatherResponse object containing the weather data, or None if no data is available
            
        Raises:
            WeatherParseError: If response parsing fails
        """
        pass

    def get_expiry_time(self) -> datetime:
        """Get expiry time for weather data.
        
        Returns:
            Datetime when the weather data expires
        """
        return datetime.now(self.utc_tz) + timedelta(hours=1)

    def _create_response(self, data: WeatherData | list[WeatherData], elaboration_time: datetime, expires: datetime | None = None) -> WeatherResponse:
        """Create a weather response object.
        
        Args:
            data: The weather data to include in the response
            elaboration_time: The time the forecast was elaborated
            expires: Optional expiration time for the forecast
        
        Returns:
            WeatherResponse object containing the weather data
            
        Raises:
            WeatherValidationError: If data validation fails
        """
        try:
            return WeatherResponse(
                data=data if isinstance(data, list) else [data],
                elaboration_time=elaboration_time,
                expires=expires or self.get_expiry_time()
            )
        except ValueError as e:
            raise WeatherValidationError(str(e))

    def _handle_errors(self, error_code: ErrorCode, message: str, traceback: str | None = None) -> None:
        """Handle errors in weather service.
        
        Args:
            error_code: The error code to use
            message: The error message
            traceback: Optional traceback information
        """
        aggregate_error(str(error_code), message, traceback)

def handle_weather_error(error: Exception, service: str, operation: str) -> None:
    """Handle weather service error."""
    details = _handle_weather_error(error, service, operation)
    if isinstance(error, WeatherError):
        raise error
    raise WeatherServiceError(str(error), service, operation, details) 