"""Portuguese weather service implementation using IPMA API.

Source: Instituto Português do Mar e da Atmosfera (IPMA)
API Documentation: https://api.ipma.pt
"""

import os
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
import math
from datetime import timezone
import logging

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherCode, WeatherResponse
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_schemas import PORTUGUESE_SCHEMA
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.utils.logging_utils import log_execution, EnhancedLoggerMixin, get_logger
from golfcal2.exceptions import (
    WeatherError,
    APIError,
    APITimeoutError,
    APIRateLimitError,
    APIResponseError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.config.types import AppConfig

""" References:
https://api.ipma.pt/
 """

logger = logging.getLogger(__name__)

class PortugueseWeatherService(WeatherService):
    """Service for handling weather data for Portugal using IPMA API.
    
    The IPMA API provides daily forecasts for Portuguese cities and islands.
    Data is updated twice daily at 10:00 and 20:00 UTC.
    """

    BASE_URL = "https://api.ipma.pt/open-data"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal2 (jarkko.ahonen@iki.fi)"
    
    def __init__(self, timezone: ZoneInfo, utc: ZoneInfo, config: Dict[str, Any]):
        """Initialize service."""
        super().__init__(timezone, utc)
        self.config = config
        self.set_log_context(service="portuguese_weather")
        
        # Configure logger
        for handler in self.logger.handlers:
            handler.set_name('portuguese_weather')  # Ensure unique handler names
        self.logger.propagate = True  # Allow logs to propagate to root logger
        
        # Test debug call to verify logger name mapping
        self.debug(">>> TEST DEBUG: PortugueseWeatherService initialized", logger_name=self.logger.name)
        
        with handle_errors(WeatherError, "portuguese_weather", "initialize service"):
            # Configure API endpoint and headers
            self.endpoint = self.BASE_URL
            self.headers = {
                'Accept': 'application/json',
                'User-Agent': self.USER_AGENT
            }
            
            # Initialize database and cache
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
            os.makedirs(data_dir, exist_ok=True)
            self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
            self.location_cache = WeatherLocationCache(os.path.join(data_dir, 'weather_locations.db'))
            
            # Rate limiting configuration
            self._last_api_call = None
            self._min_call_interval = timedelta(seconds=1)
            self._last_request_time = 0

    def get_block_size(self, hours_ahead: float) -> int:
        """Get the block size in hours for grouping forecasts.
        
        IPMA provides daily forecasts, so we always return 24 hours.
        
        Args:
            hours_ahead: Number of hours ahead of current time
            
        Returns:
            int: Block size in hours (24 for daily forecasts)
        """
        return 24  # IPMA provides daily forecasts

    def get_expiry_time(self) -> datetime:
        """Get expiry time for IPMA weather data.
        
        IPMA updates their forecasts twice daily at 10:00 and 22:00 UTC.
        """
        now = datetime.now(self.utc_tz)
        
        # Calculate next update time
        if now.hour < 10:
            next_update = now.replace(hour=10, minute=0, second=0, microsecond=0)
        elif now.hour < 22:
            next_update = now.replace(hour=22, minute=0, second=0, microsecond=0)
        else:
            next_update = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        
        return next_update

    def _init_location_cache(self):
        """Initialize location cache with data from IPMA API."""
        try:
            # Get locations from API
            locations_url = f"{self.BASE_URL}/distrits-islands.json"
            response = requests.get(locations_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list):
                    locations = []
                    for loc in data:
                        try:
                            location = {
                                'id': str(loc['globalIdLocal']),
                                'name': loc['local'],
                                'latitude': float(loc['latitude']),
                                'longitude': float(loc['longitude']),
                                'metadata': {
                                    'region': loc.get('idRegiao'),
                                    'district': loc.get('idDistrito'),
                                    'municipality': loc.get('idConcelho'),
                                    'warning_area': loc.get('idAreaAviso')
                                }
                            }
                            locations.append(location)
                        except (KeyError, ValueError) as e:
                            self.warning(
                                "Failed to parse location data",
                                exc_info=e,
                                data=loc
                            )
                            continue
                    
                    if locations:
                        self.location_cache.store_location_set(
                            service_type='ipma',
                            set_type='municipalities',
                            data=locations,
                            expires_in=timedelta(days=30)
                        )
                        self.debug(f"Stored {len(locations)} locations in cache")
                    else:
                        self.error("Empty municipality list received from IPMA")
                else:
                    self.error(
                        "Failed to get municipality list",
                        status=response.status_code
                    )
            else:
                self.error(
                    "Failed to get municipality list",
                    status=response.status_code
                )
        except requests.RequestException as e:
            self.error("Failed to fetch locations from IPMA API", exc_info=e)
        except Exception as e:
            self.error("Error initializing location cache", exc_info=e)

    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from IPMA API."""
        try:
            # Initialize location cache if needed
            self._init_location_cache()
            
            # Get nearest location from cache
            location = self.location_cache.get_nearest_location('ipma', lat, lon)
            if not location:
                self.warning(
                    "No location found in cache",
                    latitude=lat,
                    longitude=lon
                )
                return None

            # Get forecast data
            forecast_url = f"{self.BASE_URL}/forecast/meteorology/cities/daily/{location['id']}.json"
            self.debug(
                "Getting forecast data",
                url=forecast_url,
                location_id=location['id'],
                location_name=location['name'],
                distance_km=location['distance']
            )
            
            # Respect rate limits
            if self._last_api_call:
                time_since_last = datetime.now() - self._last_api_call
                if time_since_last < self._min_call_interval:
                    sleep_time = (self._min_call_interval - time_since_last).total_seconds()
                    self.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
            
            forecast_response = requests.get(
                forecast_url,
                headers=self.headers,
                timeout=10
            )
            
            self._last_api_call = datetime.now()
            
            self.debug(
                "Got forecast response",
                status=forecast_response.status_code,
                content_type=forecast_response.headers.get('content-type'),
                content_length=len(forecast_response.content)
            )
            
            if forecast_response.status_code != 200:
                error = APIResponseError(
                    f"IPMA forecast request failed with status {forecast_response.status_code}",
                    response=forecast_response
                )
                aggregate_error(str(error), "portuguese_weather", None)
                return None

            forecast_data = forecast_response.json()
            if not forecast_data or 'data' not in forecast_data:
                error = WeatherError(
                    "Invalid forecast data format from IPMA API",
                    ErrorCode.INVALID_RESPONSE,
                    {"response": forecast_data}
                )
                aggregate_error(str(error), "portuguese_weather", None)
                return None

            self.debug(
                "Received forecast data",
                data=json.dumps(forecast_data, indent=2),
                data_type=type(forecast_data).__name__,
                has_data=bool(forecast_data.get('data')),
                data_length=len(forecast_data.get('data', [])),
                first_period=forecast_data.get('data', [{}])[0] if forecast_data.get('data') else None
            )

            return forecast_data

        except Exception as e:
            self.error("Error fetching forecasts", exc_info=e)
            return None

    def _wind_class_to_speed(self, wind_class: int) -> float:
        """Convert IPMA wind speed class to m/s.
        
        Classes:
        1 - Weak (< 15 km/h)
        2 - Moderate (15-35 km/h)
        3 - Strong (35-55 km/h)
        4 - Very strong (> 55 km/h)
        """
        class_speeds = {
            1: 2.8,   # 10 km/h
            2: 6.9,   # 25 km/h
            3: 12.5,  # 45 km/h
            4: 18.1   # 65 km/h
        }
        return class_speeds.get(wind_class, 0.0)

    def _map_ipma_code(self, code: int, hour: int) -> str:
        """Map IPMA weather codes to our internal codes.
        
        IPMA codes from API documentation:
        0 - No information
        1 - Clear sky
        2 - Partly cloudy
        3 - Cloudy
        4 - Overcast
        5 - Light rain showers
        6 - Rain showers and thunder
        7 - Heavy rain and thunder
        8 - Snow showers
        9 - Thunder
        10 - Heavy rain
        11 - Heavy snow
        12 - Light rain
        13 - Light snow
        14 - Rain and snow
        15 - Fog
        16 - Heavy fog
        17 - Frost
        18 - High clouds
        """
        with handle_errors(
            WeatherError,
            "portuguese_weather",
            f"map weather code {code}",
            lambda: WeatherCode.CLOUDY  # Fallback to cloudy on error
        ):
            is_day = 6 <= hour <= 20
            
            code_map = {
                # Clear and cloudy conditions
                0: 'cloudy',  # Default for no information
                1: 'clearsky_day' if is_day else 'clearsky_night',
                2: 'partlycloudy_day' if is_day else 'partlycloudy_night',
                3: 'cloudy',
                4: 'cloudy',
                18: 'partlycloudy_day' if is_day else 'partlycloudy_night',
                
                # Rain
                5: 'lightrainshowers_day' if is_day else 'lightrainshowers_night',
                10: 'heavyrain',
                12: 'lightrain',
                
                # Thunder
                6: 'rainshowersandthunder_day' if is_day else 'rainshowersandthunder_night',
                7: 'heavyrainandthunder',
                9: 'thunder',
                
                # Snow
                8: 'snowshowers_day' if is_day else 'snowshowers_night',
                11: 'heavysnow',
                13: 'lightsnow',
                
                # Mixed
                14: 'sleet',
                
                # Other
                15: 'fog',
                16: 'fog',
                17: 'clearsky_day' if is_day else 'clearsky_night'  # Frost shown with clear sky
            }
            
            return code_map.get(code, 'cloudy')  # Default to cloudy if code not found

    def _get_wind_direction(self, direction: Optional[str]) -> Optional[str]:
        """Convert wind direction to cardinal direction.
        
        Handles both degree values and cardinal directions from IPMA and AEMET.
        Also handles Spanish/Portuguese abbreviations:
        - N (Norte/North)
        - NE (Nordeste/Northeast)
        - E (Este/East)
        - SE (Sudeste/Southeast)
        - S (Sur/South)
        - SO/SW (Sudoeste/Southwest)
        - O/W (Oeste/West)
        - NO/NW (Noroeste/Northwest)
        """
        if direction is None:
            return None
        
        # Map of Spanish/Portuguese abbreviations to standard cardinal directions
        direction_map = {
            'N': 'N',
            'NE': 'NE',
            'E': 'E',
            'SE': 'SE',
            'S': 'S',
            'SO': 'SW',
            'O': 'W',
            'NO': 'NW',
            'SW': 'SW',
            'W': 'W',
            'NW': 'NW'
        }
        
        # If it's a known direction abbreviation, map it
        if isinstance(direction, str):
            direction = direction.upper()
            if direction in direction_map:
                return direction_map[direction]
        
        # Try to convert from degrees
        try:
            degrees = float(direction)
            cardinal_directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
            index = round(degrees / 45) % 8
            return cardinal_directions[index]
        except (ValueError, TypeError):
            self.warning(f"Could not parse wind direction: {direction}")
            return None

    def _convert_cached_data(self, cached_data: Dict[str, Dict[str, Any]]) -> List[WeatherData]:
        """Convert cached data to WeatherData objects."""
        try:
            self.debug("Converting cached data to WeatherData objects")
            forecasts = []
            
            for time_str, data in cached_data.items():
                try:
                    # Parse ISO format time
                    time = datetime.fromisoformat(time_str)
                    
                    forecast = WeatherData(
                        temperature=data['air_temperature'],
                        precipitation=data['precipitation_amount'],
                        precipitation_probability=data['probability_of_precipitation'],
                        wind_speed=data['wind_speed'],
                        wind_direction=data['wind_from_direction'],
                        symbol=data['summary_code'],
                        elaboration_time=time,
                        thunder_probability=data['probability_of_thunder'],
                        block_duration=timedelta(hours=24)  # IPMA provides daily forecasts
                    )
                    forecasts.append(forecast)
                except Exception as e:
                    self.warning(
                        "Failed to convert cached forecast",
                        error=str(e),
                        data=data
                    )
                    continue
            
            self.debug(f"Converted {len(forecasts)} cached forecasts")
            return sorted(forecasts, key=lambda x: x.elaboration_time)
        except Exception as e:
            self.error("Failed to convert cached data", error=str(e))
            return []

    @log_execution(level='DEBUG', include_args=True)
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: str = None
    ) -> Optional[List[WeatherData]]:
        """Get weather data from IPMA."""
        try:
            # Calculate time range for fetching data
            now = datetime.now(self.utc_tz)
            hours_ahead = (end_time - now).total_seconds() / 3600
            interval = self.get_block_size(hours_ahead)
            
            # Align start and end times to block boundaries
            base_time = start_time.replace(minute=0, second=0, microsecond=0)
            fetch_end_time = end_time.replace(minute=0, second=0, microsecond=0)
            if end_time.minute > 0 or end_time.second > 0:
                fetch_end_time += timedelta(hours=1)
            
            self.debug(
                "Using forecast interval",
                hours_ahead=hours_ahead,
                interval=interval,
                aligned_start=base_time.isoformat(),
                aligned_end=fetch_end_time.isoformat()
            )
            
            # Check cache for response
            cached_response = self.cache.get_response(
                service_type='ipma',
                latitude=lat,
                longitude=lon,
                start_time=base_time,
                end_time=fetch_end_time
            )
            
            if cached_response:
                self.info(
                    "Using cached response",
                    location=cached_response['location'],
                    time_range=f"{base_time.isoformat()} to {fetch_end_time.isoformat()}",
                    interval=interval
                )
                return self._parse_response(cached_response['response'], base_time, fetch_end_time, interval)
            
            # If not in cache, fetch from API
            self.info(
                "Fetching new data from API",
                coords=(lat, lon),
                time_range=f"{base_time.isoformat()} to {fetch_end_time.isoformat()}",
                interval=interval
            )
            
            # Fetch data for the full forecast range
            response_data = self._fetch_forecasts(lat, lon, base_time, fetch_end_time)
            if not response_data:
                self.warning("No forecasts found for requested time range")
                return None
            
            # Store the full response in cache
            self.cache.store_response(
                service_type='ipma',
                latitude=lat,
                longitude=lon,
                response_data=response_data,
                forecast_start=base_time,
                forecast_end=fetch_end_time,
                expires=datetime.now(self.utc_tz) + timedelta(hours=1)
            )
            
            # Parse and return just the requested time range
            return self._parse_response(response_data, base_time, fetch_end_time, interval)
            
        except Exception as e:
            self.error("Failed to get weather data", exc_info=e)
            return None

    def _log_cache_status(self, location: str, cached_data: Optional[Dict], expected_count: int) -> None:
        """Log cache hit/miss status at INFO level.
        
        Args:
            location: Location string (lat,lon)
            cached_data: The cached data if any
            expected_count: Number of time blocks we expected
        """
        if cached_data and len(cached_data) == expected_count:
            self.info("Cache hit", location=location, block_count=len(cached_data))
        else:
            self.info(
                "Cache miss",
                location=location,
                cached_count=len(cached_data) if cached_data else 0,
                expected_count=expected_count
            )

    def _get_forecast(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
        interval: str,
        data_type: str
    ) -> Optional[WeatherResponse]:
        """Get weather forecast for the given location and time range."""
        try:
            # Check cache first
            cached_response = self.cache.get_response(
                service_type='portuguese',
                latitude=latitude,
                longitude=longitude,
                start_time=start_time,
                end_time=end_time
            )
            
            if cached_response:
                self.info(
                    "Cache hit for Portuguese forecast",
                    latitude=latitude,
                    longitude=longitude,
                    start_time=start_time,
                    end_time=end_time
                )
                forecasts = self._parse_forecast_data(cached_response['response'], start_time, end_time)
                if forecasts:
                    return WeatherResponse(
                        forecasts=forecasts,
                        expires=datetime.fromisoformat(cached_response['response']['dataUpdate'])
                    )
            
            self.info(
                "Cache miss for Portuguese forecast",
                latitude=latitude,
                longitude=longitude,
                start_time=start_time,
                end_time=end_time
            )
            
            # Fetch new data
            raw_response = self._fetch_forecasts(latitude, longitude, start_time, end_time)
            if not raw_response:
                return None
                
            # Parse the raw response
            forecasts = self._parse_forecast_data(raw_response, start_time, end_time)
            if not forecasts:
                return None
                
            # Store in cache
            self.cache.store_response(
                service_type='portuguese',
                latitude=latitude,
                longitude=longitude,
                response_data=raw_response,
                forecast_start=start_time,
                forecast_end=end_time,
                expires=datetime.now(self.utc) + timedelta(hours=6)
            )
            
            return WeatherResponse(
                forecasts=forecasts,
                expires=datetime.now(self.utc) + timedelta(hours=6)
            )

        except Exception as e:
            self.error("Failed to get Portuguese forecast", error=str(e))
            return None

    def _parse_forecast_data(
        self,
        forecast_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime
    ) -> List[WeatherData]:
        """Parse forecast data into WeatherData objects."""
        forecasts = []
        for period in forecast_data.get('data', []):
            with handle_errors(WeatherError, "portuguese_weather", "process forecast period"):
                try:
                    # Parse forecast date (YYYY-MM-DD format)
                    forecast_date = datetime.strptime(
                        period.get('forecastDate', ''),
                        '%Y-%m-%d'
                    ).replace(tzinfo=self.local_tz)
                    
                    # Skip if not the date we want
                    if forecast_date.date() != start_time.date():
                        continue
                        
                except ValueError as e:
                    self.warning(
                        "Failed to parse forecast date",
                        date=period.get('forecastDate'),
                        error=str(e),
                        period_data=period
                    )
                    continue
                
                # Skip if outside our time range
                if forecast_date < start_time.replace(hour=0, minute=0, second=0, microsecond=0):
                    continue
                
                # Extract weather data
                try:
                    tmin = float(period.get('tMin', 0))
                    tmax = float(period.get('tMax', 0))
                    
                    # Calculate hourly temperatures using a simple sine curve
                    # Minimum at 6 AM, maximum at 2 PM
                    min_hour = 6
                    max_hour = 14
                    
                    precip_prob = float(period.get('precipitaProb', 0))
                    # Convert probability to amount (simple estimation)
                    precip = precip_prob / 100.0 if precip_prob > 0 else 0
                    
                    # Wind speed class to m/s conversion
                    wind_class = int(period.get('classWindSpeed', 0))
                    wind_speed = self._wind_class_to_speed(wind_class)
                    
                    wind_dir = period.get('predWindDir')
                    weather_type = int(period.get('idWeatherType', 0))
                    
                    # Generate hourly forecasts for the time range
                    for hour in range(24):
                        forecast_time = forecast_date.replace(hour=hour)
                        
                        # Skip if outside our time range
                        if forecast_time < start_time or forecast_time > end_time:
                            continue
                        
                        # Calculate temperature for this hour using sine curve
                        hour_progress = (hour - min_hour) % 24
                        day_progress = hour_progress / 24.0
                        temp_range = tmax - tmin
                        if min_hour <= hour <= max_hour:
                            # Rising temperature
                            progress = (hour - min_hour) / (max_hour - min_hour)
                            temp = tmin + temp_range * math.sin(progress * math.pi / 2)
                        else:
                            # Falling temperature
                            if hour > max_hour:
                                progress = (hour - max_hour) / (24 + min_hour - max_hour)
                            else:  # hour < min_hour
                                progress = (hour + 24 - max_hour) / (24 + min_hour - max_hour)
                            temp = tmax - temp_range * math.sin(progress * math.pi / 2)
                        
                        self.debug(
                            "Calculated hourly values",
                            hour=hour,
                            temp=temp,
                            base_temp_min=tmin,
                            base_temp_max=tmax,
                            precip=precip,
                            wind_speed=wind_speed
                        )
                        
                        # Map weather type to symbol
                        try:
                            symbol_code = self._map_ipma_code(weather_type, hour)
                        except Exception as e:
                            self.warning(
                                "Failed to map weather code",
                                code=weather_type,
                                hour=hour,
                                error=str(e)
                            )
                            continue

                        # Calculate thunder probability based on weather type
                        thunder_prob = 0.0
                        if weather_type in [6, 7, 9]:  # Thunder types in IPMA codes
                            thunder_prob = 50.0

                        forecast = WeatherData(
                            temperature=temp,
                            precipitation=precip,
                            precipitation_probability=precip_prob,
                            wind_speed=wind_speed,
                            wind_direction=self._get_wind_direction(wind_dir),
                            symbol=symbol_code,
                            elaboration_time=forecast_time,
                            thunder_probability=thunder_prob,
                            block_duration=timedelta(hours=24)  # IPMA provides daily forecasts
                        )
                        forecasts.append(forecast)
                        
                        self.debug(
                            "Added hourly forecast",
                            time=forecast_time.isoformat(),
                            temp=temp,
                            precip=precip,
                            wind=wind_speed,
                            symbol=symbol_code
                        )
                        
                except (ValueError, TypeError) as e:
                    self.warning(
                        "Failed to parse forecast values",
                        error=str(e),
                        data=period,
                        raw_values={
                            'tMin': period.get('tMin'),
                            'tMax': period.get('tMax'),
                            'precipitaProb': period.get('precipitaProb'),
                            'classWindSpeed': period.get('classWindSpeed'),
                            'predWindDir': period.get('predWindDir'),
                            'idWeatherType': period.get('idWeatherType')
                        }
                    )
                    continue

        self.debug(
            "Completed forecast processing",
            total_forecasts=len(forecasts),
            time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
        )
        return forecasts

    def _parse_response(
        self,
        response_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        interval: int
    ) -> Optional[WeatherResponse]:
        """Parse API response into WeatherResponse object."""
        try:
            forecasts = []
            
            # Process each forecast period
            for period in response_data.get('data', []):
                try:
                    # Parse forecast date (YYYY-MM-DD format)
                    forecast_date = datetime.strptime(
                        period.get('forecastDate', ''),
                        '%Y-%m-%d'
                    ).replace(tzinfo=self.local_tz)
                    
                    # Skip if not the date we want
                    if forecast_date.date() != start_time.date():
                        continue
                        
                except ValueError as e:
                    self.warning(
                        "Failed to parse forecast date",
                        date=period.get('forecastDate'),
                        error=str(e),
                        period_data=period
                    )
                    continue
                
                # Skip if outside our time range
                if forecast_date < start_time.replace(hour=0, minute=0, second=0, microsecond=0):
                    continue
                
                # Extract weather data
                try:
                    tmin = float(period.get('tMin', 0))
                    tmax = float(period.get('tMax', 0))
                    
                    # Calculate hourly temperatures using a simple sine curve
                    # Minimum at 6 AM, maximum at 2 PM
                    min_hour = 6
                    max_hour = 14
                    
                    precip_prob = float(period.get('precipitaProb', 0))
                    # Convert probability to amount (simple estimation)
                    precip = precip_prob / 100.0 if precip_prob > 0 else 0
                    
                    # Wind speed class to m/s conversion
                    wind_class = int(period.get('classWindSpeed', 0))
                    wind_speed = self._wind_class_to_speed(wind_class)
                    
                    wind_dir = period.get('predWindDir')
                    weather_type = int(period.get('idWeatherType', 0))
                    
                    # Generate hourly forecasts for the time range
                    for hour in range(24):
                        forecast_time = forecast_date.replace(hour=hour)
                        
                        # Skip if outside our time range
                        if forecast_time < start_time or forecast_time > end_time:
                            continue
                        
                        # Calculate temperature for this hour using sine curve
                        hour_progress = (hour - min_hour) % 24
                        day_progress = hour_progress / 24.0
                        temp_range = tmax - tmin
                        if min_hour <= hour <= max_hour:
                            # Rising temperature
                            progress = (hour - min_hour) / (max_hour - min_hour)
                            temp = tmin + temp_range * math.sin(progress * math.pi / 2)
                        else:
                            # Falling temperature
                            if hour > max_hour:
                                progress = (hour - max_hour) / (24 + min_hour - max_hour)
                            else:  # hour < min_hour
                                progress = (hour + 24 - max_hour) / (24 + min_hour - max_hour)
                            temp = tmax - temp_range * math.sin(progress * math.pi / 2)
                        
                        self.debug(
                            "Calculated hourly values",
                            hour=hour,
                            temp=temp,
                            base_temp_min=tmin,
                            base_temp_max=tmax,
                            precip=precip,
                            wind_speed=wind_speed
                        )
                        
                        # Map weather type to symbol
                        try:
                            symbol_code = self._map_ipma_code(weather_type, hour)
                        except Exception as e:
                            self.warning(
                                "Failed to map weather code",
                                code=weather_type,
                                hour=hour,
                                error=str(e)
                            )
                            continue

                        # Calculate thunder probability based on weather type
                        thunder_prob = 0.0
                        if weather_type in [6, 7, 9]:  # Thunder types in IPMA codes
                            thunder_prob = 50.0

                        forecast = WeatherData(
                            temperature=temp,
                            precipitation=precip,
                            precipitation_probability=precip_prob,
                            wind_speed=wind_speed,
                            wind_direction=self._get_wind_direction(wind_dir),
                            symbol=symbol_code,
                            elaboration_time=forecast_time,
                            thunder_probability=thunder_prob,
                            block_duration=timedelta(hours=interval)
                        )
                        forecasts.append(forecast)
                        
                        self.debug(
                            "Added hourly forecast",
                            time=forecast_time.isoformat(),
                            temp=temp,
                            precip=precip,
                            wind=wind_speed,
                            symbol=symbol_code
                        )
                        
                except (ValueError, TypeError) as e:
                    self.warning(
                        "Failed to parse forecast values",
                        error=str(e),
                        data=period,
                        raw_values={
                            'tMin': period.get('tMin'),
                            'tMax': period.get('tMax'),
                            'precipitaProb': period.get('precipitaProb'),
                            'classWindSpeed': period.get('classWindSpeed'),
                            'predWindDir': period.get('predWindDir'),
                            'idWeatherType': period.get('idWeatherType')
                        }
                    )
                    continue

            self.debug(
                "Completed forecast processing",
                total_forecasts=len(forecasts),
                time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
            )
            
            if not forecasts:
                self.warning("No forecasts found in response for requested time range")
                return None
            
            # Sort forecasts by time
            forecasts.sort(key=lambda x: x.elaboration_time)
            
            return WeatherResponse(data=forecasts, expires=self.get_expiry_time())
            
        except Exception as e:
            self.error("Error parsing weather response", error=str(e))
            return None
