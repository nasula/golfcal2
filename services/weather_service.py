"""Weather service base class and manager."""

from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import math

import pytz

from golfcal.utils.logging_utils import LoggerMixin

class WeatherCode(str, Enum):
    """Standard weather codes used across all weather services."""
    CLEAR_DAY = 'clearsky_day'
    CLEAR_NIGHT = 'clearsky_night'
    FAIR_DAY = 'fair_day'
    FAIR_NIGHT = 'fair_night'
    PARTLY_CLOUDY_DAY = 'partlycloudy_day'
    PARTLY_CLOUDY_NIGHT = 'partlycloudy_night'
    CLOUDY = 'cloudy'
    FOG = 'fog'
    RAIN = 'rain'
    LIGHT_RAIN = 'lightrain'
    HEAVY_RAIN = 'heavyrain'
    LIGHT_SLEET = 'lightsleet'
    HEAVY_SLEET = 'heavysleet'
    LIGHT_SNOW = 'lightsnow'
    HEAVY_SNOW = 'heavysnow'
    SNOW = 'snow'
    RAIN_SHOWERS_DAY = 'rainshowers_day'
    RAIN_SHOWERS_NIGHT = 'rainshowers_night'
    HEAVY_RAIN_SHOWERS_DAY = 'heavyrainshowers_day'
    HEAVY_RAIN_SHOWERS_NIGHT = 'heavyrainshowers_night'
    LIGHT_RAIN_SHOWERS_DAY = 'lightrainshowers_day'
    LIGHT_RAIN_SHOWERS_NIGHT = 'lightrainshowers_night'
    RAIN_AND_THUNDER = 'rainandthunder'
    HEAVY_RAIN_AND_THUNDER = 'heavyrainandthunder'

def get_weather_symbol(symbol_code: str) -> str:
    """Map weather symbol codes to emojis."""
    emoji_map = {
        'clearsky_day': '🌞', 'clearsky_night': '🌙',
        'fair_day': '🌤️', 'fair_night': '🌙',
        'partlycloudy_day': '⛅', 'partlycloudy_night': '🌤️',
        'cloudy': '☁️',
        'fog': '🌫️',
        'rain': '🌧️', 'lightrain': '🌦️',
        'heavyrain': '🌧️', 'lightsleet': '🌨️',
        'heavysleet': '🌨️🌧️', 'lightsnow': '🌨️',
        'heavysnow': '🌨️', 'snow': '🌨️',
        'rainshowers_day': '🌦️', 'rainshowers_night': '🌧️',
        'heavyrainshowers_day': '🌧️', 'heavyrainshowers_night': '🌧️',
        'heavysleetshowers_day': '🌨️🌧️', 'heavysleetshowers_night': '🌨️🌧️',
        'heavysnowshowers_day': '🌨️', 'heavysnowshowers_night': '🌨️',
        'lightrainshowers_day': '🌦️', 'lightrainshowers_night': '🌦️',
        'lightsleetshowers_day': '🌨️', 'lightsleetshowers_night': '🌨️',
        'lightsnowshowers_day': '🌨️', 'lightsnowshowers_night': '🌨️',
        'rainandthunder': '⛈️', 'heavyrainandthunder': '⛈️'
    }
    return emoji_map.get(symbol_code, '☁️')  # Default to cloudy if code not found

