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
        """Initialize service.
        
        Args:
            local_tz: Local timezone
            utc_tz: UTC timezone
            config: Application configuration
        """
        super().__init__(local_tz, utc_tz)
        
        # Configure logger
        for handler in self.logger.handlers:
            handler.set_name('iberian_weather')  # Ensure unique handler names
        
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
                "Getting municipality list",
                url=municipality_url
            )
            
            try:
                response = requests.get(
                    municipality_url,
                    headers=self.headers,
                    timeout=10
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
                params = {
                    'api_key': self.api_key
                }
            
                self.debug(
                    "AEMET URL",
                    url=forecast_url,
                    params=params
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
                    data_sample=json.dumps(forecast_data)[:500]  # Log first 500 chars of the response
                )

                forecasts = []
                if not isinstance(forecast_data, list) or not forecast_data:
                    self.warning(
                        "Unexpected forecast data format",
                        expected="non-empty list",
                        actual_type=type(forecast_data).__name__,
                        data_sample=json.dumps(forecast_data)[:200]
                    )
                    return []

                for period in forecast_data[0].get('prediccion', {}).get('dia', []):
                    self.debug(
                        "Processing forecast period",
                        period_data=json.dumps(period)[:200]
                    )
                    with handle_errors(
                        WeatherError,
                        "iberian_weather",
                        "process forecast period",
                        lambda: None
                    ):
                        # Get date
                        date_str = period.get('fecha')
                        if not date_str:
                            continue
                        
                        base_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=self.utc_tz)
                    
                        # Process hourly data
                        for hour_data in period.get('hora', []):
                            with handle_errors(
                                WeatherError,
                                "iberian_weather",
                                "process hourly forecast",
                                lambda: None
                            ):
                                # Get hour
                                hour_str = hour_data.get('hora', '0').split('-')[0]
                                try:
                                    hour = int(hour_str)
                                except ValueError:
                                    self.warning(
                                        "Invalid hour format",
                                        hour_str=hour_str,
                                        hour_data=hour_data
                                    )
                                    continue

                                forecast_time = base_date.replace(hour=hour)
                                
                                # Skip if outside our time range
                                if forecast_time < start_time or forecast_time > end_time:
                                    continue
                                
                                # Extract weather data
                                temp = float(hour_data.get('temperatura', 0))
                                precip = float(hour_data.get('precipitacion', 0))
                                prob_precip = float(hour_data.get('probPrecipitacion', 0))
                                
                                # Get wind data
                                wind_data = hour_data.get('vientoAndRachaMax', [{}])[0]
                                wind_speed = float(wind_data.get('velocidad', 0)) / 3.6  # Convert km/h to m/s
                                wind_direction = wind_data.get('direccion')
                                
                                # Get sky condition
                                sky_data = hour_data.get('estadoCielo', {})
                                sky_code = sky_data.get('value', '') if isinstance(sky_data, dict) else sky_data
                                
                                # Map AEMET codes to our codes
                                try:
                                    symbol_code = self._map_aemet_code(sky_code, hour)
                                except Exception as e:
                                    error = WeatherError(
                                        f"Failed to map weather code: {str(e)}",
                                        ErrorCode.VALIDATION_FAILED,
                                        {
                                            "code": sky_code,
                                            "hour": hour,
                                            "forecast_time": forecast_time.isoformat()
                                        }
                                    )
                                    aggregate_error(str(error), "iberian_weather", e.__traceback__)
                                    continue

                                # Calculate thunder probability based on weather code
                                thunder_prob = 0.0
                                if 'tormenta' in sky_data.get('descripcion', '').lower():
                                    thunder_prob = 50.0

                                forecast_data = WeatherData(
                                    temperature=temp,
                                    precipitation=precip,
                                    precipitation_probability=prob_precip,
                                    wind_speed=wind_speed,
                                    wind_direction=self._get_wind_direction(wind_direction),
                                    symbol=symbol_code,
                                    elaboration_time=forecast_time,
                                    thunder_probability=thunder_prob
                                )
                                forecasts.append(forecast_data)
                                
                                self.debug(
                                    "Added forecast",
                                    time=forecast_time.isoformat(),
                                    temp=temp,
                                    precip=precip,
                                    wind=wind_speed,
                                    symbol=symbol_code
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
        """Map AEMET weather codes to our internal codes."""
        with handle_errors(
            WeatherError,
            "iberian_weather",
            f"map weather code {code}",
            lambda: WeatherCode.CLOUDY  # Fallback to cloudy on error
        ):
            # Implementation of the mapping logic
            # This is just a placeholder - you'll need to implement the actual mapping
            return WeatherCode.CLOUDY
    
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