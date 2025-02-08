# OpenMeteo Weather Service

## Overview

OpenMeteo weather service strategy implementation. This service is used as the primary provider for locations outside the Nordic/Baltic regions, with global coverage and good accuracy.

## Coverage Area

Global coverage with some limitations:
1. Land areas worldwide
2. Coastal waters
3. Limited coverage in polar regions

## Block Size Pattern

OpenMeteo provides forecasts with varying granularity based on forecast range:

1. Short Range (<48 hours):
   - 1-hour blocks
   - High accuracy
   - Complete weather data

2. Medium Range (48 hours - 7 days):
   - 3-hour blocks
   - Good accuracy
   - Most weather parameters available

3. Long Range (>7 days):
   - 6-hour blocks
   - Reduced accuracy
   - Basic weather parameters

## Implementation

```python
class OpenMeteoStrategy(WeatherStrategy):
    """Weather strategy for OpenMeteo service."""
    
    service_type: str = "openmeteo"
    
    def get_block_size(self, hours_ahead: float) -> int:
        """Get block size based on forecast range.
        
        OpenMeteo provides:
        - 1-hour blocks for first 48 hours
        - 3-hour blocks for days 3-7
        - 6-hour blocks beyond day 7
        """
        if hours_ahead <= 48:
            return 1
        elif hours_ahead <= 168:  # 7 days
            return 3
        else:
            return 6

    def get_weather(self) -> Optional[WeatherResponse]:
        """Get weather data from OpenMeteo."""
        try:
            response = self._fetch_forecasts(
                self.context.lat,
                self.context.lon,
                self.context.start_time,
                self.context.end_time
            )
            
            if response:
                return self._parse_response(response)
            return None
            
        except Exception as e:
            self.error(f"Error fetching OpenMeteo forecast: {e}")
            return None

    def get_expiry_time(self) -> datetime:
        """Get expiry time for cached weather data.
        
        OpenMeteo updates forecasts every 3 hours.
        We expire the cache 5 minutes before the next update.
        """
        now = datetime.now(self.context.utc_tz)
        next_update = now.replace(
            hour=(now.hour // 3 + 1) * 3,
            minute=0,
            second=0,
            microsecond=0
        )
        if next_update <= now:
            next_update += timedelta(hours=3)
        return next_update - timedelta(minutes=5)
```

## API Usage

1. No authentication required
2. Rate Limiting:
   - Free tier: 10,000 requests per day
   - Automatic rate limiting applied

3. Response Format:
   ```json
   {
     "latitude": 41.8789,
     "longitude": 2.7649,
     "hourly": {
       "time": ["2024-02-08T12:00", "2024-02-08T13:00"],
       "temperature_2m": [15.2, 16.1],
       "precipitation_probability": [0, 15],
       "precipitation": [0.0, 0.2],
       "weathercode": [1, 3],
       "windspeed_10m": [3.2, 3.8]
     }
   }
   ```

## Error Handling

1. Service Errors:
   - Connection timeouts
   - Rate limiting
   - Invalid coordinates
   - Parse errors

2. Data Validation:
   - Temperature range checks
   - Wind speed validation
   - Weather code mapping

## Testing

Test cases cover:
1. Short-range forecasts (Lykia Links Tomorrow)
2. Medium-range forecasts (PGA Catalunya 4 Days)
3. Long-range forecasts (PDR Next Week)
4. Edge cases:
   - Timezone handling
   - DST transitions
   - Equatorial locations

## Features

- Global coverage with high-resolution forecasts
- No API key required
- Hourly data for temperature, precipitation, wind, and weather conditions
- WMO weather codes for standardized condition reporting
- Automatic unit conversion (km/h to m/s for wind speed)
- Built-in caching and error handling

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