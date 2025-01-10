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

from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherCode, WeatherResponse
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import PORTUGUESE_SCHEMA
from golfcal2.services.weather_cache import WeatherLocationCache
from golfcal2.utils.logging_utils import log_execution
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

class PortugueseWeatherService(WeatherService):
    """Service for handling weather data for Portugal using IPMA API.
    
    The IPMA API provides daily forecasts for Portuguese cities and islands.
    Data is updated twice daily at 10:00 and 20:00 UTC.
    """

    BASE_URL = "https://api.ipma.pt/open-data"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        """Initialize service.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Application configuration
        """
        super().__init__(local_tz, utc_tz)
        
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
            self.db = WeatherDatabase('portuguese_weather', PORTUGUESE_SCHEMA)
            self.cache = self.db  # Use database as cache
            self.location_cache = WeatherLocationCache(config)
            
            # Rate limiting configuration
            self._last_api_call = None
            self._min_call_interval = timedelta(seconds=1)
            self._last_request_time = 0
            
            self.set_log_context(service="PortugueseWeatherService")

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance between two points on the earth.
        
        Args:
            lat1: Latitude of first point in degrees
            lon1: Longitude of first point in degrees
            lat2: Latitude of second point in degrees
            lon2: Longitude of second point in degrees
            
        Returns:
            Distance between points in kilometers
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r
    
    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch forecasts from IPMA API."""
        with handle_errors(
            WeatherError,
            "portuguese_weather",
            f"fetch forecasts for coordinates ({lat}, {lon})",
            lambda: []  # Fallback to empty list on error
        ):
            # Ensure we have proper timezone objects
            if not isinstance(self.local_tz, ZoneInfo):
                self.warning(
                    "Invalid local timezone type",
                    expected="ZoneInfo",
                    actual=type(self.local_tz).__name__
                )
                local_tz = ZoneInfo("Europe/Lisbon")  # Fallback to default timezone
            else:
                local_tz = self.local_tz

            # Convert times to UTC for comparison
            start_time_utc = start_time.astimezone(timezone.utc)
            end_time_utc = end_time.astimezone(timezone.utc)
            
            try:
                # Use the timezone from start_time
                self.debug(f"Using timezone {local_tz} for coordinates ({lat}, {lon})")
                
                # First, try to get location from cache
                cached_location = self.location_cache.get_ipma_location(lat, lon)
                
                if cached_location:
                    self.debug(
                        "Found cached location",
                        name=cached_location['name'],
                        code=cached_location['code'],
                        distance_km=cached_location['distance']
                    )
                    location_id = cached_location['code']
                else:
                    # If not in cache, fetch from API
                    locations_url = f"{self.endpoint}/distrits-islands.json"
                    self.debug(
                        "Getting locations list",
                        url=locations_url,
                        headers=self.headers,
                        lat=lat,
                        lon=lon
                    )
                    
                    response = requests.get(
                        locations_url,
                        headers=self.headers,
                        timeout=10
                    )
                    
                    self.debug(
                        "Got locations response",
                        status=response.status_code,
                        content_type=response.headers.get('content-type'),
                        content_length=len(response.content)
                    )
                    
                    if response.status_code != 200:
                        error = APIResponseError(
                            f"IPMA locations request failed with status {response.status_code}",
                            response=response
                        )
                        aggregate_error(str(error), "portuguese_weather", None)
                        return []

                    locations = response.json()
                    self.debug(
                        "Parsed locations response",
                        type=type(locations).__name__,
                        count=len(locations.get('data', [])) if isinstance(locations, dict) else 0,
                        sample=str(locations)[:200] if locations else None
                    )
                    
                    # Get locations array from response
                    locations_data = locations.get('data', []) if isinstance(locations, dict) else []
                    if not locations_data:
                        self.warning("No locations data in response")
                        return []
                    
                    # Find nearest location
                    nearest_location = None
                    min_distance = float('inf')
                    processed = 0
                    
                    self.debug(
                        "Starting location search",
                        target_lat=lat,
                        target_lon=lon,
                        total_locations=len(locations_data)
                    )
                    
                    for location in locations_data:
                        try:
                            loc_lat = float(location.get('latitude', 0))
                            loc_lon = float(location.get('longitude', 0))
                            
                            distance = self._haversine_distance(lat, lon, loc_lat, loc_lon)
                            
                            self.debug(
                                "Checking location",
                                name=location.get('local', 'unknown'),
                                id=location.get('globalIdLocal', 'unknown'),
                                lat=loc_lat,
                                lon=loc_lon,
                                distance_km=distance
                            )
                            
                            if distance < min_distance:
                                min_distance = distance
                                nearest_location = location
                                self.debug(
                                    "Found closer location",
                                    name=location.get('local', 'unknown'),
                                    id=location.get('globalIdLocal', 'unknown'),
                                    distance_km=distance,
                                    location_lat=loc_lat,
                                    location_lon=loc_lon
                                )
                            
                            processed += 1
                            if processed % 10 == 0:  # Log progress every 10 locations
                                self.debug(f"Processed {processed} locations")
                                
                        except (ValueError, TypeError) as e:
                            self.warning(
                                "Failed to process location",
                                error=str(e),
                                location_data=location
                            )
                            continue

                    if not nearest_location:
                        self.warning(
                            "No location found near coordinates",
                            latitude=lat,
                            longitude=lon,
                            total_processed=processed
                        )
                        return []

                    location_id = nearest_location.get('globalIdLocal')
                    if not location_id:
                        self.warning(
                            "Location has no ID",
                            location=nearest_location
                        )
                        return []
                    
                    # Cache the location for future use
                    self.location_cache.cache_ipma_location(
                        lat=lat,
                        lon=lon,
                        location_code=str(location_id),
                        name=nearest_location.get('local', ''),
                        loc_lat=float(nearest_location.get('latitude', 0)),
                        loc_lon=float(nearest_location.get('longitude', 0)),
                        distance=min_distance
                    )

                # Get forecast data
                forecast_url = f"{self.endpoint}/forecast/meteorology/cities/daily/{location_id}.json"
                self.debug(
                    "Getting forecast data",
                    url=forecast_url,
                    location_id=location_id,
                    location_name=cached_location['name'] if cached_location else nearest_location.get('local', 'unknown'),
                    distance_km=cached_location['distance'] if cached_location else min_distance
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
                    return []

                forecast_data = forecast_response.json()
                if not forecast_data or 'data' not in forecast_data:
                    error = WeatherError(
                        "Invalid forecast data format from IPMA API",
                        ErrorCode.INVALID_RESPONSE,
                        {"response": forecast_data}
                    )
                    aggregate_error(str(error), "portuguese_weather", None)
                    return []

                self.debug(
                    "Received forecast data",
                    data=json.dumps(forecast_data, indent=2),
                    data_type=type(forecast_data).__name__,
                    has_data=bool(forecast_data.get('data')),
                    data_length=len(forecast_data.get('data', [])),
                    first_period=forecast_data.get('data', [{}])[0] if forecast_data.get('data') else None
                )

                forecasts = []
                for period in forecast_data.get('data', []):
                    with handle_errors(
                        WeatherError,
                        "portuguese_weather",
                        "process forecast period",
                        lambda: None
                    ):
                        # Parse forecast date (YYYY-MM-DD format)
                        try:
                            # Parse the actual forecast date from API
                            forecast_date = datetime.strptime(
                                period.get('forecastDate', ''),
                                '%Y-%m-%d'
                            ).replace(tzinfo=local_tz)
                            
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
                                    thunder_probability=thunder_prob
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
                
            except requests.exceptions.Timeout:
                error = APITimeoutError(
                    "IPMA API request timed out",
                    {"url": forecast_url if 'forecast_url' in locals() else locations_url}
                )
                aggregate_error(str(error), "portuguese_weather", None)
                return []
            except requests.exceptions.RequestException as e:
                error = APIError(
                    f"IPMA API request failed: {str(e)}",
                    ErrorCode.REQUEST_FAILED,
                    {"url": forecast_url if 'forecast_url' in locals() else locations_url}
                )
                aggregate_error(str(error), "portuguese_weather", e.__traceback__)
                return []

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
                    thunder_probability=data['probability_of_thunder']
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

    def get_block_size(self, hours_ahead: float) -> int:
        """Get block size for IPMA forecasts.
        
        IPMA provides:
        - 1-hour blocks for first 24 hours
        - 3-hour blocks for 24-72 hours
        - 6-hour blocks beyond 72 hours
        """
        if hours_ahead <= 24:
            return 1
        elif hours_ahead <= 72:
            return 3
        else:
            return 6

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

    @log_execution(level='DEBUG', include_args=True)
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, club: str = None) -> Optional[List[WeatherData]]:
        """Get weather data from IPMA."""
        try:
            now_utc = datetime.now(ZoneInfo("UTC"))
            
            # IPMA only provides forecasts up to 5 days ahead
            max_forecast_time = now_utc + timedelta(days=5)
            if start_time > max_forecast_time:
                self.debug(f"Requested time {start_time} is beyond maximum forecast range of 5 days")
                return None
                
            if end_time > max_forecast_time:
                self.debug(f"Limiting forecast end time to {max_forecast_time} (5 days ahead)")
                end_time = max_forecast_time
            
            # Determine if the start time is more than 24 hours in the future
            is_far_future = (start_time - now_utc).total_seconds() > 24 * 3600
            interval = 3 if is_far_future else 1
            
            # Calculate the base time for fetching weather data
            base_hour = (start_time.hour // interval) * interval
            base_time = start_time.replace(hour=base_hour, minute=0, second=0, microsecond=0)
            
            # Adjust base_time if necessary to ensure we cover the event start
            if base_time > start_time:
                base_time -= timedelta(hours=interval)
            
            # Calculate end time to ensure we cover the event end
            end_hour = min(23, ((end_time.hour + interval - 1) // interval) * interval)  # Ensure hour doesn't exceed 23
            fetch_end_time = end_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            if fetch_end_time < end_time:
                # If we need to go to the next day, add a day and set hour to 0
                fetch_end_time = (fetch_end_time + timedelta(days=1)).replace(hour=0)
            
            # Check if we have cached data
            if club and self.cache:
                location = f"{lat:.4f},{lon:.4f}"
                # Generate a list of times to check in cache
                cache_times = []
                current_time = base_time
                while current_time <= fetch_end_time:
                    cache_times.append(current_time.strftime('%Y-%m-%dT%H:%M:%S+00:00'))
                    current_time += timedelta(hours=interval)
                
                fields = ['air_temperature', 'precipitation_amount', 'probability_of_precipitation', 'wind_speed', 'wind_from_direction', 'summary_code', 'probability_of_thunder']
                cached_data = self.cache.get_weather_data(location, cache_times, 'hourly', fields)
                
                # Log cache status
                self._log_cache_status(location, cached_data, len(cache_times))
                
                if cached_data:
                    # Convert cached data to WeatherData objects
                    forecasts = []
                    for time_str, data in cached_data.items():
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
                            block_duration=timedelta(hours=interval)
                        )
                        forecasts.append(forecast)
                    return forecasts
            
            # Fetch data from API
            forecasts = self._fetch_forecasts(lat, lon, base_time, fetch_end_time)
            if not forecasts:
                return None
            
            # Set block duration for each forecast
            for forecast in forecasts:
                forecast.block_duration = timedelta(hours=interval)
            
            # Cache the results
            if club and self.cache:
                # Convert forecasts to database format
                cache_data = []
                location = f"{lat:.4f},{lon:.4f}"
                for forecast in forecasts:
                    cache_data.append({
                        'location': location,
                        'time': forecast.elaboration_time.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                        'data_type': 'hourly',
                        'air_temperature': forecast.temperature,
                        'precipitation_amount': forecast.precipitation,
                        'probability_of_precipitation': forecast.precipitation_probability,
                        'wind_speed': forecast.wind_speed,
                        'wind_from_direction': forecast.wind_direction,
                        'summary_code': forecast.symbol,
                        'probability_of_thunder': forecast.thunder_probability
                    })
                self.cache.store_weather_data(
                    cache_data,
                    expires=(now_utc + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                    last_modified=now_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                )
            
            return forecasts
            
        except Exception as e:
            self.error(f"Failed to get weather data: {e}")
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
