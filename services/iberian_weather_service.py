"""Service for handling weather data for Iberian region."""

import os
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
import math

from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_types import WeatherData, WeatherCode
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import IBERIAN_SCHEMA
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
            
            # Initialize database
            self.db = WeatherDatabase('iberian_weather', IBERIAN_SCHEMA)
            
            # Rate limiting configuration
            self._last_api_call = None
            self._min_call_interval = timedelta(seconds=1)
            self._last_request_time = 0
            
            self.set_log_context(service="IberianWeatherService")
    
    @log_execution(level='DEBUG', include_args=True)
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Get weather data for a specific time and location."""
        self.debug(">>> TEST DEBUG: Entering get_weather", lat=lat, lon=lon)
        
        with handle_errors(
            WeatherError,
            "iberian_weather",
            f"get weather for coordinates ({lat}, {lon})",
            lambda: []  # Fallback to empty list on error
        ):
            # Check cache first
            location = f"{lat},{lon}"
            times = [
                t.strftime("%Y-%m-%d %H:%M:%S")
                for t in [start_time + timedelta(hours=i) for i in range(24)]
            ]
            
            self.debug(
                "Checking cache",
                location=location,
                start=start_time.isoformat(),
                end=end_time.isoformat()
            )
            
            cached_data = self.db.get_weather_data(
                location=location,
                times=times,
                data_type="daily",
                fields=[
                    'air_temperature',
                    'precipitation_amount',
                    'wind_speed',
                    'wind_from_direction',
                    'probability_of_precipitation',
                    'probability_of_thunder',
                    'summary_code'
                ]
            )
            
            if cached_data:
                self.debug(f"Found {len(cached_data)} cached entries")
                return self._convert_cached_data(cached_data)
            
            # Fetch new data if not in cache
            self.debug("No cached data found, fetching from API")
            forecasts = self._fetch_forecasts(lat, lon, start_time, end_time)
            
            if forecasts:
                # Store in cache
                self.debug(f"Storing {len(forecasts)} forecasts in cache")
                cache_data = []
                for forecast in forecasts:
                    cache_entry = {
                        'location': location,
                        'time': forecast.elaboration_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'data_type': 'daily',
                        'air_temperature': forecast.temperature,
                        'precipitation_amount': forecast.precipitation,
                        'wind_speed': forecast.wind_speed,
                        'wind_from_direction': forecast.wind_direction,
                        'probability_of_precipitation': forecast.precipitation_probability,
                        'probability_of_thunder': forecast.thunder_probability,
                        'summary_code': forecast.symbol
                    }
                    cache_data.append(cache_entry)
                
                # Calculate expiration (next update time)
                now = datetime.now(self.utc_tz)
                expires = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                
                self.db.store_weather_data(
                    cache_data,
                    expires=expires.strftime("%Y-%m-%d %H:%M:%S"),
                    last_modified=now.strftime("%Y-%m-%d %H:%M:%S")
                )
            
            return forecasts

    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch forecasts from AEMET API."""
        # Debug call before handle_errors
        self.debug(">>> TEST DEBUG: Before handle_errors in _fetch_forecasts")
        
        with handle_errors(
            WeatherError,
            "iberian_weather",
            f"fetch forecasts for coordinates ({lat}, {lon})",
            lambda: []  # Fallback to empty list on error
        ):
            # Test debug call to verify code path
            self.debug(">>> TEST DEBUG: Inside handle_errors in _fetch_forecasts")
            self.debug(">>> TEST DEBUG: Entering _fetch_forecasts", lat=lat, lon=lon)
            
            if not self.api_key:
                error = WeatherError(
                    "AEMET API key not configured",
                    ErrorCode.CONFIG_MISSING,
                    {"setting": "api_keys.weather.aemet"}
                )
                aggregate_error(str(error), "iberian_weather", None)
                return []

            # First, get the municipality code for the coordinates
            municipality_url = f"{self.endpoint}/maestro/municipios"
            self.debug(
                ">>> TEST DEBUG: Starting municipality request",
                url=municipality_url,
                headers=self.headers,
                lat=lat,
                lon=lon
            )
            
            try:
                response = requests.get(
                    municipality_url,
                    headers=self.headers,
                    timeout=10
                )
                
                self.debug(
                    ">>> TEST DEBUG: Municipality response",
                    status=response.status_code,
                    content_type=response.headers.get('content-type'),
                    content_length=len(response.content)
                )
                
                if response.status_code != 200:
                    error = APIResponseError(
                        f"AEMET municipality list request failed with status {response.status_code}",
                        response=response
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                initial_data = response.json()
                
                # Debug the initial response
                self.debug(
                    "Got initial response",
                    response_type=type(initial_data).__name__,
                    response_data=initial_data
                )
                
                if not isinstance(initial_data, dict) or 'datos' not in initial_data:
                    error = WeatherError(
                        "Invalid initial response format from AEMET API",
                        ErrorCode.INVALID_RESPONSE,
                        {"response": initial_data}
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                # Get the actual municipality list from the datos URL
                municipality_data_url = initial_data['datos']
                self.debug("Fetching municipality list from", url=municipality_data_url)
                
                municipality_response = requests.get(
                    municipality_data_url,
                    headers=self.headers,
                    timeout=10
                )
                
                if municipality_response.status_code != 200:
                    error = APIResponseError(
                        f"AEMET municipality data request failed with status {municipality_response.status_code}",
                        response=municipality_response
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                municipalities = municipality_response.json()
                
                # Debug the municipality response
                self.debug(
                    "Got municipality list response",
                    response_type=type(municipalities).__name__,
                    response_length=len(municipalities) if isinstance(municipalities, (list, dict)) else 0,
                    sample_data=str(municipalities)[:200] if municipalities else None
                )
                
                # Find the nearest municipality
                nearest_municipality = None
                min_distance = float('inf')
                
                if not isinstance(municipalities, list):
                    self.error(
                        "Invalid municipality data format",
                        expected_type="list",
                        actual_type=type(municipalities).__name__,
                        data_sample=str(municipalities)[:200] if municipalities else None
                    )
                    return []

                self.debug(f"Processing {len(municipalities)} municipalities")
                processed = 0
                
                for municipality in municipalities:
                    try:
                        # Use latitud_dec and longitud_dec fields
                        mun_lat = float(municipality.get('latitud_dec', 0))
                        mun_lon = float(municipality.get('longitud_dec', 0))
                        
                        # Calculate distance using Haversine formula
                        distance = self._haversine_distance(lat, lon, mun_lat, mun_lon)
                        
                        if distance < min_distance:
                            min_distance = distance
                            nearest_municipality = municipality
                            self.debug(
                                "Found closer municipality",
                                name=municipality.get('nombre', 'unknown'),
                                url=municipality.get('url', 'unknown'),
                                distance_km=distance,
                                municipality_lat=mun_lat,
                                municipality_lon=mun_lon
                            )
                        
                        processed += 1
                        if processed % 1000 == 0:  # Log progress every 1000 municipalities
                            self.debug(f"Processed {processed} municipalities")
                            
                    except (ValueError, TypeError) as e:
                        self.warning(
                            "Failed to process municipality",
                            error=str(e),
                            municipality_data=municipality
                        )
                        continue

                if not nearest_municipality:
                    self.warning(
                        "No municipality found near coordinates",
                        latitude=lat,
                        longitude=lon,
                        total_processed=processed
                    )
                    return []

                # Use the URL field for the municipality code
                municipality_code = nearest_municipality.get('url', '')
                if not municipality_code:
                    self.warning(
                        "Municipality has no URL",
                        municipality=nearest_municipality
                    )
                    return []

                # Extract the numeric ID from the URL (e.g., "vilobi-d-onyar-id17233" -> "17233")
                numeric_id = municipality_code.split('-id')[-1] if '-id' in municipality_code else None
                if not numeric_id:
                    self.warning(
                        "Could not extract numeric ID from municipality URL",
                        url=municipality_code
                    )
                    return []

                # Format the municipality code correctly (AEMET requires leading zeros)
                numeric_id = numeric_id.zfill(5)  # Ensure 5 digits with leading zeros

                self.debug(
                    "Found nearest municipality",
                    municipality=nearest_municipality.get('nombre', 'unknown'),
                    code=numeric_id,
                    distance_km=min_distance
                )

                # Now get the weather forecast for this municipality
                forecast_url = f"{self.endpoint}/prediccion/especifica/municipio/horaria/{numeric_id}"
                
                self.debug(
                    "AEMET URL",
                    url=forecast_url,
                    municipality_id=numeric_id,
                    municipality_name=nearest_municipality.get('nombre', 'unknown')
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

                if response.status_code == 404:  # Not Found - no data available
                    self.warning(
                        "No forecasts found",
                        latitude=lat,
                        longitude=lon,
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat(),
                        time_range=f"{start_time} to {end_time}"
                    )
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
                        "No forecasts found",
                        latitude=lat,
                        longitude=lon,
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat(),
                        time_range=f"{start_time} to {end_time}"
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

                # Add detailed debug logging
                self.debug(
                    "Received forecast data",
                    data_type=type(forecast_data).__name__,
                    data_length=len(forecast_data) if isinstance(forecast_data, (list, dict)) else 0,
                    data=json.dumps(forecast_data, indent=2),  # Log the entire response
                    url=data['datos']  # Log the URL we fetched from
                )

                forecasts = []
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
                    "First forecast entry structure",
                    prediccion=json.dumps(forecast_data[0].get('prediccion', {}), indent=2),
                    dias=len(forecast_data[0].get('prediccion', {}).get('dia', [])),
                    nombre=forecast_data[0].get('nombre', 'unknown'),
                    provincia=forecast_data[0].get('provincia', 'unknown')
                )

                # Process each day's forecast
                for dia in forecast_data[0].get('prediccion', {}).get('dia', []):
                    try:
                        # Get date
                        date_str = dia.get('fecha')
                        if not date_str:
                            continue
                        
                        # AEMET provides dates in local time
                        base_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                        # Convert to UTC first, then to the target timezone
                        if abs(lon) > 15:  # Canary Islands
                            base_date = base_date.replace(tzinfo=ZoneInfo('Atlantic/Canary'))
                        else:  # Mainland Spain
                            base_date = base_date.replace(tzinfo=ZoneInfo('Europe/Madrid'))
                        
                        self.debug(
                            "Processing date",
                            date=date_str,
                            base_date=base_date.isoformat(),
                            timezone=str(base_date.tzinfo)
                        )
                    
                        # Process hourly data
                        hourly_data = dia.get('temperatura', [])
                        self.debug(
                            "Processing temperature data",
                            count=len(hourly_data),
                            sample=json.dumps(hourly_data[:2], indent=2)
                        )
                        
                        for hour_data in hourly_data:
                            try:
                                # Get hour
                                hour_str = hour_data.get('periodo')
                                if not hour_str:
                                    continue
                                
                                hour = int(hour_str)
                                forecast_time = base_date.replace(hour=hour)
                                
                                # Skip if outside our time range
                                if forecast_time < start_time or forecast_time > end_time:
                                    continue
                                
                                # Get temperature
                                temp = float(hour_data.get('value', 0))
                                
                                # Find precipitation data
                                precip_data = next(
                                    (p for p in dia.get('precipitacion', [])
                                     if p.get('periodo') == hour_str),
                                    {'value': '0'}
                                )
                                precip_value = precip_data.get('value', '0')
                                # Handle 'Ip' (trace precipitation) as 0.1 mm
                                precip = 0.1 if precip_value == 'Ip' else float(precip_value)
                                
                                # Find probability data - periods are in 6-hour blocks
                                period_start = (hour // 6) * 6
                                period_end = ((hour // 6) + 1) * 6
                                period_str = f"{period_start:02d}{period_end:02d}"
                                
                                prob_data = next(
                                    (p for p in dia.get('probPrecipitacion', [])
                                     if p.get('periodo') == period_str),
                                    {'value': '0'}
                                )
                                prob_precip = float(prob_data.get('value', 0))
                                
                                # Find wind data
                                wind_data = next(
                                    (w for w in dia.get('vientoAndRachaMax', [])
                                     if w.get('periodo') == hour_str and 'direccion' in w),
                                    {}
                                )
                                
                                wind_speed = float(wind_data.get('velocidad', [0])[0]) / 3.6  # Convert km/h to m/s
                                wind_direction = wind_data.get('direccion', [''])[0]
                                
                                # Find sky condition
                                sky_data = next(
                                    (s for s in dia.get('estadoCielo', [])
                                     if s.get('periodo') == hour_str),
                                    {}
                                )
                                sky_code = sky_data.get('value', '')
                                sky_desc = sky_data.get('descripcion', '')
                                
                                self.debug(
                                    "Processed hourly data",
                                    time=forecast_time.isoformat(),
                                    temp=temp,
                                    precip=precip,
                                    prob_precip=prob_precip,
                                    wind_speed=wind_speed,
                                    wind_direction=wind_direction,
                                    sky_code=sky_code,
                                    sky_desc=sky_desc
                                )
                                
                                # Map AEMET codes to our codes
                                symbol_code = self._map_aemet_code(sky_code, hour)
                                
                                # Calculate thunder probability based on description
                                thunder_prob = 0.0
                                if 'tormenta' in sky_desc.lower():
                                    thunder_prob = 50.0

                                forecast = WeatherData(
                                    temperature=temp,
                                    precipitation=precip,
                                    precipitation_probability=prob_precip,
                                    wind_speed=wind_speed,
                                    wind_direction=self._get_wind_direction(wind_direction),
                                    symbol=symbol_code,
                                    elaboration_time=forecast_time,
                                    thunder_probability=thunder_prob
                                )
                                forecasts.append(forecast)
                                
                                self.debug(
                                    "Added forecast",
                                    time=forecast_time.isoformat(),
                                    temp=temp,
                                    precip=precip,
                                    wind=wind_speed,
                                    symbol=symbol_code
                                )
                                
                            except (ValueError, IndexError, KeyError) as e:
                                self.warning(
                                    "Failed to process hour",
                                    hour=hour_str if 'hour_str' in locals() else 'unknown',
                                    error=str(e),
                                    data=hour_data
                                )
                                continue
                    except Exception as e:
                        self.warning(
                            "Failed to process day",
                            error=str(e),
                            data=dia
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
    
    def _get_wind_direction(self, direction: Optional[str]) -> Optional[float]:
        """Convert AEMET wind direction to degrees."""
        with handle_errors(
            WeatherError,
            "iberian_weather",
            f"get wind direction from {direction}",
            lambda: None  # Fallback to None on error
        ):
            if not direction:
                return None
                
            # Map cardinal directions to degrees
            direction_map = {
                'N': 0.0,
                'NNE': 22.5,
                'NE': 45.0,
                'ENE': 67.5,
                'E': 90.0,
                'ESE': 112.5,
                'SE': 135.0,
                'SSE': 157.5,
                'S': 180.0,
                'SSW': 202.5,
                'SW': 225.0,
                'WSW': 247.5,
                'W': 270.0,
                'WNW': 292.5,
                'NW': 315.0,
                'NNW': 337.5
            }
            
            return direction_map.get(direction.upper())

    def _convert_cached_data(self, cached_data: Dict[str, Dict[str, Any]]) -> List[WeatherData]:
        """Convert cached data back to WeatherData objects."""
        self.debug("Converting cached data to WeatherData objects")
        forecasts = []
        
        for time_str, data in cached_data.items():
            try:
                forecast_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=self.utc_tz)
                
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