# Weather Service Manager

## Overview

The Weather Service Manager coordinates multiple weather service providers to ensure reliable weather data delivery. It implements a geographic-based service selection with fallback mechanisms.

## Service Selection

The manager uses the following logic to select a weather service:

1. For Nordic locations (55°N-72°N, 4°E-32°E):
   - Uses MET.no service for high-accuracy forecasts
   - Falls back to OpenMeteo if MET.no fails

2. For all other locations:
   - Uses OpenMeteo service as primary provider
   - Falls back to OpenWeather if OpenMeteo fails

## Implementation

```python
class WeatherManager:
    """Manager for handling multiple weather services."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        """Initialize weather services."""
        self.services = {
            'met': MetWeatherService(local_tz, utc_tz, config),
            'openmeteo': OpenMeteoService(local_tz, utc_tz, config),
            'openweather': OpenWeatherService(local_tz, utc_tz, config)
        }
    
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> WeatherResponse:
        """Get weather data using appropriate service."""
        # Try primary service based on location
        try:
            if self._is_nordic_location(lat, lon):
                return self.services['met'].get_weather(lat, lon, start_time, end_time)
            else:
                return self.services['openmeteo'].get_weather(lat, lon, start_time, end_time)
        except WeatherError as e:
            self.warning(f"Primary service failed: {e}")
            
            # Try fallback service
            try:
                return self.services['openweather'].get_weather(lat, lon, start_time, end_time)
            except WeatherError as e:
                self.error(f"Fallback service failed: {e}")
                raise WeatherServiceUnavailable("No weather service available")
    
    def _is_nordic_location(self, lat: float, lon: float) -> bool:
        """Check if coordinates are in Nordic region."""
        return (55 <= lat <= 72) and (4 <= lon <= 32)
```

## Service Errors

The manager handles various error scenarios:

1. Primary Service Errors
   - Connection failures
   - API errors
   - Invalid data
   - Coverage limitations

2. Fallback Service Errors
   - Same as primary service
   - If all services fail, raises WeatherServiceUnavailable

## Integration Example

```python
# Initialize manager
manager = WeatherManager(
    local_tz=ZoneInfo("Europe/Oslo"),
    utc_tz=ZoneInfo("UTC"),
    config={
        'met': {'user_agent': 'GolfCal2/0.6.0'},
        'openmeteo': {},
        'openweather': {'api_key': 'your-key'}
    }
)

# Get weather for Oslo Golf Club
try:
    weather = manager.get_weather(
        lat=59.8940,
        lon=10.6450,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(hours=24)
    )
    print(f"Temperature: {weather.data[0].temperature}°C")
except WeatherServiceUnavailable as e:
    print(f"Weather data unavailable: {e}")
``` 