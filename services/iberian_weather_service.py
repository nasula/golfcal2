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

class IberianWeatherService(WeatherService):
    """Service for handling weather data for Iberian region."""

    BASE_URL = "https://opendata.aemet.es/opendata/api"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz, utc_tz):
        """Initialize service with API endpoints and credentials."""
        super().__init__(local_tz, utc_tz)
        
        # API configuration
        self.api_key = os.getenv('AEMET_API_KEY', 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqYXJra28uYWhvbmVuQGlraS5maSIsImp0aSI6IjNiMjM2ZDY4LTY4ZDAtNDY5Ni1iMjE4LTJiZjM4ZmM5ZjE4YiIsImlzcyI6IkFFTUVUIiwiaWF0IjoxNjk5NzE2NjI3LCJ1c2VySWQiOiIzYjIzNmQ2OC02OGQwLTQ2OTYtYjIxOC0yYmYzOGZjOWYxOGIiLCJyb2xlIjoiIn0.Ry8uRDVHGYhcEG_4G3UDVXKmHhwR0TVKqvYuKPvjnYY')
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
        try:
            if not self.api_key:
                self.error("AEMET API key not configured")
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
            
            response = requests.get(
                forecast_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            self._last_api_call = datetime.now()
            
            if response.status_code != 200:
                self.error(
                    "AEMET API request failed",
                    status_code=response.status_code,
                    response=response.text
                )
                return []

            data = response.json()
            if not data or 'datos' not in data:
                self.error("Invalid response format from AEMET API")
                return []

            # Get actual forecast data
            forecast_response = requests.get(
                data['datos'],
                headers=self.headers,
                timeout=10
            )
            
            if forecast_response.status_code != 200:
                self.error(
                    "AEMET forecast data request failed",
                    status_code=forecast_response.status_code,
                    response=forecast_response.text
                )
                return []

            forecast_data = forecast_response.json()
            if not forecast_data:
                self.error("Invalid forecast data format from AEMET API")
                return []

            forecasts = []
            for period in forecast_data[0].get('prediccion', {}).get('dia', []):
                try:
                    # Get date
                    date_str = period.get('fecha')
                    if not date_str:
                        continue
                    
                    base_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=self.utc_tz)
                
                # Process hourly data
                    for hour_data in period.get('hora', []):
                        try:
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
                                self.warning(
                                    "Failed to map weather code",
                                    code=sky,
                                    hour=hour,
                                    exc_info=str(e)
                                )
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
                            
                        except (KeyError, ValueError) as e:
                            self.warning(f"Failed to parse hour data: {e}")
                        continue
            
                except (KeyError, ValueError) as e:
                    self.warning(f"Failed to parse period data: {e}")
                    continue

            return forecasts
            
        except Exception as e:
            self.error(
                "Failed to fetch AEMET data",
                exc_info=e
            )
            return []
    
    @log_execution(level='DEBUG')
    def _parse_response(self, data: Dict[str, Any], start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Parse MET.no API response."""
        forecasts = []
        
        try:
            timeseries = data['properties']['timeseries']
            
            for entry in timeseries:
                time_str = entry['time']
                forecast_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                
                # Skip forecasts outside our time range
                if not (start_time <= forecast_time <= end_time):
                    continue
                
                # Get instant data
                instant = entry['data']['instant']['details']
                
                # Get precipitation data from next_1_hours if available, else next_6_hours
                precip_data = (
                    entry['data'].get('next_1_hours', {}).get('details', {}) or
                    entry['data'].get('next_6_hours', {}).get('details', {})
                )
                
                # Get symbol from next_1_hours if available, else next_6_hours
                symbol_data = (
                    entry['data'].get('next_1_hours', {}).get('summary', {}) or
                    entry['data'].get('next_6_hours', {}).get('summary', {})
                )
                
                forecast = WeatherData(
                    temperature=instant.get('air_temperature'),
                    precipitation=precip_data.get('precipitation_amount', 0.0),
                    precipitation_probability=precip_data.get('probability_of_precipitation'),
                    wind_speed=instant.get('wind_speed', 0.0),
                    wind_direction=self._get_wind_direction(instant.get('wind_from_direction')),
                    symbol=symbol_data.get('symbol_code', 'cloudy'),
                    elaboration_time=forecast_time,
                    thunder_probability=entry['data'].get('probability_of_thunder', 0.0)
                )
                
                forecasts.append(forecast)
            
            return forecasts
            
        except KeyError as e:
            self.error(
                "Invalid data structure in MET.no response",
                exc_info=e,
                data_keys=list(data.keys()) if isinstance(data, dict) else None
            )
            return []
    
    def _apply_rate_limit(self) -> None:
        """Apply rate limiting for MET.no API."""
        # Ensure at least 1 second between requests
        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            sleep_time = 1.0 - elapsed
            self.debug(
                "Rate limit",
                sleep_seconds=sleep_time
            )
            time.sleep(sleep_time)
        self._last_request_time = time.time()
    
    def _get_wind_direction(self, degrees: Optional[float]) -> Optional[str]:
        """Convert wind direction from degrees to cardinal direction."""
        if degrees is None:
            return None

        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / 45) % 8
        return directions[index]
    
    def _map_symbol_code(self, symbol_code: str) -> str:
        """Map MET.no symbol codes to our internal weather codes.
        
        See https://api.met.no/weatherapi/weathericon/2.0/documentation for symbol codes.
        """
        # Basic mapping of MET.no symbol codes to our internal codes
        symbol_map = {
            'clearsky': 'CLEAR',
            'fair': 'PARTLY_CLOUDY',
            'partlycloudy': 'PARTLY_CLOUDY',
            'cloudy': 'CLOUDY',
            'fog': 'FOG',
            'rain': 'RAIN',
            'sleet': 'SLEET',
            'snow': 'SNOW',
            'rainshowers': 'RAIN_SHOWERS',
            'sleetshowers': 'SLEET_SHOWERS',
            'snowshowers': 'SNOW_SHOWERS',
            'lightrainshowers': 'LIGHT_RAIN',
            'heavyrainshowers': 'HEAVY_RAIN',
            'lightrain': 'LIGHT_RAIN',
            'heavyrain': 'HEAVY_RAIN',
            'lightsnow': 'LIGHT_SNOW',
            'heavysnow': 'HEAVY_SNOW',
            'thunder': 'THUNDER',
            'rainandthunder': 'RAIN_AND_THUNDER',
            'sleetandthunder': 'SLEET_AND_THUNDER',
            'snowandthunder': 'SNOW_AND_THUNDER',
            'rainshowersandthunder': 'RAIN_AND_THUNDER',
            'sleetshowersandthunder': 'SLEET_AND_THUNDER',
            'snowshowersandthunder': 'SNOW_AND_THUNDER'
        }
        
        return symbol_map.get(symbol_code, 'CLOUDY')  # Default to CLOUDY if unknown code
    
    def _map_aemet_code(self, code: str, hour: int) -> str:
        """Map AEMET weather codes to our internal format.
        
        AEMET codes are numeric and represent different weather conditions:
        11-19: Clear to cloudy
        21-29: Precipitation (rain, snow, etc)
        51-59: Thunderstorm conditions
        61-69: Fog and other conditions
        """
        is_day = 6 <= hour <= 18
        
        try:
            code_num = int(code)
            
            # Clear to cloudy conditions (11-19)
            if 11 <= code_num <= 19:
                if code_num == 11:  # Clear sky
                    return 'clearsky_day' if is_day else 'clearsky_night'
                elif code_num == 12:  # Few clouds
                    return 'fair_day' if is_day else 'fair_night'
                elif code_num == 13:  # Scattered clouds
                    return 'partlycloudy_day' if is_day else 'partlycloudy_night'
                else:  # Broken or overcast clouds
                    return 'cloudy'
            
            # Precipitation conditions (21-29)
            elif 21 <= code_num <= 29:
                if code_num in (21, 24):  # Light rain
                    return 'lightrain'
                elif code_num in (22, 25):  # Rain
                    return 'rain'
                elif code_num in (23, 26):  # Heavy rain
                    return 'heavyrain'
                elif code_num == 27:  # Light snow
                    return 'lightsnow'
                elif code_num == 28:  # Snow
                    return 'snow'
                elif code_num == 29:  # Heavy snow
                    return 'heavysnow'
            
            # Thunderstorm conditions (51-59)
            elif 51 <= code_num <= 59:
                if code_num == 51:  # Light thunderstorm
                    return 'lightrainandthunder'
                elif code_num == 52:  # Thunderstorm
                    return 'rainandthunder'
                elif code_num == 53:  # Heavy thunderstorm
                    return 'heavyrainandthunder'
                elif code_num == 54:  # Light thunderstorm with snow
                    return 'lightsnowandthunder'
                elif code_num == 55:  # Thunderstorm with snow
                    return 'snowandthunder'
                elif code_num == 56:  # Heavy thunderstorm with snow
                    return 'heavysnowandthunder'
            
            # Other conditions (61-69)
            elif 61 <= code_num <= 69:
                if code_num in (61, 62):  # Fog
                    return 'fog'
                elif code_num == 63:  # Light drizzle
                    return 'lightrain'
                elif code_num == 64:  # Drizzle
                    return 'rain'
                elif code_num == 65:  # Heavy drizzle
                    return 'heavyrain'
                elif code_num == 66:  # Light freezing rain
                    return 'lightsleet'
                elif code_num == 67:  # Freezing rain
                    return 'sleet'
                elif code_num == 68:  # Heavy freezing rain
                    return 'heavysleet'
            
            return 'cloudy'  # Default to cloudy if code not recognized
            
        except (ValueError, TypeError):
            return 'cloudy'  # Default to cloudy if code is invalid