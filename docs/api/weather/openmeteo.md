# OpenMeteo Weather Service API

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
    """Service for handling weather data using Open-Meteo API.
    
    Open-Meteo provides free weather forecast APIs without key requirements.
    Data is updated hourly.
    """
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        super().__init__(local_tz, utc_tz)
        
        # Setup cache and retry mechanism
        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        self.client = openmeteo_requests.Client(session=retry_session)
        
        # Initialize database and cache
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
        self.location_cache = WeatherLocationCache(os.path.join(data_dir, 'weather_locations.db'))
        
        # Rate limiting configuration
        self._min_call_interval = timedelta(seconds=1)
        self.service_type = 'open_meteo'
```

## API Details

- **Base URL**: `https://api.open-meteo.com/v1/forecast`
- **Authentication**: None required
- **Rate Limit**: 10,000 requests/day with minimum 1-second interval
- **Update Frequency**: Hourly
- **Geographic Coverage**: Global

## Request Format

### Parameters

```python
params = {
    "latitude": lat,
    "longitude": lon,
    "hourly": [
        "temperature_2m",
        "precipitation",
        "precipitation_probability",
        "weathercode",
        "windspeed_10m",
        "winddirection_10m"
    ],
    "timezone": "UTC"
}
```

## Weather Codes

OpenMeteo uses WMO weather codes that are mapped to internal codes:

| WMO Code | Description | Internal Code |
|----------|-------------|---------------|
| 0 | Clear sky | clearsky_day/clearsky_night |
| 1, 2, 3 | Mainly clear, partly cloudy, overcast | fair_day/fair_night |
| 45, 48 | Foggy | fog |
| 51, 53, 55 | Drizzle: Light, moderate, dense | lightrain |
| 61, 63, 65 | Rain: Slight, moderate, heavy | rain |
| 71, 73, 75 | Snow: Slight, moderate, heavy | snow |
| 95, 96, 99 | Thunderstorm | thunder |

## Error Handling

The service implements comprehensive error handling:

1. Service Errors
   - Network connectivity issues (`requests.RequestException`)
   - Invalid coordinates
   - Parse errors (JSON format)
   - Missing data fields
   - Rate limit exceeded

2. Recovery Strategies
   - Automatic retries (5 attempts with exponential backoff)
   - Cache utilization for recent requests
   - Fallback to OpenWeather service
   - Rate limit tracking with minimum 1-second interval

## Caching

Weather data is cached using both memory and database caching:

1. Memory Cache:
   - Duration: 1 hour (3600 seconds)
   - Implementation: `requests_cache.CachedSession`

2. Database Cache:
   - Location: `data/weather_cache.db`
   - Implementation: `WeatherResponseCache`
   - Cache key format: `f"open_meteo_{lat:.4f}_{lon:.4f}_{start_time.isoformat()}_{end_time.isoformat()}"`

## Data Mapping

### Units

All data is automatically converted to standard units:
- Temperature: Celsius
- Wind Speed: m/s (converted from km/h)
- Precipitation: mm/h
- Direction: Degrees (0-360)

## Usage Example

```python
service = OpenMeteoService(local_tz, utc_tz, config)
weather = service.get_weather(
    lat=60.1699,
    lon=24.9384,
    start_time=datetime(...),
    end_time=datetime(...)
)
```

## Logging

The service implements detailed logging:
```python
self.debug("Making API request with params", params=params)
self.debug("Got API response", response_type=type(response).__name__)
self.debug("Processed hourly entry", index=i, entry=entry)
self.error("Error fetching forecasts", exc_info=e)
```

## Configuration

Example configuration in `config.yaml`:
```yaml
weather:
  providers:
    openmeteo:
      timeout: 10  # seconds
```

## Related Documentation

- [OpenMeteo API Documentation](https://open-meteo.com/en/docs)
- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md) 