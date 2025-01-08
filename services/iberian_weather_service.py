"""Service for handling weather data for Iberian region."""

import os
import time
import json
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
import math

from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherCode, WeatherResponse
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import IBERIAN_SCHEMA
from golfcal2.services.weather_cache import WeatherLocationCache
from golfcal2.utils.logging_utils import log_execution
from golfcal2.config.settings import load_config
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
https://opendata.aemet.es/dist/index.html?

AEMET OpenData API provides:
- Hourly forecasts for next 48 hours
- 6-hourly forecasts for next 2 days after that
- Daily forecasts up to 7 days

API endpoints:
- /prediccion/especifica/municipio/horaria/{municipio} - Hourly forecast for municipality
- /prediccion/especifica/municipio/diaria/{municipio} - Daily forecast for municipality
- /maestro/municipios - List of municipalities

Update schedule (UTC):
- 03:00
- 09:00
- 15:00
- 21:00
"""

class IberianWeatherService(WeatherService):
    """Service for handling weather data for Iberian region."""

    BASE_URL = "https://opendata.aemet.es/opendata/api"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        """Initialize service."""
        super().__init__(local_tz, utc_tz)
        
        # Configure logger
        for handler in self.logger.handlers:
            handler.set_name('iberian_weather')  # Ensure unique handler names
        self.logger.propagate = False  # Prevent duplicate logs
        
        # Test debug call to verify logger name mapping
        self.debug(">>> TEST DEBUG: IberianWeatherService initialized", logger_name=self.logger.name)
        
        with handle_errors(WeatherError, "iberian_weather", "initialize service"):
            self.api_key = config.global_config['api_keys']['weather']['aemet']
            
            self.endpoint = self.BASE_URL
            self.headers = {
                'Accept': 'application/json',
                'User-Agent': self.USER_AGENT,
                'api_key': self.api_key  # AEMET requires API key in headers
            }
            
            # Initialize database and cache
            self.db = WeatherDatabase('iberian_weather', IBERIAN_SCHEMA)
            self.cache = self.db  # Use database as cache
            self.location_cache = WeatherLocationCache(config)
            
            # Rate limiting configuration
            self._last_api_call = None
            self._min_call_interval = timedelta(seconds=1)
            self._last_request_time = 0
            
            self.set_log_context(service="IberianWeatherService")
    
    @log_execution(level='DEBUG', include_args=True)
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, club: str = None) -> Optional[List[WeatherData]]:
        """Get weather data from AEMET."""
        try:
            now_utc = datetime.now(ZoneInfo("UTC"))
            
            # Use the timezone from the start_time parameter
            local_tz = start_time.tzinfo
            self.debug(f"Using timezone {local_tz} for coordinates ({lat}, {lon})")
            
            # Check forecast range - AEMET provides:
            # - Hourly data for next 48 hours
            # - 6-hourly data for 2 days after that
            hours_ahead = (start_time - now_utc).total_seconds() / 3600
            if hours_ahead > 96:  # 48 hours hourly + 48 hours 6-hourly
                self.info(
                    "Requested time beyond AEMET forecast range",
                    requested_time=start_time.isoformat(),
                    hours_ahead=hours_ahead,
                    max_hours=96
                )
                return None
            
            # Determine forecast interval based on how far ahead we're looking
            interval_hours = 1 if hours_ahead <= 48 else 6
            
            # For 6-hour blocks, align start and end times to block boundaries
            if interval_hours == 6:
                # Round down start time to nearest 6-hour block
                block_start = (start_time.hour // 6) * 6
                start_time = start_time.replace(hour=block_start, minute=0, second=0, microsecond=0)
                
                # Round up end time to next 6-hour block
                block_end = ((end_time.hour + 5) // 6) * 6
                end_time = end_time.replace(hour=block_end, minute=0, second=0, microsecond=0)
            
            self.debug(
                "Using forecast interval",
                hours_ahead=hours_ahead,
                interval_hours=interval_hours,
                aligned_start=start_time.isoformat(),
                aligned_end=end_time.isoformat()
            )
            
            # Check cache first
            location = f"{lat:.4f},{lon:.4f}"
            # Generate a list of times to check in cache
            cache_times = []
            # Round down to nearest hour for cache checking
            current_time = start_time.replace(minute=0, second=0, microsecond=0)
            while current_time <= end_time:
                # Convert to UTC for cache lookup since we store everything in UTC
                if current_time.tzinfo != timezone.utc:
                    current_time = current_time.astimezone(timezone.utc)
                cache_times.append(current_time.isoformat())
                current_time += timedelta(hours=interval_hours)
                
            fields = ['air_temperature', 'precipitation_amount', 'probability_of_precipitation', 
                     'wind_speed', 'wind_from_direction', 'summary_code', 'probability_of_thunder',
                     'block_duration_hours']
            
            # Try both hourly and daily data types
            data_type = 'daily' if hours_ahead > 54 else 'hourly'
            cached_data = self.db.get_weather_data(location, cache_times, data_type, fields)
            if cached_data:
                self.debug(
                    "Found cached weather data",
                    count=len(cached_data)
                )
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
                        block_duration=timedelta(hours=data.get('block_duration_hours', 1))
                    )
                    forecasts.append(forecast)
                
                if forecasts:
                    self.info(
                        "Cache hit - using cached forecasts",
                        location=location,
                        count=len(forecasts),
                        time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
                    )
                    return sorted(forecasts, key=lambda x: x.elaboration_time)
            
            self.info(
                "Cache miss - fetching from AEMET API",
                location=location,
                time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
            )
            
            # Convert start and end times to local timezone for AEMET
            start_time_local = start_time
            end_time_local = end_time
            
            # Get the forecasts using local time
            forecasts = self._fetch_forecasts(lat, lon, start_time_local, end_time_local, local_tz, now_utc, interval_hours)
            if not forecasts:
                return None
                
            # Sort forecasts by time
            forecasts.sort(key=lambda x: x.elaboration_time)
            
            # Update cache with new forecasts
            try:
                cache_data = []
                for forecast in forecasts:
                    # Calculate hours ahead for this forecast
                    hours_ahead = (forecast.elaboration_time - now_utc).total_seconds() / 3600
                    
                    cache_entry = {
                        'location': location,  # Use the same truncated location key
                        'time': forecast.elaboration_time.isoformat(),
                        'data_type': 'daily' if hours_ahead > 54 else 'hourly',  # Use correct data type
                        'air_temperature': forecast.temperature,
                        'precipitation_amount': forecast.precipitation,
                        'probability_of_precipitation': forecast.precipitation_probability,
                        'wind_speed': forecast.wind_speed,
                        'wind_from_direction': forecast.wind_direction,
                        'summary_code': forecast.symbol,
                        'probability_of_thunder': forecast.thunder_probability,
                        'block_duration_hours': forecast.block_duration.total_seconds() / 3600
                    }
                    cache_data.append(cache_entry)
                
                if cache_data:  # Only store if we have data
                    self.debug(
                        "Storing forecasts in cache",
                        count=len(cache_data),
                        data_type=cache_data[0]['data_type'],
                        block_hours=[d['block_duration_hours'] for d in cache_data]
                    )
                    
                    # Calculate expiry time based on AEMET's update schedule
                    current_hour = now_utc.hour
                    update_hours = [3, 9, 15, 21]  # AEMET update times (UTC)
                    next_update_hour = next((hour for hour in update_hours if hour > current_hour), update_hours[0])
                    
                    if next_update_hour <= current_hour:
                        # If we're past all update times today, next update is tomorrow
                        expires = (now_utc + timedelta(days=1)).replace(hour=update_hours[0], minute=0, second=0, microsecond=0)
                    else:
                        expires = now_utc.replace(hour=next_update_hour, minute=0, second=0, microsecond=0)
                    
                    self.debug(
                        "Setting cache expiry",
                        current_hour=current_hour,
                        next_update=next_update_hour,
                        expires=expires.isoformat()
                    )
                    
                    self.db.store_weather_data(
                        cache_data,
                        expires=expires.isoformat(),
                        last_modified=now_utc.isoformat()
                    )
            except Exception as e:
                self.warning(f"Failed to update cache: {e}")
            
            self.debug(
                "Completed forecast processing",
                total_forecasts=len(forecasts),
                time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
            )
            
            if not forecasts:
                self.warning(
                    "No forecasts available for requested time range",
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                    available_dates=[dia.get('fecha') for dia in forecast_data[0].get('prediccion', {}).get('dia', [])]
                )
                
            return forecasts
        except Exception as e:
            self.error(f"Failed to get weather data: {e}")
            return None

    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime, local_tz: ZoneInfo, now_utc: datetime, interval_hours: int) -> List[WeatherData]:
        """Fetch forecasts from AEMET API."""
        with handle_errors(
            WeatherError,
            "iberian_weather",
            f"fetch forecasts for coordinates ({lat}, {lon})",
            lambda: []  # Fallback to empty list on error
        ):
            # Get nearest municipality from cache first
            nearest_municipality = self.location_cache.get_aemet_municipality(lat, lon)
            
            if not nearest_municipality:
                self.error(
                    "No municipality found",
                    lat=lat,
                    lon=lon
                )
                return []
            
            municipality_code = nearest_municipality['code']
            
            self.debug(
                "Found nearest municipality",
                name=nearest_municipality['name'],
                code=municipality_code,
                distance_km=nearest_municipality['distance']
            )

            # Calculate hours ahead
            hours_ahead = (start_time - now_utc).total_seconds() / 3600
            
            # Use daily forecast endpoint for forecasts beyond hourly range
            if hours_ahead > 54:  # AEMET hourly forecasts only go up to ~54 hours
                forecast_url = f"{self.endpoint}/prediccion/especifica/municipio/diaria/{municipality_code[2:]}"
                self.debug(
                    "Using daily forecast endpoint",
                    url=forecast_url,
                    hours_ahead=hours_ahead
                )
            else:
                forecast_url = f"{self.endpoint}/prediccion/especifica/municipio/horaria/{municipality_code[2:]}"
                self.debug(
                    "Using hourly forecast endpoint",
                    url=forecast_url,
                    hours_ahead=hours_ahead
                )

            # Now check if we have the API key before making any requests
            if not self.api_key:
                error = WeatherError(
                    "AEMET API key not configured",
                    ErrorCode.CONFIG_MISSING,
                    {"setting": "api_keys.weather.aemet"}
                )
                aggregate_error(str(error), "iberian_weather", None)
                return []

            try:
                # Get the weather forecast for this municipality
                municipality_code = nearest_municipality['code']
                if municipality_code.startswith('id'):
                    municipality_code = municipality_code[2:]  # Remove 'id' prefix
                
                self.debug(
                    "Fetching AEMET forecast",
                    url=forecast_url,
                    municipality_id=municipality_code,
                    municipality_name=nearest_municipality['name']
                )
                
                # Respect rate limits
                if self._last_api_call:
                    time_since_last = datetime.now() - self._last_api_call
                    if time_since_last < self._min_call_interval:
                        sleep_time = (self._min_call_interval - time_since_last).total_seconds()
                        self.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                        time.sleep(sleep_time)
                
                self.debug("Making AEMET API request")
                response = requests.get(
                    forecast_url,
                    headers=self.headers,  # API key is already in headers
                    timeout=10
                )
                
                self._last_api_call = datetime.now()
                self.debug(f"AEMET API response status: {response.status_code}")
                
                if response.status_code == 429:  # Too Many Requests
                    error = APIRateLimitError(
                        "AEMET API rate limit exceeded",
                        retry_after=int(response.headers.get('Retry-After', 60))
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                if response.status_code != 200:
                    error = APIResponseError(
                        f"AEMET API request failed with status {response.status_code}",
                        response=response
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                data = response.json()
                self.debug("Got AEMET API response data", data=data)
                
                if not data or 'datos' not in data:
                    error = WeatherError(
                        "Invalid response format from AEMET API",
                        ErrorCode.INVALID_RESPONSE,
                        {"response": data}
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                # Get actual forecast data
                self.debug("Fetching forecast data from", url=data['datos'])
                forecast_response = requests.get(
                    data['datos'],
                    headers=self.headers,
                    timeout=10
                )
                
                self.debug(f"Forecast data response status: {forecast_response.status_code}")
                
                if forecast_response.status_code == 404:  # Not Found - no data available
                    self.warning(
                        "No forecasts found for municipality",
                        municipality_code=municipality_code,
                        municipality_name=nearest_municipality['name'],
                        latitude=lat,
                        longitude=lon,
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat()
                    )
                    return []
                
                if forecast_response.status_code != 200:
                    error = APIResponseError(
                        f"AEMET forecast data request failed with status {forecast_response.status_code}",
                        response=forecast_response
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                forecast_data = forecast_response.json()
                if not forecast_data:
                    error = WeatherError(
                        "Invalid forecast data format from AEMET API",
                        ErrorCode.INVALID_RESPONSE,
                        {"response": forecast_data}
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                # Check if the response indicates an error
                if isinstance(forecast_data, dict) and forecast_data.get('estado') == 404:
                    self.warning(
                        "AEMET API returned error response",
                        error=forecast_data.get('descripcion', 'Unknown error'),
                        municipality_code=municipality_code,
                        municipality_name=nearest_municipality['name']
                    )
                    return []

                # Add detailed debug logging
                self.debug(
                    "Received forecast data",
                    data_type=type(forecast_data).__name__,
                    data_length=len(forecast_data) if isinstance(forecast_data, (list, dict)) else 0,
                    data=json.dumps(forecast_data, indent=2),  # Log the entire response
                    url=data['datos']  # Log the URL we fetched from
                )

                if not isinstance(forecast_data, list) or not forecast_data:
                    self.warning(
                        "Unexpected forecast data format",
                        expected="non-empty list",
                        actual_type=type(forecast_data).__name__,
                        data=json.dumps(forecast_data, indent=2)
                    )
                    return []

                # Log the first forecast entry structure
                self.debug(
                    "First forecast entry",
                    dias=len(forecast_data[0].get('prediccion', {}).get('dia', [])),
                    nombre=forecast_data[0].get('nombre', 'unknown')
                )

                # Use _parse_daily_forecast to process the data
                return self._parse_daily_forecast(forecast_data, start_time, end_time, local_tz)

            except requests.exceptions.Timeout:
                error = APITimeoutError(
                    "AEMET API request timed out",
                    {"url": forecast_url}
                )
                aggregate_error(str(error), "iberian_weather", None)
                return []
            except requests.exceptions.RequestException as e:
                error = APIError(
                    f"AEMET API request failed: {str(e)}",
                    ErrorCode.REQUEST_FAILED,
                    {"url": forecast_url}
                )
                aggregate_error(str(error), "iberian_weather", e.__traceback__)
                return []

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance between two points on the earth."""
        R = 6371  # Earth's radius in kilometers

        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c  # Distance in kilometers
    
    def _map_aemet_code(self, code: str, hour: int) -> str:
        """Map AEMET weather codes to our internal codes.
        
        AEMET codes:
        11 - Clear sky
        11n - Clear sky (night)
        12 - Slightly cloudy
        12n - Slightly cloudy (night)
        13 - Intervals of clouds
        13n - Intervals of clouds (night)
        14 - Cloudy
        15 - Very cloudy
        16 - Overcast
        17 - High clouds
        23 - Intervals of clouds with rain
        24 - Cloudy with rain
        25 - Very cloudy with rain
        26 - Overcast with rain
        33 - Intervals of clouds with snow
        34 - Cloudy with snow
        35 - Very cloudy with snow
        36 - Overcast with snow
        43 - Intervals of clouds with rain and snow
        44 - Cloudy with rain and snow
        45 - Very cloudy with rain and snow
        46 - Overcast with rain and snow
        51 - Intervals of clouds with storm
        52 - Cloudy with storm
        53 - Very cloudy with storm
        54 - Overcast with storm
        61 - Intervals of clouds with snow storm
        62 - Cloudy with snow storm
        63 - Very cloudy with snow storm
        64 - Overcast with snow storm
        71 - Intervals of clouds with rain and storm
        72 - Cloudy with rain and storm
        73 - Very cloudy with rain and storm
        74 - Overcast with rain and storm
        """
        with handle_errors(
            WeatherError,
            "iberian_weather",
            f"map weather code {code}",
            lambda: WeatherCode.CLOUDY  # Fallback to cloudy on error
        ):
            is_day = 6 <= hour <= 20
            
            # Remove 'n' suffix for night codes
            base_code = code.rstrip('n')
            
            code_map = {
                # Clear conditions
                '11': 'clearsky_day' if is_day else 'clearsky_night',
                '12': 'fair_day' if is_day else 'fair_night',
                '13': 'partlycloudy_day' if is_day else 'partlycloudy_night',
                '14': 'cloudy',
                '15': 'cloudy',
                '16': 'cloudy',
                '17': 'partlycloudy_day' if is_day else 'partlycloudy_night',
                
                # Rain
                '23': 'lightrainshowers_day' if is_day else 'lightrainshowers_night',
                '24': 'lightrain',
                '25': 'rain',
                '26': 'rain',
                
                # Snow
                '33': 'lightsnowshowers_day' if is_day else 'lightsnowshowers_night',
                '34': 'lightsnow',
                '35': 'snow',
                '36': 'snow',
                
                # Mixed precipitation
                '43': 'sleetshowers_day' if is_day else 'sleetshowers_night',
                '44': 'lightsleet',
                '45': 'sleet',
                '46': 'sleet',
                
                # Thunderstorms
                '51': 'rainandthunder',
                '52': 'rainandthunder',
                '53': 'heavyrainandthunder',
                '54': 'heavyrainandthunder',
                
                # Snow with thunder
                '61': 'snowandthunder',
                '62': 'snowandthunder',
                '63': 'heavysnowandthunder',
                '64': 'heavysnowandthunder',
                
                # Rain and thunder
                '71': 'rainandthunder',
                '72': 'rainandthunder',
                '73': 'heavyrainandthunder',
                '74': 'heavyrainandthunder'
            }
            
            return code_map.get(base_code, 'cloudy')  # Default to cloudy if code not found
    
    def _get_wind_direction(self, direction: Optional[str]) -> Optional[str]:
        """Convert wind direction to cardinal direction."""
        if direction is None:
            return None
            
        # Map of Spanish abbreviations to standard cardinal directions
        direction_map = {
            'N': 'N',
            'NE': 'NE',
            'E': 'E',
            'SE': 'SE',
            'S': 'S',
            'SO': 'SW',  # Spanish: Sudoeste -> Southwest
            'O': 'W',    # Spanish: Oeste -> West
            'NO': 'NW'   # Spanish: Noroeste -> Northwest
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

    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size based on hours ahead.
        
        AEMET provides:
        - Hourly data for temperature, precipitation, wind, and sky conditions
        - 6-hour blocks for precipitation probability (periods like "0006", "0612", etc.)
        
        We'll return 1 for all forecasts since we need to process hourly data,
        but internally we'll handle the 6-hour probability blocks in the data parsing.
        """
        return 1  # Always return 1 since AEMET provides hourly data

    def _convert_cached_data(self, cached_data: Dict[str, Dict[str, Any]]) -> List[WeatherData]:
        """Convert cached data back to WeatherData objects."""
        self.debug("Converting cached data to WeatherData objects")
        forecasts = []
        
        for time_str, data in cached_data.items():
            try:
                # Parse ISO format time string
                forecast_time = datetime.fromisoformat(time_str)
                
                forecast = WeatherData(
                    temperature=data.get('air_temperature', 0.0),
                    precipitation=data.get('precipitation_amount', 0.0),
                    precipitation_probability=data.get('probability_of_precipitation', 0.0),
                    wind_speed=data.get('wind_speed', 0.0),
                    wind_direction=data.get('wind_from_direction'),
                    symbol=data.get('summary_code', 'cloudy'),
                    elaboration_time=forecast_time,
                    thunder_probability=data.get('probability_of_thunder', 0.0)
                )
                forecasts.append(forecast)
                
                self.debug(
                    "Converted cached forecast",
                    time=forecast_time.isoformat(),
                    temp=forecast.temperature,
                    precip=forecast.precipitation,
                    wind=forecast.wind_speed,
                    symbol=forecast.symbol
                )
                
            except (ValueError, KeyError) as e:
                self.warning(
                    "Failed to convert cached forecast",
                    error=str(e),
                    data=data
                )
                continue
        
        self.debug(f"Converted {len(forecasts)} cached forecasts")
        return sorted(forecasts, key=lambda x: x.elaboration_time)

    def get_expiry_time(self) -> datetime:
        """Get expiry time for AEMET weather data.
        
        AEMET updates their forecasts four times daily at:
        - 03:00 UTC
        - 09:00 UTC
        - 15:00 UTC
        - 21:00 UTC
        
        They also provide an expiry time in their response headers,
        but we'll use their known update schedule as a fallback.
        """
        now = datetime.now(self.utc_tz)
        
        # If we have an expiry time from the response, use it
        if hasattr(self, '_response_expires') and self._response_expires:
            return self._response_expires
        
        # Calculate next update time based on schedule
        current_hour = now.hour
        update_hours = [3, 9, 15, 21]
        
        # Find the next update hour
        next_update_hour = next((hour for hour in update_hours if hour > current_hour), update_hours[0])
        
        # If we're past all update hours today, the next update is tomorrow
        if next_update_hour <= current_hour:
            next_update = (now + timedelta(days=1)).replace(hour=update_hours[0], minute=0, second=0, microsecond=0)
        else:
            next_update = now.replace(hour=next_update_hour, minute=0, second=0, microsecond=0)
        
        return next_update
    
    def _parse_response_expiry(self, response: requests.Response) -> None:
        """Parse expiry time from AEMET response headers."""
        try:
            # AEMET provides expiry time in 'Expires' header
            expires_header = response.headers.get('Expires')
            if expires_header:
                self._response_expires = datetime.strptime(
                    expires_header,
                    '%a, %d %b %Y %H:%M:%S %Z'
                ).replace(tzinfo=self.utc_tz)
                self.debug(f"Got expiry time from response: {self._response_expires.isoformat()}")
            else:
                self._response_expires = None
        except (ValueError, TypeError) as e:
            self.warning(f"Failed to parse expiry time from response: {e}")
            self._response_expires = None

    def _prepare_cache_entry(self, location: str, time: str, temp: float, precip: float, 
                           wind_speed: Optional[float] = None, wind_direction: Optional[str] = None,
                           prob_precip: Optional[float] = None, prob_thunder: Optional[float] = None,
                           sky_code: Optional[str] = None) -> Dict[str, Any]:
        """Prepare a cache entry for storing."""
        # Convert time to ISO format with timezone if needed
        try:
            dt = datetime.fromisoformat(time)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            iso_time = dt.isoformat()
        except ValueError:
            # If not ISO format, try parsing as regular datetime
            dt = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
            dt = dt.replace(tzinfo=timezone.utc)
            iso_time = dt.isoformat()

        # Get hour for day/night symbol mapping
        hour = dt.hour

        self.debug(
            "Prepared cache entry",
            location=location,
            time=time,
            temp=temp,
            precip=precip,
            sky_code=sky_code
        )
        
        return {
            'location': location,
            'time': iso_time,
            'data_type': 'daily',
            'air_temperature': temp,
            'precipitation_amount': precip,
            'wind_speed': wind_speed,
            'wind_from_direction': self._get_wind_direction(wind_direction),
            'probability_of_precipitation': prob_precip,
            'probability_of_thunder': prob_thunder,
            'summary_code': self._map_aemet_code(str(sky_code), hour) if sky_code else 'cloudy'
        }

    def _parse_forecast_data(self, data: List[Dict[str, Any]], start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Parse AEMET forecast data."""
        with handle_errors(
            WeatherError,
            "iberian_weather",
            "parse forecast data",
            lambda: []  # Fallback to empty list on error
        ):
            if not data or not isinstance(data, list):
                self.error("Invalid forecast data format", data=data)
                return []
            
            forecasts = []
            
            # Convert times to UTC for comparison
            start_time_utc = start_time.astimezone(self.utc_tz)
            end_time_utc = end_time.astimezone(self.utc_tz)
            
            for day_data in data:
                try:
                    # Get date from prediccion
                    date_str = day_data.get('prediccion', {}).get('dia', [{}])[0].get('fecha')
                    if not date_str:
                        self.warning("No date found in forecast data")
                        continue
                    
                    # Parse date (format: YYYY-MM-DD)
                    try:
                        base_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=self.utc_tz)
                    except ValueError:
                        self.warning("Invalid date format", date=date_str)
                        continue
                    
                    # Get hourly data
                    hourly_data = day_data.get('prediccion', {}).get('dia', [{}])[0]
                    
                    # Process each hour
                    for hour in range(24):
                        forecast_time = base_date.replace(hour=hour)
                        
                        # Skip if outside requested time range
                        if forecast_time < start_time_utc or forecast_time > end_time_utc:
                            continue
                        
                        # Get temperature for this hour
                        temperature = None
                        for temp_data in hourly_data.get('temperatura', []):
                            if temp_data.get('periodo') == str(hour):
                                temperature = float(temp_data.get('valor', 0))
                                break
                        
                        # Get precipitation for this hour
                        precipitation = 0.0
                        precipitation_prob = 0.0
                        for precip_data in hourly_data.get('precipitacion', []):
                            if precip_data.get('periodo') == str(hour):
                                precipitation = float(precip_data.get('valor', 0))
                                precipitation_prob = float(precip_data.get('probabilidad', 0)) / 100
                                break
                        
                        # Get wind data for this hour
                        wind_speed = 0.0
                        wind_direction = None
                        for wind_data in hourly_data.get('viento', []):
                            if wind_data.get('periodo') == str(hour):
                                wind_speed = float(wind_data.get('velocidad', 0))
                                wind_direction = self._get_wind_direction(wind_data.get('direccion'))
                                break
                        
                        # Get thunder probability for this hour
                        thunder_prob = 0.0
                        for storm_data in hourly_data.get('tormenta', []):
                            if storm_data.get('periodo') == str(hour):
                                thunder_prob = float(storm_data.get('probabilidad', 0)) / 100
                                break
                        
                        # Get weather symbol for this hour
                        symbol = 'cloudy'  # Default symbol
                        for state_data in hourly_data.get('estadoCielo', []):
                            if state_data.get('periodo') == str(hour):
                                symbol = self._get_weather_symbol(state_data.get('descripcion', ''))
                                break
                        
                        forecast = WeatherData(
                            temperature=temperature,
                            precipitation=precipitation,
                            precipitation_probability=precipitation_prob,
                            wind_speed=wind_speed,
                            wind_direction=wind_direction,
                            symbol=symbol,
                            elaboration_time=forecast_time,
                            thunder_probability=thunder_prob
                        )
                        
                        forecasts.append(forecast)
                        
                except Exception as e:
                    self.error("Failed to parse day forecast", error=str(e), exc_info=True)
                    continue
            
            self.debug(f"Parsed {len(forecasts)} hourly forecasts")
            return forecasts

    def _parse_daily_forecast(self, forecast_data: List[Dict], start_time: datetime, end_time: datetime, local_tz: ZoneInfo) -> List[WeatherData]:
        """Parse daily forecast data from AEMET."""
        forecasts = []
        
        if not forecast_data or not isinstance(forecast_data, list) or len(forecast_data) == 0:
            self.warning(
                "Invalid forecast data format",
                expected="non-empty list",
                actual_type=type(forecast_data).__name__,
                data=forecast_data
            )
            return []

        try:
            prediccion = forecast_data[0].get('prediccion', {})
            if not prediccion or not isinstance(prediccion, dict):
                self.warning(
                    "Invalid prediccion data format",
                    expected="dictionary",
                    actual_type=type(prediccion).__name__,
                    data=prediccion
                )
                return []

            dias = prediccion.get('dia', [])
            if not dias or not isinstance(dias, list):
                self.warning(
                    "Invalid dias data format",
                    expected="non-empty list",
                    actual_type=type(dias).__name__,
                    data=dias
                )
                return []

            for day in dias:
                try:
                    if not isinstance(day, dict):
                        self.warning(
                            "Invalid day data format",
                            expected="dictionary",
                            actual_type=type(day).__name__,
                            data=day
                        )
                        continue

                    # Get the date
                    date_str = day.get('fecha')
                    if not date_str:
                        self.warning("Missing fecha in day data", data=day)
                        continue

                    base_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                    base_date = base_date.replace(tzinfo=local_tz)
                    
                    # Determine if this is a short-term or medium-term forecast
                    now_utc = datetime.now(ZoneInfo("UTC"))
                    hours_ahead = (base_date - now_utc).total_seconds() / 3600
                    is_short_term = hours_ahead <= 48  # Short term = first 48 hours
                    
                    self.debug(
                        "Processing forecast",
                        date=date_str,
                        hours_ahead=hours_ahead,
                        is_short_term=is_short_term
                    )
                    
                    # Get temperature data
                    temp_data = day.get('temperatura')
                    if is_short_term and isinstance(temp_data, list):
                        # Short-term hourly format
                        temp_hours = {}
                        for temp_point in temp_data:
                            if isinstance(temp_point, dict):
                                try:
                                    hour = int(temp_point.get('periodo', 0))
                                    value = float(temp_point.get('value', 0))
                                    temp_hours[hour] = value
                                except (ValueError, TypeError) as e:
                                    self.warning(
                                        "Invalid temperature point",
                                        error=str(e),
                                        data=temp_point
                                    )
                                    continue
                        
                        # For hourly data, we don't need min/max
                        min_temp = max_temp = None
                    elif isinstance(temp_data, dict):
                        # Medium-term 6h block format
                        try:
                            min_temp = float(temp_data.get('minima', 0))
                            max_temp = float(temp_data.get('maxima', 0))
                            # Map hours to temperatures if available
                            temp_hours = {}
                            if isinstance(temp_data.get('dato'), list):
                                for temp_point in temp_data['dato']:
                                    if isinstance(temp_point, dict):
                                        try:
                                            hour = int(temp_point.get('hora', 0))
                                            value = float(temp_point.get('value', 0))
                                            temp_hours[hour] = value
                                        except (ValueError, TypeError) as e:
                                            self.warning(
                                                "Invalid temperature point",
                                                error=str(e),
                                                data=temp_point
                                            )
                                            continue
                        except (ValueError, TypeError) as e:
                            self.warning(
                                "Invalid temperature values",
                                error=str(e),
                                data=temp_data
                            )
                            continue
                    else:
                        self.warning(
                            "Invalid temperature data format",
                            expected="list (hourly) or dictionary (6h blocks)",
                            actual_type=type(temp_data).__name__,
                            data=temp_data
                        )
                        continue
                    
                    # Get all available periods from estadoCielo
                    periods = set()
                    estado_cielo = day.get('estadoCielo', [])
                    if isinstance(estado_cielo, list):
                        for item in estado_cielo:
                            if isinstance(item, dict):
                                period = item.get('periodo')
                                if period and period != '00-24':  # Skip full-day period
                                    # Handle both period ranges and single hours
                                    if '-' in str(period):
                                        periods.add(period)
                                    elif is_short_term:
                                        # Convert single hour to range for short-term forecasts
                                        try:
                                            hour = int(period)
                                            periods.add(f"{hour:02d}-{(hour+1):02d}")
                                        except (ValueError, TypeError):
                                            self.warning(
                                                "Invalid hour value",
                                                period=period
                                            )
                    
                    # If no specific periods found, use appropriate blocks based on forecast type
                    if not periods:
                        if is_short_term:
                            # For hourly data, use 1-hour blocks
                            periods = [f"{h:02d}-{(h+1):02d}" for h in range(24)]
                        else:
                            # For 6h blocks, use standard blocks
                            periods = ['00-06', '06-12', '12-18', '18-24']
                    
                    # Sort periods for consistent processing
                    periods = sorted(list(periods))
                    
                    for period in periods:
                        try:
                            # Parse period times
                            period_parts = period.split('-')
                            if len(period_parts) != 2:
                                self.warning(
                                    "Invalid period format",
                                    period=period
                                )
                                continue

                            try:
                                period_start = int(period_parts[0])
                                period_end = int(period_parts[1])
                            except ValueError as e:
                                self.warning(
                                    "Invalid period values",
                                    error=str(e),
                                    period=period
                                )
                                continue

                            forecast_time = base_date.replace(hour=period_start)
                            
                            # Skip if outside requested range
                            if forecast_time < start_time or forecast_time > end_time:
                                continue
                            
                            # Get temperature based on data format
                            if isinstance(temp_data, list):
                                # For hourly data, use exact hour
                                temp = temp_hours.get(period_start)
                            else:
                                # For 6h blocks, interpolate if needed
                                temp = temp_hours.get(period_start)
                                if temp is None:
                                    # Simple interpolation based on time of day
                                    if period_start < 6:
                                        temp = min_temp
                                    elif period_start < 14:
                                        temp = max_temp
                                    else:
                                        temp = min_temp + (max_temp - min_temp) * 0.5
                            
                            # Get precipitation probability
                            prob_precip = 0
                            prob_precipitacion = day.get('probPrecipitacion', [])
                            if isinstance(prob_precipitacion, list):
                                for prob in prob_precipitacion:
                                    if isinstance(prob, dict) and prob.get('periodo') == period:
                                        try:
                                            prob_precip = float(prob.get('value', 0))
                                        except (ValueError, TypeError):
                                            pass
                                        break
                            
                            # Get wind data
                            wind_speed = 0
                            wind_dir = 'C'
                            viento = day.get('viento', [])
                            if isinstance(viento, list):
                                for wind in viento:
                                    if isinstance(wind, dict) and wind.get('periodo') == period:
                                        try:
                                            wind_speed = float(wind.get('velocidad', 0))
                                            wind_dir = wind.get('direccion', 'C')
                                        except (ValueError, TypeError):
                                            pass
                                        break
                            
                            # Get sky condition
                            sky_value = ''
                            if isinstance(estado_cielo, list):
                                for sky in estado_cielo:
                                    if isinstance(sky, dict) and sky.get('periodo') == period:
                                        sky_value = sky.get('value', '')
                                        break
                            
                            block_duration = timedelta(hours=period_end - period_start)
                            
                            forecast = WeatherData(
                                temperature=float(temp),
                                precipitation=0.0,  # Daily forecast doesn't provide precipitation amount
                                precipitation_probability=prob_precip,
                                wind_speed=wind_speed / 3.6,  # Convert km/h to m/s
                                wind_direction=self._get_wind_direction(wind_dir),
                                symbol=self._map_aemet_code(sky_value, period_start) if sky_value else 'cloudy',
                                elaboration_time=forecast_time,
                                thunder_probability=0.0,
                                block_duration=block_duration
                            )
                            
                            forecasts.append(forecast)
                            
                        except (ValueError, TypeError, KeyError) as e:
                            self.warning(
                                "Failed to process period",
                                error=str(e),
                                period=period,
                                date=date_str,
                                exc_info=True
                            )
                            continue
                        
                except Exception as e:
                    self.warning(
                        "Failed to process day",
                        error=str(e),
                        data=day,
                        exc_info=True
                    )
                    continue
            
            return sorted(forecasts, key=lambda x: x.elaboration_time)
        except Exception as e:
            self.warning(
                "Failed to parse forecast data",
                error=str(e),
                data=forecast_data,
                exc_info=True
            )
            return []