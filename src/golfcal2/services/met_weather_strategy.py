"""
MET weather service strategy implementation.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import requests

from golfcal2.services.weather_service import WeatherStrategy
from golfcal2.services.weather_types import WeatherResponse, WeatherData, WeatherCode
from golfcal2.exceptions import APIError, ErrorCode

class MetWeatherStrategy(WeatherStrategy):
    """Weather strategy for Norwegian Meteorological Institute (MET)."""
    
    service_type: str = "met"
    HOURLY_RANGE: int = 48  # 2 days
    SIX_HOURLY_RANGE: int = 240  # 10 days
    MAX_FORECAST_RANGE: int = 216  # 9 days
    
    def get_weather(self) -> Optional[WeatherResponse]:
        """Get weather data from MET."""
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
            self.error("Failed to get weather data from MET", exc_info=e)
            return None
    
    def get_expiry_time(self) -> datetime:
        """Get expiry time for cached weather data."""
        # MET forecasts are updated every hour
        return datetime.now(self.context.utc_tz) + timedelta(hours=1)
    
    def _fetch_forecasts(self) -> Optional[Dict[str, Any]]:
        """Fetch forecast data from MET API."""
        try:
            # Build API URL
            base_url = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
            params = {
                'lat': f"{self.context.lat:.4f}",
                'lon': f"{self.context.lon:.4f}"
            }
            
            # Set up headers
            headers = {
                'User-Agent': 'golfcal2/1.0.0',
                'Accept': 'application/json'
            }
            
            # Make request
            response = requests.get(base_url, params=params, headers=headers)
            
            # Handle response
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                raise APIError("Authentication failed", ErrorCode.AUTH_FAILED)
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
        """Parse MET API response into WeatherResponse."""
        try:
            if 'properties' not in response_data:
                return None
            
            timeseries = response_data['properties']['timeseries']
            weather_data: List[WeatherData] = []
            
            for entry in timeseries:
                try:
                    # Handle both ISO format with and without Z suffix
                    time_str = entry['time']
                    if time_str.endswith('Z'):
                        time_str = time_str[:-1]  # Remove Z
                        time = datetime.fromisoformat(time_str).replace(tzinfo=self.context.utc_tz)
                    else:
                        time = datetime.fromisoformat(time_str)
                    
                    if not (self.context.start_time <= time <= self.context.end_time):
                        continue
                    
                    instant = entry['data']['instant']['details']
                    next_hour = entry['data'].get('next_1_hours', {})
                    next_hour_details = next_hour.get('details', {})
                    next_hour_summary = next_hour.get('summary', {})
                    
                    # Get symbol code and probabilities
                    symbol_code = next_hour_summary.get('symbol_code', 'UNKNOWN')
                    
                    # Convert symbol code to WeatherCode enum
                    try:
                        weather_code = WeatherCode(symbol_code.upper())
                    except ValueError:
                        weather_code = WeatherCode.UNKNOWN
                    
                    # Get probabilities with defaults
                    precipitation_prob = next_hour_details.get('probability_of_precipitation', 0.0)
                    thunder_prob = next_hour_details.get('probability_of_thunder', 0.0)
                    
                    weather_data.append(WeatherData(
                        time=time,
                        temperature=instant.get('air_temperature', 0.0),
                        precipitation=next_hour_details.get('precipitation_amount', 0.0),
                        wind_speed=instant.get('wind_speed', 0.0),
                        wind_direction=instant.get('wind_from_direction', 0.0),
                        precipitation_probability=precipitation_prob,
                        thunder_probability=thunder_prob,
                        weather_code=weather_code
                    ))
                except ValueError as e:
                    self.warning(f"Failed to parse timestamp {entry['time']}: {e}")
                    continue
            
            # Get elaboration time from response metadata or use current time
            elaboration_time = datetime.now(self.context.utc_tz)
            if 'meta' in response_data and 'updated_at' in response_data['meta']:
                try:
                    time_str = response_data['meta']['updated_at']
                    if time_str.endswith('Z'):
                        time_str = time_str[:-1]
                    elaboration_time = datetime.fromisoformat(time_str).replace(tzinfo=self.context.utc_tz)
                except ValueError:
                    pass
            
            return WeatherResponse(
                data=weather_data,
                elaboration_time=elaboration_time,
                expires=self.get_expiry_time()
            )
            
        except Exception as e:
            self.error(f"Failed to parse response: {e}", exc_info=True)
            return None 