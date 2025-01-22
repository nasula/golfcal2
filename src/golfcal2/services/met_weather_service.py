"""
Weather service implementation for Norwegian Meteorological Institute (MET).
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, cast, Iterator
from zoneinfo import ZoneInfo

import requests

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.services.weather_types import WeatherData, WeatherResponse, WeatherCode
from golfcal2.utils.logging_utils import get_logger

class MetWeatherService(WeatherService):
    """Weather service implementation for Norwegian Meteorological Institute (MET)."""

    service_type: str = "met"
    HOURLY_RANGE: int = 48  # 2 days of hourly forecasts
    SIX_HOURLY_RANGE: int = 216  # 9 days of 6-hourly forecasts
    MAX_FORECAST_RANGE: int = 216  # 9 days * 24 hours

    def __init__(self, timezone: Union[str, ZoneInfo], utc: Union[str, ZoneInfo], config: Dict[str, Any]) -> None:
        """Initialize the service.
        
        Args:
            timezone: Local timezone
            utc: UTC timezone
            config: Service configuration
        """
        super().__init__(timezone, utc)
        self.config = config
        self.set_log_context(service="met_weather")

    def _get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data from MET.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecast
            end_time: End time for forecast
            club: Optional club identifier for caching
            
        Returns:
            Optional[WeatherResponse]: Weather data if available
        """
        try:
            # Check if request is beyond maximum forecast range
            now_utc = datetime.now(self.utc_tz)
            hours_ahead = (end_time - now_utc).total_seconds() / 3600
            
            if hours_ahead > self.MAX_FORECAST_RANGE:
                self.warning(
                    "Request beyond maximum forecast range",
                    max_range_hours=self.MAX_FORECAST_RANGE,
                    requested_hours=hours_ahead,
                    end_time=end_time.isoformat()
                )
                return None

            # Determine forecast interval based on time range
            interval = self.get_block_size(hours_ahead)
            
            # Fetch and parse forecast data
            response_data = self._fetch_forecasts(lat, lon, start_time, end_time)
            if not response_data:
                return None
                
            weather_data = self._parse_response(response_data, start_time, end_time, interval)
            if not weather_data:
                return None
                
            return WeatherResponse(
                elaboration_time=now_utc,
                data=weather_data
            )
            
        except Exception as e:
            self.error("Failed to get weather data from MET", exc_info=e)
            return None

    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from MET API.
        
        Args:
            lat: Latitude
            lon: Longitude
            start_time: Start time for forecast
            end_time: End time for forecast
            
        Returns:
            Optional[Dict[str, Any]]: Raw forecast data if successful
        """
        try:
            # Build API URL
            base_url = self.config.get('api_url', 'https://api.met.no/weatherapi/locationforecast/2.0/complete')
            user_agent = self.config.get('user_agent', 'GolfCal2/1.0')
            
            # Make request
            headers = {'User-Agent': user_agent}
            params = {'lat': lat, 'lon': lon}
            
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            
            return cast(Dict[str, Any], response.json())
            
        except Exception as e:
            self.error("Failed to fetch forecast data from MET", exc_info=e)
            return None

    def _parse_response(
        self,
        response_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        interval: int
    ) -> Optional[List[WeatherData]]:
        """Parse response data into weather data objects.
        
        Args:
            response_data: Raw response data from MET API
            start_time: Start time for forecast
            end_time: End time for forecast
            interval: Time interval in hours
            
        Returns:
            Optional[List[WeatherData]]: List of weather data objects if parsing successful
        """
        try:
            timeseries = response_data.get('properties', {}).get('timeseries', [])
            if not timeseries:
                self.warning("No timeseries data in response")
                return None
                
            weather_data: List[WeatherData] = []
            
            # For 6-hour blocks, align start and end times to block boundaries
            if interval > 1:
                # Convert to UTC for block alignment
                start_utc = start_time.astimezone(self.utc_tz)
                end_utc = end_time.astimezone(self.utc_tz)
                
                # Find the previous and next block boundaries
                start_block = (start_utc.hour // 6) * 6
                end_block = ((end_utc.hour + 5) // 6) * 6
                
                # Adjust start and end times to block boundaries
                aligned_start = start_utc.replace(hour=start_block, minute=0, second=0, microsecond=0)
                if end_block == 24:
                    aligned_end = (end_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    aligned_end = end_utc.replace(hour=end_block, minute=0, second=0, microsecond=0)
                    
                self.debug(
                    "Aligned time boundaries",
                    original_start=start_time.isoformat(),
                    original_end=end_time.isoformat(),
                    aligned_start=aligned_start.isoformat(),
                    aligned_end=aligned_end.isoformat()
                )
            else:
                aligned_start = start_time
                aligned_end = end_time
            
            for timepoint in timeseries:
                time_str = timepoint.get('time')
                if not time_str:
                    continue
                    
                time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                
                # Use aligned times for filtering when using 6-hour blocks
                if interval > 1:
                    if time < aligned_start or time > aligned_end:
                        continue
                else:
                    if time < start_time or time > end_time:
                        continue
                    
                instant = timepoint.get('data', {}).get('instant', {}).get('details', {})
                if not instant:
                    continue

                # Use appropriate forecast block based on interval
                if interval <= 1:
                    next_block = timepoint.get('data', {}).get('next_1_hours', {})
                else:
                    next_block = timepoint.get('data', {}).get('next_6_hours', {})
                    # Skip non-aligned 6-hour blocks
                    if time.hour % 6 != 0:
                        continue

                # Skip if we don't have the required forecast data
                if not next_block:
                    continue
                    
                # Create weather data object
                data = WeatherData(
                    elaboration_time=time,
                    temperature=float(instant.get('air_temperature', 0.0)),
                    precipitation=float(next_block.get('details', {}).get('precipitation_amount', 0.0)),
                    precipitation_probability=float(next_block.get('details', {}).get('probability_of_precipitation', 0.0)),
                    wind_speed=float(instant.get('wind_speed', 0.0)),
                    wind_direction=float(instant.get('wind_from_direction', 0.0)),
                    weather_code=self._map_symbol_code(next_block.get('summary', {}).get('symbol_code', 'cloudy')),
                    weather_description=str(next_block.get('summary', {}).get('symbol_code', '')),
                    thunder_probability=0.0,  # MET doesn't provide thunder probability
                    symbol_time_range=f"{time.hour:02d}:00-{((time.hour + interval) % 24):02d}:00"
                )
                weather_data.append(data)
                
            return weather_data if weather_data else None
            
        except Exception as e:
            self.error("Failed to parse MET response", exc_info=e)
            return None

    def _map_symbol_code(self, met_code: str) -> WeatherCode:
        """Map MET symbol codes to internal weather codes.
        
        Args:
            met_code: MET weather symbol code
            
        Returns:
            WeatherCode: Internal weather code
        """
        # Strip _day/_night suffix if present
        base_code = met_code.split('_')[0] if '_' in met_code else met_code
        
        # Map MET codes to internal codes
        code_map = {
            'clearsky': WeatherCode.CLEARSKY_DAY,
            'fair': WeatherCode.FAIR_DAY,
            'partlycloudy': WeatherCode.PARTLYCLOUDY_DAY,
            'cloudy': WeatherCode.CLOUDY,
            'fog': WeatherCode.FOG,
            'lightrainshowers': WeatherCode.LIGHTRAINSHOWERS_DAY,
            'rainshowers': WeatherCode.RAINSHOWERS_DAY,
            'heavyrainshowers': WeatherCode.HEAVYRAINSHOWERS_DAY,
            'lightrain': WeatherCode.LIGHTRAIN,
            'rain': WeatherCode.RAIN,
            'heavyrain': WeatherCode.HEAVYRAIN,
            'lightsleetshowers': WeatherCode.LIGHTSLEETSHOWERS_DAY,
            'sleetshowers': WeatherCode.SLEETSHOWERS_DAY,
            'heavysleetshowers': WeatherCode.HEAVYSLEETSHOWERS_DAY,
            'lightsleet': WeatherCode.LIGHTSLEET,
            'sleet': WeatherCode.SLEET,
            'heavysleet': WeatherCode.HEAVYSLEET,
            'lightsnowshowers': WeatherCode.LIGHTSNOWSHOWERS_DAY,
            'snowshowers': WeatherCode.SNOWSHOWERS_DAY,
            'heavysnowshowers': WeatherCode.HEAVYSNOWSHOWERS_DAY,
            'lightsnow': WeatherCode.LIGHTSNOW,
            'snow': WeatherCode.SNOW,
            'heavysnow': WeatherCode.HEAVYSNOW,
            'thunder': WeatherCode.THUNDER
        }
        
        return code_map.get(base_code, WeatherCode.CLOUDY)