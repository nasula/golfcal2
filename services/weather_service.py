"""Weather service implementation."""

import os
import json
import time
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import requests

from golfcal2.utils.logging_utils import EnhancedLoggerMixin, log_execution
from golfcal2.services.weather_types import WeatherService, WeatherData, get_weather_symbol
from golfcal2.services.mediterranean_weather_service import MediterraneanWeatherService
from golfcal2.services.iberian_weather_service import IberianWeatherService
from golfcal2.services.met_weather_service import MetWeatherService
from golfcal2.services.portuguese_weather_service import PortugueseWeatherService
from golfcal2.exceptions import (
    WeatherError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error

class WeatherManager(EnhancedLoggerMixin):
    """Weather service manager."""
    
    def __init__(self, local_tz, utc_tz, config):
        """Initialize weather services.
        
        Args:
            local_tz: Local timezone object
            utc_tz: UTC timezone object
            config: Application configuration
        """
        super().__init__()
        
        with handle_errors(WeatherError, "weather", "initialize services"):
            # Store timezone settings
            self.local_tz = local_tz
            self.utc_tz = utc_tz
            
            # Initialize services
            self.services = {
                'mediterranean': MediterraneanWeatherService(local_tz, utc_tz, config),
                'iberian': IberianWeatherService(local_tz, utc_tz, config),
                'met': MetWeatherService(local_tz, utc_tz, config),
                'portuguese': PortugueseWeatherService(local_tz, utc_tz, config)
            }
            
            # Define service regions
            self.regions = {
                'norway': {
                    'service': 'met',
                    'bounds': (57.0, 71.5, 4.0, 31.5)  # lat_min, lat_max, lon_min, lon_max
                },
                'mediterranean': {
                    'service': 'mediterranean',
                    'bounds': (35.0, 45.0, 20.0, 45.0)
                },
                'portugal': {
                    'service': 'portuguese',  # Using PortugueseWeatherService
                    'bounds': (36.5, 42.5, -9.5, -7.5)  # Mainland Portugal
                },
                'spain_mainland': {
                    'service': 'iberian',
                    'bounds': (36.0, 44.0, -7.5, 3.5)  # Mainland Spain (AEMET)
                },
                'spain_canary': {
                    'service': 'iberian',
                    'bounds': (27.5, 29.5, -18.5, -13.0)  # Canary Islands (AEMET)
                }
            }
            
            # Remove club-specific mappings as we'll use coordinates only
            self.set_correlation_id()  # Generate unique ID for this manager instance
    
    @log_execution(level='DEBUG')
    def get_weather(
        self, 
        club: str, 
        teetime: datetime, 
        coordinates: Dict[str, float], 
        duration_minutes: Optional[int] = None
    ) -> Optional[str]:
        """Get weather data for a specific time and location."""
        with handle_errors(
            WeatherError,
            "weather",
            f"get weather for club {club}",
            lambda: None  # Fallback to None on error
        ):
            lat = coordinates.get('lat')
            lon = coordinates.get('lon')
            
            if lat is None or lon is None:
                error = WeatherError(
                    "Missing coordinates for weather lookup",
                    ErrorCode.MISSING_DATA,
                    {"club": club, "coordinates": coordinates}
                )
                aggregate_error(str(error), "weather", None)
                return None

            # Skip past dates
            if teetime < datetime.now(self.utc_tz):
                self.debug(f"Weather: Skipping past date {teetime}")
                return None

            # Skip dates more than 10 days in future
            if teetime > datetime.now(self.utc_tz) + timedelta(days=10):
                self.debug(f"Weather: Skipping future date {teetime}")
                return None

            # Calculate end time based on duration
            end_time = teetime + timedelta(minutes=duration_minutes if duration_minutes else 240)

            # Select appropriate weather service based on location
            weather_service = self._get_service_for_location(lat, lon, club)
            if not weather_service:
                error = WeatherError(
                    f"No weather service available for location",
                    ErrorCode.SERVICE_UNAVAILABLE,
                    {
                        "club": club,
                        "latitude": lat,
                        "longitude": lon
                    }
                )
                aggregate_error(str(error), "weather", None)
                return None

            # Get weather data
            weather_data = weather_service.get_weather(lat, lon, teetime, end_time)
            if not weather_data:
                error = WeatherError(
                    f"Failed to get weather data",
                    ErrorCode.SERVICE_ERROR,
                    {
                        "club": club,
                        "latitude": lat,
                        "longitude": lon,
                        "teetime": teetime.isoformat()
                    }
                )
                aggregate_error(str(error), "weather", None)
                return None

            # Format weather data
            return self._format_weather_data(weather_data)
    
    def _format_weather_data(self, weather_data: List[WeatherData]) -> str:
        """Format weather data into a human-readable string."""
        with handle_errors(
            WeatherError,
            "weather",
            "format weather data",
            lambda: ""  # Fallback to empty string on error
        ):
            if not weather_data:
                return ""
            
            lines = []
            for data in weather_data:
                time_str = data.elaboration_time.strftime("%H:%M")
                symbol = get_weather_symbol(data.symbol)
                temp = f"{data.temperature:.1f}°C"
                wind = f"{data.wind_speed:.1f}m/s"
                
                # Add precipitation probability
                precip = ""
                if data.precipitation_probability is not None or data.precipitation > 0:
                    prob = data.precipitation_probability or (data.precipitation * 100 if data.precipitation else 0)
                    precip = f" 💧{prob:.1f}%"
                
                # Add thunder probability if present
                thunder = ""
                if data.thunder_probability and data.thunder_probability > 0:
                    thunder = f" ⚡{data.thunder_probability:.1f}%"
                
                lines.append(f"{time_str} {symbol} {temp} {wind}{precip}{thunder}")
            
            return "\n".join(lines)
    
    @log_execution(level='DEBUG')
    def _get_service_for_location(self, lat: float, lon: float, club: Optional[str] = None) -> Optional[WeatherService]:
        """Get appropriate weather service for location."""
        with handle_errors(
            WeatherError,
            "weather",
            f"get service for location (lat={lat}, lon={lon})",
            lambda: None  # Fallback to None on error
        ):
            service_name = None
            
            # Select service based on coordinates
            for region, config in self.regions.items():
                lat_min, lat_max, lon_min, lon_max = config['bounds']
                if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                    self.debug(
                        "Found matching region",
                        region=region,
                        service=config['service'],
                        coordinates=f"({lat}, {lon})"
                    )
                    service_name = config['service']
                    break
            
            # Default to MET service as fallback
            if not service_name:
                self.info(
                    "No specific region found, using MET service as fallback",
                    latitude=lat,
                    longitude=lon
                )
                service_name = 'met'
            
            # Return the actual service instance
            service = self.services.get(service_name)
            if not service:
                error = WeatherError(
                    f"Weather service '{service_name}' not found",
                    ErrorCode.SERVICE_UNAVAILABLE,
                    {
                        "service": service_name,
                        "latitude": lat,
                        "longitude": lon
                    }
                )
                aggregate_error(str(error), "weather", None)
                return None
            
            return service
    
    def _apply_rate_limit(self) -> None:
        """Apply rate limiting."""
        if self._last_api_call:
            elapsed = datetime.now() - self._last_api_call
            if elapsed < self._min_call_interval:
                sleep_time = (self._min_call_interval - elapsed).total_seconds()
                self.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                time.sleep(sleep_time)
        self._last_api_call = datetime.now()