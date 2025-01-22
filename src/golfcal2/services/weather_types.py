"""Weather service types and base classes."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Union, Iterator
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
    elaboration_time: Optional[datetime] = None
    temperature: Optional[Union[float, str]] = None
    precipitation: Optional[Union[float, str]] = None
    precipitation_probability: Optional[Union[float, str]] = None
    wind_speed: Optional[Union[float, str]] = None
    wind_direction: Optional[Union[float, str]] = None
    weather_code: Optional[Union[WeatherCode, str]] = None
    weather_description: str = ''  # Human-readable description
    thunder_probability: Optional[Union[float, str]] = None
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    symbol_time_range: Optional[str] = None  # For 6h blocks, shows time range like "18:00 to 24:00"

    def __post_init__(self) -> None:
        """Convert string values to appropriate types."""
        self.temperature = self._convert_to_float(self.temperature)
        self.precipitation = self._convert_to_float(self.precipitation)
        self.precipitation_probability = self._convert_to_float(self.precipitation_probability)
        self.wind_speed = self._convert_to_float(self.wind_speed)
        self.wind_direction = self._convert_to_float(self.wind_direction, default=0.0)
        if isinstance(self.weather_code, str):
            try:
                self.weather_code = WeatherCode[self.weather_code]
            except (KeyError, ValueError):
                self.weather_code = WeatherCode.UNKNOWN
        self.thunder_probability = self._convert_to_float(self.thunder_probability)
        
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
        """Get the weather symbol."""
        if isinstance(self.weather_code, str):
            return self.weather_code
        if self.weather_code is None:
            return WeatherCode.UNKNOWN.value
        return self.weather_code.value

    def __str__(self) -> str:
        """Return string representation of weather data."""
        time_str = self.elaboration_time.isoformat() if self.elaboration_time else "unknown"
        return (
            f"WeatherData("
            f"time={time_str}, "
            f"temp={self.temperature}°C, "
            f"precip={self.precipitation}mm, "
            f"wind={self.wind_speed}m/s@{self.wind_direction}°"
            f")"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'elaboration_time': self.elaboration_time.isoformat() if self.elaboration_time else None,
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
            'metadata': self.metadata,
            'symbol_time_range': self.symbol_time_range
        }

@dataclass
class WeatherResponse:
    """Container for weather response data."""
    elaboration_time: datetime
    data: Union[WeatherData, List[WeatherData]]
    expires: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def forecasts(self) -> List[WeatherData]:
        """Get forecasts as a list for backward compatibility."""
        if isinstance(self.data, list):
            return self.data
        return [self.data]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'elaboration_time': self.elaboration_time.isoformat(),
            'expires': self.expires.isoformat() if self.expires else None,
            'data': [d.to_dict() for d in self.forecasts],
            'metadata': self.metadata
        }

class WeatherError(GolfCalError):
    """Base class for weather service errors."""

    def __init__(self, message: str, error_code: ErrorCode) -> None:
        """Initialize error with message and code."""
        super().__init__(message, code=error_code)
        self.error_code = error_code

class WeatherServiceUnavailable(WeatherError):
    """Error raised when weather service is unavailable."""

class WeatherDataError(WeatherError):
    """Error raised when there is an issue with weather data."""

class APIResponseError(WeatherError):
    """Error raised when there is an issue with API response."""

    def __init__(self, message: str, error_code: ErrorCode, response: requests.Response) -> None:
        """Initialize error with message, code and response."""
        super().__init__(message, error_code)
        self.response = response 

@handle_errors(GolfCalError, service="weather", operation="base")
class WeatherService:
    """Base class for weather services."""

    def __init__(self, utc: ZoneInfo, config: Dict[str, Any]) -> None:
        """Initialize weather service.
        
        Args:
            utc: UTC timezone
            config: Service configuration
        """
        self.utc = utc
        self.config = config

    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data for given location and time range.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time
            end_time: End time
            club: Optional club name for caching
            
        Returns:
            Weather data response or None if not available
        """
        raise NotImplementedError

    def _parse_response(self, response: requests.Response) -> Optional[WeatherResponse]:
        """Parse weather service response.
        
        Args:
            response: Response from weather service
            
        Returns:
            Parsed weather data or None if parsing failed
        """
        raise NotImplementedError

    def _create_response(
        self,
        data: Union[WeatherData, List[WeatherData]],
        elaboration_time: datetime,
        expires: Optional[datetime] = None
    ) -> WeatherResponse:
        """Create weather response with proper data handling.
        
        Args:
            data: Weather data or list of weather data
            elaboration_time: Time when data was elaborated
            expires: Optional expiry time
            
        Returns:
            Weather response
        """
        if expires is None:
            expires = elaboration_time + timedelta(hours=1)
            
        if isinstance(data, list):
            return WeatherResponse(
                elaboration_time=elaboration_time,
                data=data
            )
        else:
            return WeatherResponse(
                elaboration_time=elaboration_time,
                data=[data]
            ) 