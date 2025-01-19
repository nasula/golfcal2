"""Service for handling weather data for Iberian region."""

import os
import time
import json
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
import math

from golfcal2.services.base_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherCode, WeatherResponse, Location
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_location_cache import WeatherLocationCache
from golfcal2.utils.logging_utils import log_execution, get_logger
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
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal2 (jarkko.ahonen@iki.fi)"
    
    # AEMET forecast ranges
    HOURLY_RANGE = 48  # 48 hours of hourly forecasts
    SIX_HOURLY_RANGE = 96  # Up to 96 hours (4 days) for 6-hourly forecasts
    DAILY_RANGE = 168  # Up to 168 hours (7 days) for daily forecasts
    
    def __init__(self, timezone: ZoneInfo, utc: ZoneInfo, config: Dict[str, Any]):
        """Initialize service."""
        super().__init__(timezone, utc)
        self.config = config
        self.set_log_context(service="iberian_weather")
        
        # Rate limiting
        self._last_api_call = None
        self._min_call_interval = timedelta(seconds=1)
        
        # API configuration
        self.headers = {
            'Accept': 'application/json',
            'api_key': config.global_config['api_keys']['weather']['aemet']
        }

    def _init_municipality_cache(self):
        """Initialize municipality cache with data from AEMET API."""
        try:
            # Get municipalities from API
            municipalities_url = f"{self.BASE_URL}/maestro/municipios"
            response = requests.get(municipalities_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'datos' in data:
                    # AEMET returns a URL to the actual data
                    data_url = data['datos']
                    self.debug("Getting municipality data from URL", url=data_url)
                    
                    # Get the actual data
                    data_response = requests.get(data_url, headers=self.headers, timeout=10)
                    if data_response.status_code == 200:
                        municipalities = data_response.json()
                        if municipalities and isinstance(municipalities, list):
                            locations = []
                            for loc in municipalities:
                                try:
                                    location = {
                                        'id': str(loc['id']),
                                        'name': loc['nombre'],
                                        'latitude': float(loc['latitud']),
                                        'longitude': float(loc['longitud']),
                                        'metadata': {
                                            'province': loc.get('provincia'),
                                            'region': loc.get('comunidad'),
                                            'altitude': loc.get('altitud')
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
                                # Store for 90 days instead of 30
                                self.location_cache.store_location_set(
                                    service_type='aemet',
                                    set_type='municipalities',
                                    data=locations,
                                    expires_in=timedelta(days=90)
                                )
                                self.debug(f"Stored {len(locations)} locations in cache")
                            else:
                                self.error("Empty municipality list received from AEMET")
                        else:
                            self.error(
                                "Invalid municipality data format",
                                status=data_response.status_code,
                                data=municipalities
                            )
                    else:
                        self.error(
                            "Failed to get municipality data",
                            status=data_response.status_code,
                            url=data_url
                        )
                else:
                    self.error(
                        "Invalid response format",
                        status=response.status_code,
                        data=data
                    )
            else:
                self.error(
                    "Failed to get municipality list",
                    status=response.status_code
                )
        except requests.RequestException as e:
            self.error("Failed to fetch locations from AEMET API", exc_info=e)
        except Exception as e:
            self.error("Error initializing municipality cache", exc_info=e)

    def _find_nearest_municipality(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Find nearest municipality to given coordinates."""
        # First check if we have any municipalities cached
        has_municipalities = self.location_cache.get_location_set('aemet', 'municipalities')
        if not has_municipalities:
            # Only initialize once if cache is empty
            self._init_municipality_cache()

        nearest = self.location_cache.get_nearest_location('aemet', lat, lon)
        if nearest:
            return {
                'code': nearest['id'],
                'name': nearest['name'],
                'province': nearest['metadata'].get('province') if nearest['metadata'] else None,
                'region': nearest['metadata'].get('region') if nearest['metadata'] else None,
                'latitude': nearest['latitude'],
                'longitude': nearest['longitude'],
                'distance': nearest['distance']
            }
        
        return None

    @log_execution(level='DEBUG', include_args=True)
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, club: str = None) -> Optional[List[WeatherData]]:
        """Get weather data from AEMET."""
        # Quick return if location is outside coverage area
        if not self._is_in_coverage_area(lat, lon):
            self.debug(
                "Location outside coverage area",
                coords=(lat, lon)
            )
            return None
        
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
                service_type='aemet',
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
                service_type='aemet',
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

    def _fetch_forecasts(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from AEMET API."""
        try:
            # Check if location is in coverage area
            if not self._is_in_coverage_area(lat, lon):
                self.debug(
                    "Location outside coverage area",
                    coords=(lat, lon)
                )
                return None
            
            # Find nearest municipality
            municipality = self._find_nearest_municipality(lat, lon)
            if not municipality:
                self.warning(
                    "No municipality found for coordinates",
                    coords=(lat, lon)
                )
                return None

            # Get forecast data
            forecast_url = f"{self.BASE_URL}/prediccion/especifica/municipio/diaria/{municipality['id']}"
            self.debug(
                "Getting forecast data",
                url=forecast_url,
                location_id=municipality['id'],
                location_name=municipality['name'],
                distance_km=municipality['distance']
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
                    f"AEMET forecast request failed with status {forecast_response.status_code}",
                    response=forecast_response
                )
                aggregate_error(str(error), "iberian_weather", None)
                return None

            forecast_data = forecast_response.json()
            if not forecast_data or 'prediccion' not in forecast_data:
                error = WeatherError(
                    "Invalid forecast data format from AEMET API",
                    ErrorCode.INVALID_RESPONSE,
                    {"response": forecast_data}
                )
                aggregate_error(str(error), "iberian_weather", None)
                return None

            self.debug(
                "Received forecast data",
                data=json.dumps(forecast_data, indent=2),
                data_type=type(forecast_data).__name__,
                has_data=bool(forecast_data.get('prediccion')),
                data_length=len(forecast_data.get('prediccion', [])),
                first_period=forecast_data.get('prediccion', [{}])[0] if forecast_data.get('prediccion') else None
            )

            return forecast_data

        except Exception as e:
            self.error("Error fetching forecasts", exc_info=e)
            return None

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
        
        Args:
            code: AEMET weather code
            hour: Hour of the day (0-23) to determine day/night
        
        Returns:
            Internal weather code
        """
        # Determine if it's day or night
        is_daytime = 6 <= hour < 20  # Day is between 6:00 and 20:00
        
        # Strip 'n' suffix if present (AEMET uses 'n' for night)
        base_code = code.rstrip('n')
        
        # Map AEMET codes to our internal codes
        code_map = {
            '11': 'clearsky',      # Clear sky
            '12': 'fair',          # Few clouds
            '13': 'partlycloudy',  # Variable clouds
            '14': 'cloudy',        # Cloudy
            '15': 'cloudy',        # Very cloudy
            '16': 'cloudy',        # Overcast
            '17': 'partlycloudy',  # High clouds
            '23': 'rain',          # Rain
            '24': 'snow',          # Snow
            '25': 'sleet',         # Sleet
            '26': 'hail',          # Hail
            '27': 'thunder',       # Thunder
            '33': 'lightrain',     # Light rain
            '34': 'lightsnow',     # Light snow
            '35': 'lightsleet',    # Light sleet
            '36': 'lighthail',     # Light hail
            '43': 'heavyrain',     # Heavy rain
            '44': 'heavysnow',     # Heavy snow
            '45': 'heavysleet',    # Heavy sleet
            '46': 'heavyhail',     # Heavy hail
            '51': 'rainshowers',   # Rain showers
            '52': 'snowshowers',   # Snow showers
            '53': 'sleetshowers',  # Sleet showers
            '54': 'hailshowers',   # Hail showers
            '61': 'lightrainshowers',      # Light rain showers
            '62': 'lightsnowshowers',      # Light snow showers
            '63': 'lightsleetshowers',     # Light sleet showers
            '64': 'lighthailshowers',      # Light hail showers
            '71': 'heavyrainshowers',      # Heavy rain showers
            '72': 'heavysnowshowers',      # Heavy snow showers
            '73': 'heavysleetshowers',     # Heavy sleet showers
            '74': 'heavyhailshowers',      # Heavy hail showers
            '81': 'rainandthunder',        # Rain and thunder
            '82': 'snowandthunder',        # Snow and thunder
            '83': 'sleetandthunder',       # Sleet and thunder
            '84': 'hailandthunder',        # Hail and thunder
            '91': 'lightrainandthunder',   # Light rain and thunder
            '92': 'lightsnowandthunder',   # Light snow and thunder
            '93': 'lightsleetandthunder',  # Light sleet and thunder
            '94': 'lighthailandthunder'    # Light hail and thunder
        }
        
        # Get base weather type
        weather_type = code_map.get(base_code)
        if not weather_type:
            self.warning(
                "Unknown AEMET weather code",
                code=code,
                base_code=base_code
            )
            weather_type = 'clearsky'  # Default to clearsky if unknown code
        
        # Add day/night suffix
        return weather_type + ('_day' if is_daytime else '_night')
    
    def _get_wind_direction(self, direction: Optional[str]) -> Optional[str]:
        """Convert wind direction to cardinal direction."""
        if direction is None:
            return None
            
        # Handle calm conditions
        if direction == 'C':
            return 'CALM'
            
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
                    
                    # Determine if this is a short-term or medium-term forecast
                    now_utc = datetime.now(timezone.utc)
                    hours_ahead = (base_date - now_utc).total_seconds() / 3600
                    is_short_term = hours_ahead <= 48  # Short term = first 48 hours
                    
                    # Process each hour
                    if is_short_term:
                        step = 1  # Hourly data
                    else:
                        step = 6  # 6-hour blocks
                    
                    for hour in range(0, 24, step):
                        forecast_time = base_date.replace(hour=hour)
                        
                        # Skip if outside requested time range
                        if forecast_time < start_time_utc or forecast_time > end_time_utc:
                            continue
                        
                        # Get temperature for this hour
                        temperature = None
                        for temp_data in hourly_data.get('temperatura', []):
                            if temp_data.get('periodo') == str(hour):
                                try:
                                    temperature = float(temp_data.get('value', 0))
                                except (ValueError, TypeError):
                                    self.warning("Invalid temperature value", data=temp_data)
                                    temperature = 0.0
                                break
                        
                        # Get precipitation for this hour
                        precipitation = 0.0
                        precipitation_prob = 0.0
                        for precip_data in hourly_data.get('precipitacion', []):
                            if precip_data.get('periodo') == str(hour):
                                try:
                                    precipitation = float(precip_data.get('value', 0))
                                except (ValueError, TypeError):
                                    self.warning("Invalid precipitation value", data=precip_data)
                                break
                        
                        # Get precipitation probability from probPrecipitacion
                        for prob_data in hourly_data.get('probPrecipitacion', []):
                            if prob_data.get('periodo') == str(hour):
                                try:
                                    # Value is already a percentage (0-100)
                                    precipitation_prob = float(prob_data.get('value', 0))
                                except (ValueError, TypeError):
                                    self.warning("Invalid precipitation probability", data=prob_data)
                                break
                        
                        # Get wind data for this hour
                        wind_speed = 0.0
                        wind_direction = None
                        for wind_data in hourly_data.get('viento', []):
                            if wind_data.get('periodo') == str(hour):
                                try:
                                    wind_speed = float(wind_data.get('velocidad', 0)) / 3.6  # Convert km/h to m/s
                                    wind_direction = self._get_wind_direction(wind_data.get('direccion'))
                                except (ValueError, TypeError):
                                    self.warning("Invalid wind value", data=wind_data)
                                break
                        
                        # Get thunder probability for this hour
                        thunder_prob = 0.0
                        for storm_data in hourly_data.get('tormenta', []):
                            if storm_data.get('periodo') == str(hour):
                                try:
                                    thunder_prob = float(storm_data.get('probabilidad', 0)) / 100
                                except (ValueError, TypeError):
                                    self.warning("Invalid thunder probability", data=storm_data)
                                break
                        
                        # Get weather symbol for this hour
                        symbol = 'cloudy'  # Default symbol
                        for sky_data in hourly_data.get('estadoCielo', []):
                            if sky_data.get('periodo') == str(hour):
                                code = sky_data.get('value', '')
                                is_night = hour < 6 or hour >= 20
                                if code == '11' or code == '11n':
                                    symbol = 'clearsky_night' if is_night else 'clearsky_day'
                                    break
                                elif code == '12' or code == '12n':
                                    symbol = 'partly_cloudy_night' if is_night else 'partly_cloudy_day'
                                    break
                                elif code == '13' or code == '13n':
                                    symbol = 'cloudy'
                                    break
                                elif code == '14' or code == '14n':
                                    symbol = 'fog'
                                    break
                                elif code == '15' or code == '15n':
                                    symbol = 'rain'
                                    break
                                elif code == '16' or code == '16n':
                                    symbol = 'rain_showers'
                                    break
                                elif code == '17' or code == '17n':
                                    symbol = 'thunderstorm'
                                    break
                                elif code == '18' or code == '18n':
                                    symbol = 'snow'
                                    break
                        
                        # Set block duration based on whether it's short-term or not
                        block_duration = timedelta(hours=step)
                        
                        forecast = WeatherData(
                            temperature=temperature,
                            precipitation=precipitation,
                            precipitation_probability=precipitation_prob,
                            wind_speed=wind_speed,
                            wind_direction=wind_direction,
                            symbol=symbol,
                            elaboration_time=forecast_time,
                            thunder_probability=thunder_prob,
                            block_duration=block_duration
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
            # Convert start and end times to UTC for comparison
            start_time_utc = start_time.astimezone(timezone.utc)
            end_time_utc = end_time.astimezone(timezone.utc)
            
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
                    
                    # Parse date and ensure it has the correct timezone
                    base_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                    base_date = base_date.replace(tzinfo=local_tz)
                    
                    # Determine if this is a short-term or medium-term forecast
                    now_utc = datetime.now(timezone.utc)
                    hours_ahead = (base_date - now_utc).total_seconds() / 3600
                    is_short_term = hours_ahead <= self.HOURLY_RANGE  # Short term = first 48 hours
                    is_medium_term = self.HOURLY_RANGE < hours_ahead <= self.SIX_HOURLY_RANGE
                    
                    self.debug(
                        "Processing forecast",
                        date=date_str,
                        hours_ahead=hours_ahead,
                        is_short_term=is_short_term,
                        is_medium_term=is_medium_term,
                        timezone=str(local_tz)
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
                        elif is_medium_term:
                            # For 6h blocks, use standard blocks
                            periods = ['00-06', '06-12', '12-18', '18-24']
                        else:
                            # For long-term forecasts, use 12h blocks
                            periods = ['00-12', '12-24']
                    
                    # For short-term forecasts, split longer periods into hourly blocks
                    if is_short_term:
                        hourly_periods = set()
                        for period in periods:
                            period_parts = period.split('-')
                            if len(period_parts) == 2:
                                try:
                                    start = int(period_parts[0])
                                    end = int(period_parts[1])
                                    # Split into hourly blocks
                                    for hour in range(start, end):
                                        hourly_periods.add(f"{hour:02d}-{(hour+1):02d}")
                                except ValueError:
                                    self.warning(f"Invalid period format: {period}")
                                    continue
                        periods = sorted(list(hourly_periods))
                    # For medium-term forecasts, ensure we have all 6-hour blocks
                    elif is_medium_term:
                        # Always include all 6-hour blocks for medium-term forecasts
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
                            
                            # Calculate block duration
                            block_duration = timedelta(hours=period_end - period_start)
                            
                            # Create forecast time in local timezone
                            forecast_time = base_date.replace(hour=period_start, minute=0, second=0, microsecond=0)
                            
                            # Skip if outside requested range (using UTC times)
                            forecast_time_utc = forecast_time.astimezone(timezone.utc)
                            forecast_end_utc = forecast_time_utc + block_duration
                            # Include block if it overlaps with the requested time range
                            if not (forecast_end_utc > start_time_utc and forecast_time_utc < end_time_utc):
                                continue
                            
                            # Get temperature based on data format
                            temp = None
                            temp_data = day.get('temperatura')
                            
                            if isinstance(temp_data, list):
                                # Hourly format
                                for t in temp_data:
                                    if isinstance(t, dict):
                                        try:
                                            t_period = str(t.get('periodo', ''))
                                            # Handle both single hour and range formats
                                            if (t_period == str(period_start) or 
                                                t_period == f"{period_start:02d}" or 
                                                t_period == f"{period_start:02d}-{(period_start+1):02d}"):
                                                temp = float(t.get('value', 0))
                                                self.debug(
                                                    "Found matching temperature data",
                                                    period=period,
                                                    temp_period=t_period,
                                                    temp=temp
                                                )
                                                break
                                        except (ValueError, TypeError) as e:
                                            self.warning(
                                                "Invalid temperature value",
                                                error=str(e),
                                                period=period,
                                                data=t
                                            )
                            elif isinstance(temp_data, dict):
                                # Daily format
                                datos = temp_data.get('dato', [])
                                try:
                                    min_temp = float(temp_data.get('minima', 0))
                                    max_temp = float(temp_data.get('maxima', 0))
                                except (ValueError, TypeError) as e:
                                    self.warning(
                                        "Invalid min/max temperature values",
                                        error=str(e),
                                        data=temp_data
                                    )
                                    min_temp = max_temp = 0
                                
                                # First try to find exact hour match
                                for dato in datos:
                                    if isinstance(dato, dict):
                                        try:
                                            dato_hour = dato.get('hora')
                                            # Handle both integer and string hour formats
                                            if ((isinstance(dato_hour, int) and dato_hour == period_start) or
                                                (isinstance(dato_hour, str) and (
                                                    dato_hour == str(period_start) or
                                                    dato_hour == f"{period_start:02d}" or
                                                    dato_hour == f"{period_start:02d}-{(period_start+1):02d}"))):
                                                temp = float(dato.get('value', 0))
                                                self.debug(
                                                    "Found matching temperature in dato",
                                                    period=period,
                                                    dato_hour=dato_hour,
                                                    temp=temp
                                                )
                                                break
                                        except (ValueError, TypeError) as e:
                                            self.warning(
                                                "Invalid temperature value in dato",
                                                error=str(e),
                                                data=dato
                                            )
                                
                                # If no exact match, interpolate based on time of day
                                if temp is None:
                                    if period_start < 6:  # Night (00:00-06:00)
                                        temp = min_temp
                                    elif 11 <= period_start <= 15:  # Peak day (11:00-15:00)
                                        temp = max_temp
                                    elif 6 <= period_start < 11:  # Morning (06:00-11:00)
                                        progress = (period_start - 6) / 5
                                        temp = min_temp + (max_temp - min_temp) * progress
                                    else:  # Evening (15:00-00:00)
                                        progress = (period_start - 15) / 9
                                        temp = max_temp - (max_temp - min_temp) * progress
                                    self.debug(
                                        "Using interpolated temperature",
                                        period=period,
                                        temp=temp,
                                        min_temp=min_temp,
                                        max_temp=max_temp
                                    )
                            
                            if temp is None:
                                self.warning(
                                    "Could not determine temperature",
                                    period=period,
                                    period_start=period_start,
                                    temp_data=temp_data
                                )
                                temp = 0
                            
                            # Get precipitation data
                            precip_amount = 0.0
                            prob_precip = 0.0
                            
                            # Try hourly precipitation amount
                            precipitacion = day.get('precipitacion', [])
                            if isinstance(precipitacion, list):
                                for p in precipitacion:
                                    if isinstance(p, dict) and p.get('periodo') == str(period_start):
                                        try:
                                            precip_amount = float(p.get('value', 0))
                                            break
                                        except (ValueError, TypeError):
                                            self.warning("Invalid precipitation value", data=p)
                            
                            # Get precipitation probability
                            prob_precipitacion = day.get('probPrecipitacion', [])
                            if isinstance(prob_precipitacion, list):
                                for p in prob_precipitacion:
                                    if isinstance(p, dict):
                                        p_period = str(p.get('periodo', ''))
                                        # Handle both formats: "12" and "12-18"
                                        if p_period == str(period_start) or (
                                            '-' in p_period and 
                                            len(p_period.split('-')) == 2 and
                                            int(p_period.split('-')[0]) <= period_start < int(p_period.split('-')[1])
                                        ):
                                            try:
                                                prob_precip = float(p.get('value', 0))
                                                break
                                            except (ValueError, TypeError):
                                                self.warning("Invalid precipitation probability", data=p)
                            
                            # Get wind data
                            wind_speed = 0
                            wind_dir = 'C'
                            
                            # Try hourly format first (vientoAndRachaMax)
                            viento = day.get('vientoAndRachaMax', [])
                            if isinstance(viento, list):
                                for wind in viento:
                                    if isinstance(wind, dict):
                                        wind_period = wind.get('periodo')
                                        if wind_period == str(period_start):
                                            try:
                                                # Wind speed is in a list
                                                velocidades = wind.get('velocidad', [])
                                                if velocidades and isinstance(velocidades, list):
                                                    wind_speed = float(velocidades[0])
                                                # Wind direction is in a list
                                                direcciones = wind.get('direccion', [])
                                                if direcciones and isinstance(direcciones, list):
                                                    wind_dir = direcciones[0]
                                                self.debug(
                                                    "Found matching hourly wind data",
                                                    period=period,
                                                    wind_period=wind_period,
                                                    wind_speed=wind_speed,
                                                    wind_dir=wind_dir
                                                )
                                                break
                                            except (ValueError, TypeError, IndexError) as e:
                                                self.warning(
                                                    "Invalid hourly wind data",
                                                    error=str(e),
                                                    period=period,
                                                    wind_period=wind_period,
                                                    data=wind
                                                )
                            
                            # If no hourly data, try daily format (viento)
                            if wind_speed == 0:
                                viento = day.get('viento', [])
                                if isinstance(viento, list):
                                    for wind in viento:
                                        if isinstance(wind, dict):
                                            wind_period = wind.get('periodo', '')
                                            # Match period ranges (e.g., "06-12" contains hour 8)
                                            if wind_period and '-' in wind_period:
                                                try:
                                                    start_hour, end_hour = map(int, wind_period.split('-'))
                                                    if start_hour <= period_start < end_hour:
                                                        wind_speed = float(wind.get('velocidad', 0))
                                                        wind_dir = wind.get('direccion', 'C')
                                                        self.debug(
                                                            "Found matching daily wind data",
                                                            period=period,
                                                            wind_period=wind_period,
                                                            wind_speed=wind_speed,
                                                            wind_dir=wind_dir
                                                        )
                                                        break
                                                except (ValueError, TypeError) as e:
                                                    self.warning(
                                                        "Invalid daily wind data",
                                                        error=str(e),
                                                        period=period,
                                                        wind_period=wind_period,
                                                        data=wind
                                                    )
                            
                            # Get sky condition
                            sky_value = ''
                            if isinstance(estado_cielo, list):
                                for sky in estado_cielo:
                                    if isinstance(sky, dict) and sky.get('periodo') == period:
                                        sky_value = str(sky.get('value', ''))
                                        break
                            
                            # Map AEMET sky code to our internal code
                            summary_code = self._map_aemet_code(sky_value, period_start) if sky_value else 'clearsky_day'
                            
                            # Set block duration based on whether it's short-term or not
                            block_duration = timedelta(hours=1 if is_short_term else 6)

                            forecast = WeatherData(
                                temperature=float(temp),
                                precipitation=precip_amount,  # Use actual precipitation amount
                                precipitation_probability=prob_precip,
                                wind_speed=wind_speed / 3.6,  # Convert km/h to m/s
                                wind_direction=self._get_wind_direction(wind_dir),
                                symbol=summary_code,
                                elaboration_time=forecast_time_utc,
                                thunder_probability=0.0,
                                block_duration=block_duration
                            )
                            
                            forecasts.append(forecast)
                        except Exception as e:
                            self.warning(f"Failed to process period {period}: {e}")
                            continue
                except Exception as e:
                    self.warning(f"Failed to process day {day.get('fecha')}: {e}")
                    continue
        except Exception as e:
            self.error(f"Failed to parse daily forecast: {e}")
            return []
        else:
            return forecasts

    def _get_forecast(self, location: str, time: datetime) -> Optional[WeatherData]:
        """Get forecast for a specific time from cache or API."""
        # Check cache first
        fields = ['air_temperature', 'precipitation_amount', 'probability_of_precipitation',
                 'wind_speed', 'wind_from_direction', 'summary_code', 'probability_of_thunder',
                 'block_duration_hours']
        
        # Use data type based on hours ahead
        now_utc = datetime.now(ZoneInfo("UTC"))
        hours_ahead = (time - now_utc).total_seconds() / 3600
        
        # Determine forecast interval based on how far ahead we're looking
        if hours_ahead <= self.HOURLY_RANGE:
            interval = 1  # Hourly forecasts for first 48 hours
            data_type = 'hourly'
        elif hours_ahead <= self.SIX_HOURLY_RANGE:
            interval = 6  # 6-hourly forecasts for next 2 days
            data_type = 'daily'
        else:
            interval = 12  # 12-hourly forecasts beyond that
            data_type = 'daily'
        
        # Align time to block boundaries
        aligned_time = time.replace(minute=0, second=0, microsecond=0)
        if interval > 1:
            block_start = ((aligned_time.hour) // interval) * interval
            aligned_time = aligned_time.replace(hour=block_start)
        
        # Log cache lookup details
        self.debug(
            "Looking up in cache",
            location=location,
            time=time.isoformat(),
            aligned_time=aligned_time.isoformat(),
            data_type=data_type,
            interval=interval,
            hours_ahead=hours_ahead
        )
        
        # Look up just the single time we need
        cached_data = self.db.get_weather_data(location, [aligned_time.isoformat()], data_type, fields)
        
        # Log what we got from cache
        self.debug(
            "Cache lookup result",
            location=location,
            time=aligned_time.isoformat(),
            data_type=data_type,
            found=bool(cached_data),
            cache_keys=list(cached_data.keys()) if cached_data else None
        )
        
        if cached_data and aligned_time.isoformat() in cached_data:
            self.info(
                "Cache hit",
                location=location,
                time=aligned_time.isoformat(),
                data_type=data_type,
                interval=interval
            )
            data = cached_data[aligned_time.isoformat()]
            return WeatherData(
                temperature=data['air_temperature'],
                precipitation=data['precipitation_amount'],
                precipitation_probability=data['probability_of_precipitation'],
                wind_speed=data['wind_speed'],
                wind_direction=data['wind_from_direction'],
                symbol=data['summary_code'],
                elaboration_time=aligned_time,
                thunder_probability=data['probability_of_thunder'],
                block_duration=timedelta(hours=data.get('block_duration_hours', interval))
            )
        
        # If not in cache, fetch from API
        self.info(
            "Cache miss",
            location=location,
            time=aligned_time.isoformat(),
            data_type=data_type,
            interval=interval
        )
        lat, lon = map(float, location.split(','))
        
        # Fetch a larger time range to store more forecasts
        fetch_start = aligned_time
        fetch_end = aligned_time + timedelta(hours=48 if hours_ahead <= self.HOURLY_RANGE else 168)  # 48h for short-term, 7 days for medium/long
        
        forecasts = self._fetch_forecasts(lat, lon, fetch_start, fetch_end)
        if forecasts:
            # Calculate expiry time based on AEMET's update schedule
            current_hour = datetime.now(self.utc_tz).hour
            update_hours = [3, 9, 15, 21]  # AEMET update times (UTC)
            next_update_hour = next((hour for hour in update_hours if hour > current_hour), update_hours[0])
            
            if next_update_hour <= current_hour:
                # If we're past all update times today, next update is tomorrow
                expires = (datetime.now(self.utc_tz) + timedelta(days=1)).replace(hour=update_hours[0], minute=0, second=0, microsecond=0)
            else:
                expires = datetime.now(self.utc_tz).replace(hour=next_update_hour, minute=0, second=0, microsecond=0)
            
            # Store all forecasts in cache
            cache_entries = []
            for forecast in forecasts:
                cache_entry = {
                    'location': location,
                    'time': forecast.elaboration_time.isoformat(),
                    'data_type': data_type,
                    'air_temperature': forecast.temperature,
                    'precipitation_amount': forecast.precipitation,
                    'probability_of_precipitation': forecast.precipitation_probability,
                    'wind_speed': forecast.wind_speed,
                    'wind_from_direction': forecast.wind_direction,
                    'summary_code': forecast.symbol,
                    'probability_of_thunder': forecast.thunder_probability,
                    'block_duration_hours': interval
                }
                cache_entries.append(cache_entry)
            
            # Log what we're storing in cache
            self.debug(
                "Storing in cache",
                location=location,
                time_range=f"{fetch_start.isoformat()} to {fetch_end.isoformat()}",
                data_type=data_type,
                expires=expires.isoformat(),
                forecast_count=len(cache_entries)
            )
            
            self.db.store_weather_data(
                cache_entries,
                expires=expires.isoformat(),
                last_modified=datetime.now(self.utc_tz).isoformat()
            )
            
            # Find and return the forecast for the requested time
            for forecast in forecasts:
                if forecast.elaboration_time == aligned_time:
                    forecast.block_duration = timedelta(hours=interval)
                    return forecast
        
        return None

    def _parse_response(
        self,
        response_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        interval: int
    ) -> Optional[WeatherResponse]:
        """Parse raw API response into WeatherData objects."""
        try:
            forecasts = []
            
            # Extract forecast data from response
            hourly_data = response_data.get('hourly_forecasts', [])
            daily_data = response_data.get('daily_forecasts', [])
            
            # Process hourly forecasts
            for forecast in hourly_data:
                time = datetime.fromisoformat(forecast['time'])
                if time < start_time or time > end_time:
                    continue
                    
                weather_data = WeatherData(
                    temperature=forecast['temperature'],
                    precipitation=forecast['precipitation'],
                    precipitation_probability=forecast['precipitation_probability'],
                    wind_speed=forecast['wind_speed'],
                    wind_direction=forecast['wind_direction'],
                    symbol=WeatherCode(forecast['symbol']),
                    elaboration_time=time,
                    thunder_probability=forecast.get('thunder_probability', 0),
                    block_duration=timedelta(hours=1)
                )
                forecasts.append(weather_data)
            
            # Process daily forecasts
            for forecast in daily_data:
                time = datetime.fromisoformat(forecast['time'])
                if time < start_time or time > end_time:
                    continue
                    
                weather_data = WeatherData(
                    temperature=forecast['temperature'],
                    precipitation=forecast['precipitation'],
                    precipitation_probability=forecast['precipitation_probability'],
                    wind_speed=forecast['wind_speed'],
                    wind_direction=forecast['wind_direction'],
                    symbol=WeatherCode(forecast['symbol']),
                    elaboration_time=time,
                    thunder_probability=forecast.get('thunder_probability', 0),
                    block_duration=timedelta(hours=interval)
                )
                forecasts.append(weather_data)
            
            if not forecasts:
                self.warning(
                    "No forecasts found in response for requested time range",
                    time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
                )
                return None
            
            # Sort forecasts by time
            forecasts.sort(key=lambda x: x.elaboration_time)
            
            return WeatherResponse(data=forecasts, expires=datetime.now(self.utc_tz) + timedelta(hours=1))
            
        except Exception as e:
            self.error("Error parsing weather response", error=str(e))
            return None

    def _fetch_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch data from AEMET API."""
        try:
            # Get data URL from API
            response = requests.get(url, headers=self.headers, timeout=10)
            self._last_api_call = datetime.now(ZoneInfo("UTC"))
            
            if response.status_code == 429:  # Too Many Requests
                self.error(
                    "Rate limit exceeded",
                    retry_after=response.headers.get('Retry-After', 60)
                )
                return None
            
            if response.status_code != 200:
                self.error(
                    "API request failed",
                    status=response.status_code,
                    url=url
                )
                return None
            
            data = response.json()
            if not data or 'datos' not in data:
                self.error("Invalid API response format", data=data)
                return None
            
            # Get actual forecast data
            forecast_response = requests.get(data['datos'], headers=self.headers, timeout=10)
            
            if forecast_response.status_code != 200:
                self.error(
                    "Forecast data request failed",
                    status=forecast_response.status_code,
                    url=data['datos']
                )
                return None
            
            forecast_data = forecast_response.json()
            if not forecast_data:
                self.error("Invalid forecast data format", data=forecast_data)
                return None
            
            # Check if response indicates an error
            if isinstance(forecast_data, dict) and forecast_data.get('estado') == 404:
                self.error(
                    "API returned error response",
                    error=forecast_data.get('descripcion', 'Unknown error')
                )
                return None
            
            return forecast_data[0] if isinstance(forecast_data, list) else forecast_data
            
        except requests.exceptions.Timeout:
            self.error("API request timed out", url=url)
            return None
        except requests.exceptions.RequestException as e:
            self.error("API request failed", error=str(e), url=url)
            return None
        except Exception as e:
            self.error("Error fetching data", error=str(e), url=url)
            return None

    def _is_in_coverage_area(self, lat: float, lon: float) -> bool:
        """Check if coordinates are within Spain's territory.
        
        Coverage areas:
        - Mainland Spain: 35.9N to 43.8N, 9.4W to 3.4E
        - Canary Islands: 27.6N to 29.5N, 18.2W to 13.3W
        - Balearic Islands: 38.6N to 40.1N, 1.1E to 4.4E
        """
        # Mainland Spain
        if (35.9 <= lat <= 43.8 and -9.4 <= lon <= 3.4):
            return True
        # Canary Islands
        if (27.6 <= lat <= 29.5 and -18.2 <= lon <= -13.3):
            return True
        # Balearic Islands
        if (38.6 <= lat <= 40.1 and 1.1 <= lon <= 4.4):
            return True
        return False

    def _parse_dms_to_decimal(self, dms_str: str) -> float:
        """Convert DMS (degrees, minutes, seconds) string to decimal degrees."""
        try:
            # Remove the degree symbol and quotes
            dms_str = dms_str.replace('º', ' ').replace('"', ' ').replace("'", ' ')
            parts = dms_str.split()
            
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            
            decimal = degrees + minutes/60 + seconds/3600
            return decimal
        except (ValueError, IndexError) as e:
            self.error(f"Failed to parse DMS coordinate: {dms_str}", exc_info=e)
            return None

    def _parse_location_data(self, data: dict) -> Optional[Location]:
        """Parse location data from AEMET API response."""
        try:
            # Use decimal coordinates directly if available
            lat = float(data.get('latitud_dec', 0))
            lon = float(data.get('longitud_dec', 0))
            
            # If decimal coordinates are 0, try parsing DMS format
            if lat == 0 and 'latitud' in data:
                lat = self._parse_dms_to_decimal(data['latitud'])
            if lon == 0 and 'longitud' in data:
                lon = self._parse_dms_to_decimal(data['longitud'])
            
            if lat is None or lon is None:
                return None
            
            return Location(
                id=data['id'],
                name=data['nombre'],
                latitude=lat,
                longitude=lon,
                altitude=float(data['altitud']),
                region=data.get('zona_comarcal', '')
            )
        except (ValueError, KeyError) as e:
            self.error(f"Failed to parse location data", exc_info=e, data=data)
            return None
