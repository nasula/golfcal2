# OpenMeteo Weather Service

## Overview

The OpenMeteo service provides global weather forecasts using the Open-Meteo API. It serves as the primary weather service for all non-Nordic regions in GolfCal2.

## Features

- Global coverage with high-resolution forecasts
- No API key required
- Hourly data for temperature, precipitation, wind, and weather conditions
- WMO weather codes for standardized condition reporting
- Automatic unit conversion (km/h to m/s for wind speed)
- Built-in caching and error handling

## Implementation

```python
class OpenMeteoService(WeatherService):
    """Weather service using Open-Meteo API."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        """Initialize OpenMeteo service."""
        super().__init__(local_tz, utc_tz)
        
        # Initialize OpenMeteo client with caching
        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        retry_session = retry_requests.RetrySession(retries=3)
        self.client = openmeteo_requests.Client(session=cache_session, retry_session=retry_session)
    
    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size."""
        return 1  # OpenMeteo provides hourly data
    
    def get_expiry_time(self) -> datetime:
        """Get forecast expiry time."""
        return datetime.now(self.utc_tz) + timedelta(hours=1)
    
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch forecasts from OpenMeteo API."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "timezone": "UTC",
            "hourly": [
                "temperature_2m",
                "precipitation",
                "precipitation_probability",
                "weathercode",
                "windspeed_10m",
                "winddirection_10m"
            ]
        }
        
        response = self.client.weather_api(params)
        return self._parse_response(response, start_time, end_time)
```

## API Response Format

The OpenMeteo API returns hourly data in parallel arrays:

```json
{
    "hourly": {
        "time": ["2024-01-12T00:00", "2024-01-12T01:00", ...],
        "temperature_2m": [12.3, 11.8, ...],
        "precipitation": [0.0, 0.2, ...],
        "precipitation_probability": [0, 20, ...],
        "weathercode": [0, 3, ...],
        "windspeed_10m": [3.5, 4.2, ...],
        "winddirection_10m": [180, 185, ...]
    }
}
```

## Weather Code Mapping

OpenMeteo uses WMO weather codes, which are mapped to internal codes:

```python
def _map_wmo_code(self, code: int, is_daytime: bool) -> str:
    """Map WMO weather code to internal code."""
    if code == 0:  # Clear sky
        return "clearsky_day" if is_daytime else "clearsky_night"
    elif code in [1, 2, 3]:  # Partly cloudy
        return "fair_day" if is_daytime else "fair_night"
    elif code == 45:  # Foggy
        return "fog"
    elif code in [51, 53, 55]:  # Drizzle
        return "lightrain"
    elif code in [61, 63, 65]:  # Rain
        return "rain"
    elif code in [71, 73, 75]:  # Snow
        return "snow"
    elif code in [95, 96, 99]:  # Thunderstorm
        return "thunder"
    else:
        return "cloudy"
```

## Error Handling

The service implements comprehensive error handling:

1. API Errors
   - Connection failures
   - Invalid responses
   - Missing data

2. Data Validation
   - Coordinate validation
   - Time range validation
   - Data completeness checks

3. Recovery Strategy
   - Automatic retries (3 attempts)
   - Cache utilization
   - Fallback to OpenWeather service

## Configuration

```yaml
weather:
  openmeteo:
    timeout: 10  # seconds
    cache_duration: 3600  # seconds
```

## Integration Example

```python
# Initialize service
service = OpenMeteoService(
    local_tz=ZoneInfo("Europe/Madrid"),
    utc_tz=ZoneInfo("UTC"),
    config={}
)

# Get weather for Algarve, Portugal
try:
    weather = service.get_weather(
        lat=37.0,
        lon=-8.0,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(hours=24)
    )
    print(f"Temperature: {weather.data[0].temperature}°C")
    print(f"Weather: {weather.data[0].weather_code}")
except WeatherError as e:
    print(f"Weather data unavailable: {e}")
``` 