class WeatherService:
    """Base class for weather services."""

    def __init__(self):
        """Initialize the weather service."""
        pass

    def get_weather(self, lat: float, lon: float, date: datetime, duration_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get weather data for given coordinates and date.
        
        Args:
            lat: Latitude
            lon: Longitude
            date: Date for which to get the weather (in local time)
            duration_minutes: Optional duration of the event in minutes
            
        Returns:
            Dictionary containing weather data with standardized keys:
            - symbol_code: WeatherCode enum value for weather symbol
            - air_temperature: Temperature in Celsius
            - precipitation_amount: Precipitation amount in mm
            - wind_speed: Wind speed in m/s
            - wind_from_direction: Wind direction in degrees (0-360)
            - probability_of_precipitation: Probability of rain (0-100)
            - probability_of_thunder: Probability of thunder (0-100)
        """
        try:
            # Convert date to UTC for API request
            utc_date = date.astimezone(pytz.UTC)
            self.logger.debug(f"Converting time from {date} to UTC: {utc_date}")
            
            # Get time blocks based on how far in the future the date is
            interval, event_blocks = self.get_time_blocks(utc_date, duration_minutes)
            self.logger.debug(f"Event blocks for {utc_date}: {event_blocks} (interval: {interval}h)")
            
            # Calculate times to fetch
            times_to_fetch = []
            event_date = utc_date.date()
            for block_start, block_end in event_blocks:
                # Create datetime for this block
                block_time = datetime.combine(event_date, datetime.min.time(), tzinfo=utc_date.tzinfo)
                block_time = block_time.replace(hour=block_start)
                times_to_fetch.append(block_time.strftime('%Y-%m-%dT%H:%M:%SZ'))
            
            self.logger.debug(f"Fetching weather for times: {times_to_fetch}")
            
            # Try to get data from database first
            db_data = self._get_from_db(lat, lon, times_to_fetch, interval)
            if db_data:
                self.logger.debug("Found valid weather data in database")
                return db_data
            
            # If not in database or expired, fetch from API
            self.logger.debug("No valid data in database, fetching from API")
            weather_data = self._fetch_weather_data(lat, lon, times_to_fetch, interval)
            if not weather_data:
                return None
            
            # Store the new data in database
            self._store_in_db(weather_data)
            
            # Get the first available weather data point
            for time_str in times_to_fetch:
                if time_str in weather_data:
                    return weather_data[time_str]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get weather data: {e}", exc_info=True)
            return None

    def _fetch_weather_data(self, lat: float, lon: float, times: List[str], interval: int) -> Dict[str, Dict[str, Any]]:
        """Fetch weather data from the service.
        
        This method should be implemented by each weather service to handle their specific API.
        The returned data should use the standardized field names.
        """
        raise NotImplementedError

    def format_weather(self, weather: Dict[str, Any]) -> str:
        """Format weather data into a string representation."""
        if 'forecasts' not in weather:
            return self._format_single_forecast(weather)
        
        # Group forecasts by time block
        time_blocks = {}
        for forecast in weather['forecasts']:
            hour = forecast['time'].hour
            if forecast['data_type'] == 'next_6_hours':
                # For 6-hour blocks, group by block start
                block_start = (hour // 6) * 6
                block_end = block_start + 6
                key = f"{block_start:02d}:00-{block_end:02d}:00"
            elif forecast['data_type'] == 'next_3_hours':
                # For 3-hour blocks, group by block start
                block_start = (hour // 3) * 3
                block_end = block_start + 3
                key = f"{block_start:02d}:00-{block_end:02d}:00"
            else:
                # For hourly forecasts, use the hour
                key = f"{hour:02d}:00"
            time_blocks[key] = forecast
        
        # Format each time block
        formatted_blocks = []
        for time_str, forecast in sorted(time_blocks.items()):
            formatted_blocks.append(f"{time_str} {self._format_single_forecast(forecast)}")
        
        # Join with newlines
        return '\n'.join(formatted_blocks)
    
    def _format_single_forecast(self, weather: Dict[str, Any]) -> str:
        """Format a single weather forecast."""
        symbol = get_weather_symbol(weather['symbol_code'])
        temp = f"{weather['air_temperature']}°C"
        wind = f"{weather['wind_speed']}m/s"
        
        # Add wind direction if available
        if 'wind_from_direction' in weather:
            wind = f"{wind} {self._get_wind_direction(weather['wind_from_direction'])}"
        
        # Add rain amount and probability if available
        rain_info = ""
        if 'precipitation_amount' in weather and weather['precipitation_amount'] > 0:
            rain_info = f"💧{weather['precipitation_amount']}mm"
        elif 'probability_of_precipitation' in weather and weather['probability_of_precipitation'] > 0:
            rain_info = f"💧{weather['probability_of_precipitation']}%"
        
        # Add thunder probability if available
        thunder_prob = ""
        if 'probability_of_thunder' in weather and weather['probability_of_thunder'] > 0:
            thunder_prob = f"⚡{weather['probability_of_thunder']}%"
        
        return f"{symbol} {temp} {wind}{rain_info}{thunder_prob}"

    def _get_wind_direction(self, degrees: Optional[float]) -> str:
        """Convert wind direction from degrees to cardinal direction."""
        if degrees is None:
            return 'N'  # Default to North if no direction is provided
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / 45) % 8
        return directions[index]

    def get_time_blocks(self, date: datetime, duration_minutes: Optional[int] = None) -> Tuple[int, List[Tuple[int, int]]]:
        """Get time blocks for weather data based on how far in the future the date is.
        
        Args:
            date: Date for which to get the weather (in UTC)
            duration_minutes: Optional duration of the event in minutes
            
        Returns:
            Tuple of (interval_hours, list of (start_hour, end_hour) tuples)
        """
        # Calculate hours ahead
        now = datetime.now(date.tzinfo)
        hours_ahead = math.ceil((date - now).total_seconds() / 3600)
        
        # Determine forecast type based on hours ahead
        # 0-48 hours: hourly data
        # >48 hours: 6-hourly data
        interval = 1 if hours_ahead <= 48 else 6
        
        # Calculate event duration
        event_duration = duration_minutes or 180  # Default to 3 hours
        event_hours = math.ceil(event_duration / 60)
        
        # Calculate start and end hours
        start_hour = date.hour
        end_hour = (start_hour + event_hours)
        
        # For 6-hour blocks, round to nearest block
        if interval == 6:
            start_block = (start_hour // 6) * 6
            end_block = ((end_hour + 5) // 6) * 6
            blocks = [(h, min(h + 6, 24)) for h in range(start_block, end_block, 6)]
        else:
            blocks = [(h, h + 1) for h in range(start_hour, min(end_hour, 24))]
        
        self.logger.debug(f"Time blocks for {date} (interval: {interval}h): {blocks}")
        return interval, blocks

    def _get_from_db(self, lat: float, lon: float, times: List[str], interval: int) -> Optional[Dict[str, Any]]:
        """Try to get weather data from database."""
        raise NotImplementedError

    def _store_in_db(self, weather_data: Dict[str, Dict[str, Any]]) -> None:
        """Store weather data in database."""
        raise NotImplementedError

# Import specific services after base class definition to avoid circular imports
from golfcal.services.met_weather_service import MetWeatherService
from golfcal.services.iberian_weather_service import IberianWeatherService
from golfcal.services.mediterranean_weather_service import MediterraneanWeatherService

class WeatherManager(LoggerMixin):
    """Manager for handling weather data from different services."""

    def __init__(self, local_tz, utc_tz):
        """Initialize weather services."""
        super().__init__()
        self.local_tz = local_tz
        self.utc_tz = utc_tz
        self.met_service = MetWeatherService()
        self.iberian_service = IberianWeatherService(local_tz, utc_tz)
        self.mediterranean_service = MediterraneanWeatherService(local_tz, utc_tz)

    def get_weather(
        self, 
        club: str, 
        teetime: datetime, 
        coordinates: Dict[str, float], 
        duration_minutes: Optional[int] = None
    ) -> Optional[str]:
        """Get weather data for a specific time and location."""
        try:
            lat = coordinates['lat']
            lon = coordinates['lon']

            # Skip past dates
            if teetime < datetime.now(self.utc_tz):
                self.logger.debug(f"Weather: Skipping past date {teetime}")
                return None

            # Skip dates more than 10 days in future
            if teetime > datetime.now(self.utc_tz) + timedelta(days=10):
                self.logger.debug(f"Weather: Skipping future date {teetime}")
                return None

            # Select appropriate weather service based on location
            weather_service = self._get_service_for_location(lat, lon)
            if not weather_service:
                return None

            # Get weather data
            weather_data = weather_service.get_weather(lat, lon, teetime, duration_minutes)
            if not weather_data:
                return None

            # Format weather data
            return weather_service.format_weather(weather_data)

        except Exception as e:
            self.logger.error(f"Weather: Failed to get weather for {club}: {e}", exc_info=True)
            return None

    def _get_service_for_location(self, lat: float, lon: float):
        """Get appropriate weather service for given coordinates."""
        # Mediterranean region (Turkey and Greece)
        if (35.0 <= lat <= 42.0) and (19.0 <= lon <= 45.0):
            return self.mediterranean_service

        # Iberian region (Portugal and Spain)
        if (36.0 <= lat <= 43.8) and (-9.5 <= lon <= 3.3):
            return self.iberian_service

        # Default to MET.no for other locations
        return self.met_service