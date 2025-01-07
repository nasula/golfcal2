"""Weather service data types."""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from golfcal2.utils.logging_utils import EnhancedLoggerMixin, log_execution

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
class WeatherData:
    """Weather data container."""
    temperature: float
    precipitation: float
    precipitation_probability: Optional[float]
    wind_speed: float
    wind_direction: Optional[str]
    symbol: str
    elaboration_time: datetime
    thunder_probability: Optional[float] = None

@dataclass
class WeatherResponse:
    """Weather response container with data and expiry time."""
    data: List[WeatherData]
    expires: datetime

class WeatherService(EnhancedLoggerMixin):
    """Base class for weather services."""
    
    def __init__(self, local_tz, utc_tz):
        """Initialize service."""
        super().__init__()
        self.local_tz = local_tz
        self.utc_tz = utc_tz
    
    def get_expiry_time(self) -> datetime:
        """Get expiry time for current weather data.
        
        Each service should implement this based on their update schedule.
        Default implementation is 1 hour from now.
        """
        return datetime.now(self.utc_tz) + timedelta(hours=1)
    
    @log_execution(level='DEBUG')
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> WeatherResponse:
        """Get weather data for location and time range.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time
            end_time: End time
            
        Returns:
            WeatherResponse with data and expiry time
        """
        data = self._fetch_forecasts(lat, lon, start_time, end_time)
        return WeatherResponse(data=data, expires=self.get_expiry_time())

    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch forecasts from weather service."""
        raise NotImplementedError("Subclasses must implement _fetch_forecasts")

    def get_block_size(self, hours_ahead: float) -> int:
        """Get the block size in hours for grouping forecasts based on how far ahead they are.
        
        Args:
            hours_ahead: Number of hours ahead of current time the forecast is for.
            
        Returns:
            int: Block size in hours (e.g., 1 for hourly forecasts, 6 for 6-hour blocks).
        """
        raise NotImplementedError("Subclasses must implement get_block_size") 