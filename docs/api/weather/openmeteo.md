# OpenMeteo Weather Service API

## Overview

OpenMeteo provides global weather forecasts with high resolution and accuracy. It serves as the primary weather service for all non-Nordic regions in GolfCal2 and as a fallback for Nordic regions when MET.no is unavailable.

## API Details

- **Base URL**: `https://api.open-meteo.com/v1/forecast`
- **Authentication**: None required (free tier)
- **Rate Limit**: 10,000 requests/day
- **Update Frequency**: Hourly
- **Forecast Range**: 7 days (hourly resolution)

## Features

- Global coverage with high-resolution forecasts
- No API key required
- WMO weather codes for standardized condition reporting
- Automatic unit conversion
- Built-in caching and error handling

## Endpoints

### Get Weather Forecast

```
GET /v1/forecast
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| latitude | float | Yes | Latitude (-90 to 90) |
| longitude | float | Yes | Longitude (-180 to 180) |
| hourly | string | Yes | Comma-separated list of variables |
| timezone | string | Yes | Timezone name (e.g., "Europe/Oslo") |
| forecast_days | integer | No | Number of days (default: 7) |

#### Example Request

```
GET /v1/forecast?latitude=60.1699&longitude=24.9384&hourly=temperature_2m,precipitation,windspeed_10m,winddirection_10m,weathercode&timezone=Europe/Oslo
```

#### Response Format

```json
{
    "latitude": 60.17,
    "longitude": 24.94,
    "generationtime_ms": 0.3,
    "utc_offset_seconds": 7200,
    "timezone": "Europe/Oslo",
    "timezone_abbreviation": "CEST",
    "elevation": 15.0,
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "precipitation": "mm",
        "windspeed_10m": "m/s",
        "winddirection_10m": "°",
        "weathercode": "wmo code"
    },
    "hourly": {
        "time": ["2024-01-23T00:00", ...],
        "temperature_2m": [20.5, ...],
        "precipitation": [0.0, ...],
        "windspeed_10m": [5.2, ...],
        "winddirection_10m": [180, ...],
        "weathercode": [1, ...]
    }
}
```

## Implementation

The service is implemented in `services/open_meteo_service.py`:

```python
class OpenMeteoService(WeatherService):
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[WeatherResponse]:
        # Check cache first
        cached_response = self.cache.get_response(...)
        if cached_response:
            return self._parse_response(...)
            
        # Fetch new data
        response = self._fetch_forecast(lat, lon, start_time, end_time)
        if response:
            # Store in cache
            self.cache.store_response(...)
            return self._parse_response(...)
```

## Weather Codes

OpenMeteo uses WMO (World Meteorological Organization) weather codes:

| Code | Description |
|------|-------------|
| 0 | Clear sky |
| 1, 2, 3 | Mainly clear, partly cloudy, and overcast |
| 45, 48 | Foggy |
| 51, 53, 55 | Drizzle: Light, moderate, and dense intensity |
| 61, 63, 65 | Rain: Slight, moderate and heavy intensity |
| 71, 73, 75 | Snow fall: Slight, moderate, and heavy intensity |
| 77 | Snow grains |
| 80, 81, 82 | Rain showers: Slight, moderate, and violent |
| 85, 86 | Snow showers slight and heavy |
| 95 | Thunderstorm: Slight or moderate |
| 96, 99 | Thunderstorm with slight and heavy hail |

## Error Handling

The service implements comprehensive error handling:

1. Service Errors
   - Network connectivity issues
   - Invalid coordinates
   - Parse errors
   - Rate limit exceeded

2. Recovery Strategies
   - Automatic fallback to OpenWeather
   - Cache utilization for recent requests
   - Rate limit tracking

## Caching

Weather data is cached with the following rules:

1. Cache Duration:
   - Short-term forecasts (0-48h): 1 hour
   - Medium-term forecasts (2-7d): 3 hours

2. Cache Keys:
   ```python
   f"openmeteo_{lat:.4f}_{lon:.4f}_{start_time.isoformat()}_{end_time.isoformat()}"
   ```

## Data Mapping

### Units

All data is automatically converted to standard units:
- Temperature: Celsius
- Wind Speed: m/s (converted from km/h)
- Precipitation: mm/h
- Direction: Compass points (converted from degrees)

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
self.debug("Cache hit for OpenMeteo forecast", coords=(lat, lon))
self.info("Fetching new forecast", coords=(lat, lon))
self.error("Failed to fetch OpenMeteo forecast", exc_info=e)
```

## Rate Limiting

Rate limiting is implemented using a simple counter:
```python
rate_limiter = RateLimiter(
    max_calls=10000,
    time_window=86400  # 24 hours in seconds
)
```

## Related Documentation

- [OpenMeteo API Documentation](https://open-meteo.com/en/docs)
- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md) 