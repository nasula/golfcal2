"""Weather service for Iberian region."""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import requests

from golfcal2.utils.logging_utils import log_execution
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import IBERIAN_SCHEMA
from golfcal2.services.weather_types import WeatherService, WeatherData, WeatherCode
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

class IberianWeatherService(WeatherService):
    """Service for handling weather data for Iberian region."""

    BASE_URL = "https://opendata.aemet.es/opendata/api"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz, utc_tz):
        """Initialize service with API endpoints and credentials."""
        super().__init__(local_tz, utc_tz)
        
        with handle_errors(WeatherError, "iberian_weather", "initialize service"):
            # API configuration
            settings = load_config()
            self.api_key = settings.global_config.get('api_keys', {}).get('weather', {}).get('aemet')
            if not self.api_key:
                error = WeatherError(
                    "AEMET API key not configured in config.yaml",
                    ErrorCode.CONFIG_MISSING,
                    {"setting": "api_keys.weather.aemet"}
                )
                aggregate_error(str(error), "iberian_weather", None)
                raise error
            
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
        with handle_errors(
            WeatherError,
            "iberian_weather",
            f"fetch forecasts for coordinates ({lat}, {lon})",
            lambda: []  # Fallback to empty list on error
        ):
            if not self.api_key:
                error = WeatherError(
                    "AEMET API key not configured",
                    ErrorCode.CONFIG_MISSING,
                    {"setting": "api_keys.weather.aemet"}
                )
                aggregate_error(str(error), "iberian_weather", None)
                return []

            # Get weather data from AEMET API
            forecast_url = f"{self.endpoint}/prediccion/especifica/municipio/horaria"
            params = {
                'lat': lat,
                'lon': lon,
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
            
            try:
                response = requests.get(
                    forecast_url,
                    params=params,
                    headers=self.headers,
                    timeout=10
                )
                
                self._last_api_call = datetime.now()
                
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
                if not data or 'datos' not in data:
                    error = WeatherError(
                        "Invalid response format from AEMET API",
                        ErrorCode.INVALID_RESPONSE,
                        {"response": data}
                    )
                    aggregate_error(str(error), "iberian_weather", None)
                    return []

                # Get actual forecast data
                forecast_response = requests.get(
                    data['datos'],
                    headers=self.headers,
                    timeout=10
                )
                
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

                forecasts = []
                for period in forecast_data[0].get('prediccion', {}).get('dia', []):
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
                                hour = int(hour_data.get('hora', '0').split('-')[0])
                                forecast_time = base_date.replace(hour=hour)
                                
                                # Skip if outside our time range
                                if forecast_time < start_time or forecast_time > end_time:
                                    continue
                                
                                # Extract weather data
                                temp = hour_data.get('temperatura')
                                precip = hour_data.get('precipitacion')
                                wind = hour_data.get('viento', [{}])[0]
                                sky = hour_data.get('estadoCielo', '')
                                
                                # Map AEMET codes to our codes
                                try:
                                    symbol_code = self._map_aemet_code(sky, hour)
                                except Exception as e:
                                    error = WeatherError(
                                        f"Failed to map weather code: {str(e)}",
                                        ErrorCode.VALIDATION_FAILED,
                                        {
                                            "code": sky,
                                            "hour": hour,
                                            "forecast_time": forecast_time.isoformat()
                                        }
                                    )
                                    aggregate_error(str(error), "iberian_weather", e.__traceback__)
                                    continue

                                # Calculate thunder probability based on weather code
                                thunder_prob = 0.0
                                if 'tormenta' in sky.lower():  # 'tormenta' means thunderstorm in Spanish
                                    # Extract intensity from description
                                    if 'fuerte' in sky.lower():  # 'fuerte' means strong
                                        thunder_prob = 80.0
                                    elif 'débil' in sky.lower():  # 'débil' means weak
                                        thunder_prob = 20.0
                                    else:
                                        thunder_prob = 50.0

                                forecast_data = WeatherData(
                                    temperature=float(temp) if temp else None,
                                    precipitation=float(precip) if precip else 0.0,
                                    precipitation_probability=hour_data.get('probPrecipitacion', 0.0),
                                    wind_speed=float(wind.get('velocidad', 0)) / 3.6,  # Convert km/h to m/s
                                    wind_direction=self._get_wind_direction(wind.get('direccion')),
                                    symbol=symbol_code,
                                    elaboration_time=forecast_time,
                                    thunder_probability=thunder_prob
                                )
                                forecasts.append(forecast_data)

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