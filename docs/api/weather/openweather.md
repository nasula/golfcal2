# OpenWeather Service API

## Overview

The OpenWeather service provides global weather coverage and serves as both a primary service for regions not covered by specialized providers and a fallback service when regional services are unavailable.

## Features

- Global coverage with high-resolution forecasts
- API key authentication
- 5-day forecast with 3-hour resolution
- Comprehensive weather data including temperature, precipitation, wind, and conditions
- Configurable by region
- Built-in caching and rate limiting

## Implementation

```python
class OpenWeatherService(WeatherService, EnhancedLoggerMixin):
    """OpenWeather API implementation.
    
    This service uses OpenWeather's API to provide weather forecasts globally.
    It can be configured for specific regions with different settings.
    """

    def __init__(
        self,
        local_tz: ZoneInfo,
        utc_tz: ZoneInfo,
        config: Dict[str, Any],
        region: str = "global"
    ):
        super().__init__(local_tz, utc_tz)
        
        self.base_url = "https://api.openweathermap.org/data/2.5/"
        self.region = region
        
        # Get API key from config
        if isinstance(config, dict):
            self.api_key = config.get('api_keys', {}).get('weather', {}).get('openweather')
        else:
            self.api_key = config.global_config['api_keys']['weather']['openweather']
        
        if not self.api_key:
            raise WeatherServiceUnavailable(
                "OpenWeather API key not configured",
                aggregate_error("API key not configured", "open_weather", None)
            )
        
        # Initialize database for caching with region-specific schema
        self.db = WeatherDatabase(f'openweather_{region}', OPEN_WEATHER_SCHEMA)
        
        # Initialize rate limiter (60 calls per minute)
        self.rate_limiter = RateLimiter(max_calls=60, time_window=60)
        
        # Set logging context
        self.set_log_context(service=f"OpenWeather-{region}")
```

## API Details

- **Base URL**: `https://api.openweathermap.org/data/2.5/`
- **Authentication**: API key required
- **Rate Limit**: 60 calls/minute (free tier)
- **Update Frequency**: Every 3 hours
- **Geographic Coverage**: Global
- **Forecast Range**: 5 days with 3-hour resolution

## Request Format

### Headers

```python
headers = {
    'Accept': 'application/json'
}
```

### Parameters

```python
params = {
    "lat": lat,
    "lon": lon,
    "appid": self.api_key,
    "units": "metric",  # For Celsius and m/s
    "lang": "en"
}
```

## Error Handling

The service implements comprehensive error handling:

1. Service Errors
   - Network connectivity issues (`requests.RequestException`)
   - Authentication errors (invalid API key)
   - Rate limiting (429 responses)
   - Invalid coordinates
   - Parse errors (JSON format)
   - Missing data fields

2. Recovery Strategies
   - Automatic retries with exponential backoff
   - Cache utilization for recent requests
   - Region-specific error handling
   - Rate limit tracking with rolling window

## Caching

Weather data is cached using a SQLite database:

1. Database Cache:
   - Location: Based on region (`openweather_{region}`)
   - Schema: Defined in `OPEN_WEATHER_SCHEMA`
   - Implementation: `WeatherDatabase`
   - Cache key format: `f"openweather_{region}_{lat:.4f}_{lon:.4f}_{start_time.isoformat()}_{end_time.isoformat()}"`

## Data Mapping

### Units

All data is automatically converted to standard units:
- Temperature: Celsius (using units=metric)
- Wind Speed: m/s
- Precipitation: mm/h (converted from mm/3h)
- Direction: Degrees (0-360)

## Usage Example

```python
service = OpenWeatherService(
    local_tz=ZoneInfo("Europe/Madrid"),
    utc_tz=ZoneInfo("UTC"),
    config=config,
    region="global"
)

try:
    weather = service.get_weather(
        lat=60.1699,
        lon=24.9384,
        start_time=datetime(...),
        end_time=datetime(...)
    )
    print(f"Temperature: {weather.data[0].temperature}°C")
except WeatherError as e:
    print(f"Weather data unavailable: {e}")
```

## Logging

The service implements detailed logging with enhanced context:
```python
self.debug("Fetching forecast", coords=(lat, lon), region=self.region)
self.info("Cache hit for forecast", coords=(lat, lon))
self.error("Failed to fetch forecast", exc_info=e, region=self.region)
```

## Rate Limiting

Rate limiting is implemented using a rolling window:
```python
rate_limiter = RateLimiter(
    max_calls=60,
    time_window=60  # 60 seconds
)
```

## Configuration

Example configuration in `config.yaml`:
```yaml
weather:
  providers:
    openweather:
      api_key: "your-api-key"
      timeout: 10
      regions:
        global:
          cache_duration: 3600
        nordic:
          cache_duration: 7200
```

## Related Documentation

- [OpenWeather API Documentation](https://openweathermap.org/api/one-call-3)
- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md)
``` 