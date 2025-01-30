"""
OpenMeteo weather service strategy implementation.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import requests

from golfcal2.services.weather_service import WeatherStrategy
from golfcal2.services.weather_types import WeatherResponse, WeatherData, WeatherCode
from golfcal2.exceptions import APIError, ErrorCode

class OpenMeteoStrategy(WeatherStrategy):
    """Weather strategy for OpenMeteo service."""
    
    service_type: str = "openmeteo"
    HOURLY_RANGE: int = 168  # 7 days
    MAX_FORECAST_RANGE: int = 168  # 7 days
    
    # OpenMeteo weather code mapping
    # https://open-meteo.com/en/docs#weathervariables
    WEATHER_CODE_MAP = {
        0: WeatherCode.CLEARSKY_DAY,  # Clear sky
        1: WeatherCode.FAIR_DAY,  # Mainly clear
        2: WeatherCode.PARTLYCLOUDY_DAY,  # Partly cloudy
        3: WeatherCode.CLOUDY,  # Overcast
        45: WeatherCode.CLOUDY,  # Foggy
        48: WeatherCode.CLOUDY,  # Depositing rime fog
        51: WeatherCode.LIGHTRAIN,  # Light drizzle
        53: WeatherCode.RAIN,  # Moderate drizzle
        55: WeatherCode.HEAVYRAIN,  # Dense drizzle
        61: WeatherCode.LIGHTRAIN,  # Slight rain
        63: WeatherCode.RAIN,  # Moderate rain
        65: WeatherCode.HEAVYRAIN,  # Heavy rain
        71: WeatherCode.LIGHTSNOW,  # Slight snow
        73: WeatherCode.SNOW,  # Moderate snow
        75: WeatherCode.HEAVYSNOW,  # Heavy snow
        77: WeatherCode.SNOW,  # Snow grains
        80: WeatherCode.RAINSHOWERS_DAY,  # Slight rain showers
        81: WeatherCode.RAINSHOWERS_DAY,  # Moderate rain showers
        82: WeatherCode.HEAVYRAINSHOWERS_DAY,  # Violent rain showers
        85: WeatherCode.SNOWSHOWERS_DAY,  # Slight snow showers
        86: WeatherCode.SNOWSHOWERS_DAY,  # Heavy snow showers
        95: WeatherCode.THUNDERSTORM,  # Thunderstorm
        96: WeatherCode.RAINANDTHUNDER,  # Thunderstorm with slight hail
        99: WeatherCode.HEAVYRAINANDTHUNDER,  # Thunderstorm with heavy hail
    }
    
    def get_weather(self) -> Optional[WeatherResponse]:
        """Get weather data from OpenMeteo."""
        try:
            # Check if request is beyond maximum forecast range
            now_utc = datetime.now(self.context.utc_tz)
            hours_ahead = (self.context.end_time - now_utc).total_seconds() / 3600
            
            if hours_ahead > self.MAX_FORECAST_RANGE:
                self.warning(
                    "Request beyond maximum forecast range",
                    max_range_hours=self.MAX_FORECAST_RANGE,
                    requested_hours=hours_ahead,
                    end_time=self.context.end_time.isoformat()
                )
                return None
            
            # Fetch and parse forecast data
            response_data = self._fetch_forecasts()
            if not response_data:
                return None
                
            return self._parse_response(response_data)
            
        except Exception as e:
            self.error("Failed to get weather data from OpenMeteo", exc_info=e)
            return None
    
    def get_expiry_time(self) -> datetime:
        """Get expiry time for cached weather data."""
        # OpenMeteo forecasts are updated every 3 hours
        return datetime.now(self.context.utc_tz) + timedelta(hours=3)
    
    def _fetch_forecasts(self) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from OpenMeteo API."""
        try:
            # Build API URL
            base_url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': f"{self.context.lat:.4f}",
                'longitude': f"{self.context.lon:.4f}",
                'hourly': [
                    'temperature_2m',
                    'precipitation',
                    'precipitation_probability',
                    'windspeed_10m',
                    'winddirection_10m',
                    'weathercode',
                    'thunder_probability'
                ],
                'timezone': self.context.local_tz.key
            }
            
            # Make request
            response = requests.get(base_url, params=params)
            
            # Handle response
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                raise APIError("Rate limit exceeded", ErrorCode.RATE_LIMITED)
            else:
                raise APIError(
                    f"API request failed with status {response.status_code}",
                    ErrorCode.SERVICE_UNAVAILABLE
                )
                
        except requests.exceptions.RequestException as e:
            self.error(f"Request failed: {e}")
            return None
        except Exception as e:
            self.error(f"Unexpected error: {e}")
            return None
    
    def _parse_response(self, response_data: Dict[str, Any]) -> Optional[WeatherResponse]:
        """Parse OpenMeteo API response into WeatherResponse."""
        try:
            if 'hourly' not in response_data:
                return None
            
            hourly = response_data['hourly']
            times = hourly['time']
            weather_data: List[WeatherData] = []
            
            for i, time_str in enumerate(times):
                # Parse time and ensure it's timezone-aware
                time = datetime.fromisoformat(time_str).replace(tzinfo=self.context.local_tz)
                if not (self.context.start_time <= time <= self.context.end_time):
                    continue
                
                # Map OpenMeteo weather codes to WeatherCode enum
                weather_code = hourly['weathercode'][i]
                weather_code_enum = self.WEATHER_CODE_MAP.get(weather_code, WeatherCode.UNKNOWN)
                
                # Get values with defaults for None
                temperature = hourly['temperature_2m'][i] or 0.0
                precipitation = hourly['precipitation'][i] or 0.0
                wind_speed = hourly['windspeed_10m'][i] or 0.0
                wind_direction = hourly['winddirection_10m'][i] or 0.0
                precipitation_probability = hourly.get('precipitation_probability', [0.0])[i] or 0.0
                thunder_probability = hourly.get('thunder_probability', [0.0])[i] or 0.0
                
                weather_data.append(WeatherData(
                    time=time,
                    temperature=temperature,
                    precipitation=precipitation,
                    wind_speed=wind_speed,
                    wind_direction=wind_direction,
                    precipitation_probability=precipitation_probability,
                    thunder_probability=thunder_probability,
                    weather_code=weather_code_enum
                ))
            
            # Get elaboration time from response metadata or use current time
            elaboration_time = datetime.now(self.context.utc_tz)
            
            return WeatherResponse(
                data=weather_data,
                elaboration_time=elaboration_time,
                expires=self.get_expiry_time()
            )
            
        except Exception as e:
            self.error(f"Failed to parse response: {e}", exc_info=True)
            return None
    
    def _map_weather_code(self, code: int) -> str:
        """Map OpenMeteo weather codes to symbol codes."""
        # OpenMeteo weather code mapping
        # https://open-meteo.com/en/docs#weathervariables
        mapping = {
            0: "clearsky",  # Clear sky
            1: "fair",  # Mainly clear
            2: "partlycloudy",  # Partly cloudy
            3: "cloudy",  # Overcast
            45: "fog",  # Foggy
            48: "fog",  # Depositing rime fog
            51: "lightrain",  # Light drizzle
            53: "rain",  # Moderate drizzle
            55: "heavyrain",  # Dense drizzle
            61: "lightrain",  # Slight rain
            63: "rain",  # Moderate rain
            65: "heavyrain",  # Heavy rain
            71: "lightsnow",  # Slight snow
            73: "snow",  # Moderate snow
            75: "heavysnow",  # Heavy snow
            77: "snow",  # Snow grains
            80: "lightrain",  # Slight rain showers
            81: "rain",  # Moderate rain showers
            82: "heavyrain",  # Violent rain showers
            85: "lightsnow",  # Slight snow showers
            86: "heavysnow",  # Heavy snow showers
            95: "thunderstorm",  # Thunderstorm
            96: "thunderstorm",  # Thunderstorm with slight hail
            99: "thunderstorm"  # Thunderstorm with heavy hail
        }
        return mapping.get(code, "clearsky") 