"""
OpenMeteo weather service strategy implementation.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from golfcal2.exceptions import APIError, ErrorCode
from golfcal2.services.weather_service import WeatherStrategy
from golfcal2.services.weather_types import WeatherCode, WeatherData, WeatherResponse


class OpenMeteoStrategy(WeatherStrategy):
    """Weather strategy for OpenMeteo service."""
    
    service_type: str = "openmeteo"
    HOURLY_RANGE: int = 168  # 7 days
    MAX_FORECAST_RANGE: int = 168  # 7 days
    BLOCK_SIZE: int = 1  # Always use 1-hour blocks
    
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
    
    # Thunder probability mapping based on weather codes
    THUNDER_PROBABILITY_MAP = {
        95: 80.0,  # Regular thunderstorm
        96: 90.0,  # Thunderstorm with slight hail
        99: 100.0  # Thunderstorm with heavy hail
    }
    
    def get_weather(self) -> WeatherResponse | None:
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
    
    def _fetch_forecasts(self) -> dict[str, Any] | None:
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
                    'weathercode'
                ],
                'timezone': 'UTC'  # Explicitly request UTC timestamps
            }
            
            # Log request details
            self.debug(
                "Making OpenMeteo API request",
                url=base_url,
                params=params,
                start_time=self.context.start_time.isoformat(),
                end_time=self.context.end_time.isoformat()
            )
            
            # Make request
            response = requests.get(base_url, params=params)
            
            # Log response details
            self.debug(
                "OpenMeteo API response",
                status_code=response.status_code,
                response_text=response.text[:1000] if response.text else None,
                url=response.url
            )
            
            # Handle response
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                raise APIError("Rate limit exceeded", ErrorCode.RATE_LIMITED)
            else:
                error_msg = f"API request failed with status {response.status_code}"
                if response.text:
                    try:
                        error_data = response.json()
                        if 'reason' in error_data:
                            error_msg += f": {error_data['reason']}"
                    except:
                        error_msg += f" - {response.text[:200]}"
                raise APIError(error_msg, ErrorCode.SERVICE_UNAVAILABLE)
                
        except requests.exceptions.RequestException as e:
            self.error(f"Request failed: {e}")
            return None
        except Exception as e:
            self.error(f"Unexpected error: {e}")
            return None
    
    def _parse_response(self, response_data: dict[str, Any]) -> WeatherResponse | None:
        """Parse OpenMeteo API response into WeatherResponse."""
        try:
            if 'hourly' not in response_data:
                return None
            
            hourly = response_data['hourly']
            times = hourly['time']
            weather_data: list[WeatherData] = []
            
            for i, time_str in enumerate(times):
                # OpenMeteo returns UTC times, force UTC timezone
                time = datetime.fromisoformat(time_str).replace(tzinfo=UTC)
                
                # Map OpenMeteo weather codes to WeatherCode enum
                weather_code = hourly['weathercode'][i]
                weather_code_enum = self.WEATHER_CODE_MAP.get(weather_code, WeatherCode.UNKNOWN)
                
                # Get values with defaults for None
                temperature = hourly['temperature_2m'][i] or 0.0
                precipitation = hourly['precipitation'][i] or 0.0
                wind_speed = hourly['windspeed_10m'][i] or 0.0
                wind_direction = hourly['winddirection_10m'][i] or 0.0
                precipitation_probability = hourly.get('precipitation_probability', [0.0])[i] or 0.0
                
                # Calculate thunder probability based on weather code
                thunder_probability = self.THUNDER_PROBABILITY_MAP.get(weather_code, 0.0)
                
                weather_data.append(WeatherData(
                    time=time,  # Time is in UTC
                    temperature=temperature,
                    precipitation=precipitation,
                    wind_speed=wind_speed,
                    wind_direction=wind_direction,
                    precipitation_probability=precipitation_probability,
                    thunder_probability=thunder_probability,  # Add thunder probability
                    weather_code=weather_code_enum,
                    block_duration=timedelta(hours=1)  # OpenMeteo always uses 1-hour blocks
                ))
            
            # Get elaboration time in UTC
            elaboration_time = datetime.now(UTC)
            
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
    
    def get_block_size(self, hours_ahead: float) -> int:
        """Get block size for forecast range.
        
        OpenMeteo provides hourly data for the entire forecast period,
        so we always use 1-hour blocks regardless of how far ahead we're looking.
        """
        return 1 