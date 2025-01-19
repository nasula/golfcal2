"""Weather service types and base classes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
import requests

from golfcal2.exceptions import ErrorCode

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
        'heavysnowshowersandthunder_night': '⛈️'
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
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize optional fields after dataclass creation."""
        self.metadata = self.metadata or {}

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
    """Weather data container."""
    elaboration_time: datetime
    block_duration: timedelta
    temperature: float
    precipitation: float
    precipitation_probability: float
    wind_speed: float
    wind_direction: float
    weather_code: str  # Internal weather code (e.g., 'clearsky_day')
    weather_description: str = ''  # Human-readable description
    thunder_probability: float = 0.0
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    symbol_time_range: Optional[str] = None  # For 6h blocks, shows time range like "18:00 to 24:00"

    def __post_init__(self):
        """Initialize optional fields after dataclass creation."""
        self.temperature_min = self.temperature_min or self.temperature
        self.temperature_max = self.temperature_max or self.temperature
        self.metadata = self.metadata or {}

    @property
    def symbol(self) -> str:
        """Alias for weather_code to maintain backward compatibility."""
        return self.weather_code

    @symbol.setter
    def symbol(self, value: str):
        """Set weather_code through symbol property."""
        self.weather_code = value

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
        """Convert weather data to dictionary for JSON serialization."""
        return {
            "time": self.elaboration_time.isoformat(),
            "duration": str(self.block_duration),
            "temperature": self.temperature,
            "temperature_min": self.temperature_min,
            "temperature_max": self.temperature_max,
            "precipitation": self.precipitation,
            "precipitation_probability": self.precipitation_probability,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "weather_code": self.weather_code,
            "weather_description": self.weather_description,
            "thunder_probability": self.thunder_probability,
            "symbol_time_range": self.symbol_time_range,
            "metadata": self.metadata
        }

@dataclass
class WeatherResponse:
    """Weather response container with data and expiry time."""
    data: List[WeatherData]
    expires: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert weather response to dictionary for JSON serialization."""
        return {
            "data": [d.to_dict() for d in self.data],
            "expires": self.expires.isoformat()
        }

class WeatherError(Exception):
    """Base class for weather service errors."""
    def __init__(self, message: str, error_code: ErrorCode):
        super().__init__(message)
        self.error_code = error_code

class WeatherServiceUnavailable(WeatherError):
    """Error indicating that a weather service is unavailable."""
    pass

class WeatherDataError(WeatherError):
    """Error indicating invalid or missing weather data."""
    pass

class APIResponseError(WeatherError):
    """Error indicating an invalid API response."""
    def __init__(self, message: str, error_code: ErrorCode, response: requests.Response):
        super().__init__(message, error_code)
        self.response = response 