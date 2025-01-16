# OpenWeather Service API

## Overview

OpenWeather provides global weather forecasts and serves as a fallback weather service in GolfCal2 when primary services (MET.no for Nordic regions, OpenMeteo for other regions) are unavailable.

## API Details

- **Base URL**: `https://api.openweathermap.org/data/2.5/`
- **Authentication**: API key required
- **Rate Limit**: 60 calls/minute (free tier)
- **Update Frequency**: 3 hours
- **Forecast Range**: 5 days (3-hour blocks)

## Authentication

The service requires an API key in the request parameters:
```python
params = {
    'appid': 'your-api-key',
    'lat': latitude,
    'lon': longitude,
    'units': 'metric'
}
```

## Endpoints

### Get Weather Forecast

```
GET /forecast
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| lat | float | Yes | Latitude (-90 to 90) |
| lon | float | Yes | Longitude (-180 to 180) |
| appid | string | Yes | API key |
| units | string | No | Units format (metric/imperial) |
| lang | string | No | Language code |

#### Example Request

```
GET /forecast?lat=60.1699&lon=24.9384&appid=your-api-key&units=metric
```

#### Response Format

```json
{
    "cod": "200",
    "message": 0,
    "cnt": 40,
    "list": [
        {
            "dt": 1674486000,
            "main": {
                "temp": 20.5,
                "feels_like": 19.8,
                "temp_min": 19.2,
                "temp_max": 21.3,
                "pressure": 1015,
                "humidity": 82
            },
            "weather": [
                {
                    "id": 800,
                    "main": "Clear",
                    "description": "clear sky",
                    "icon": "01d"
                }
            ],
            "clouds": {
                "all": 0
            },
            "wind": {
                "speed": 5.2,
                "deg": 180
            },
            "rain": {
                "3h": 0
            },
            "sys": {
                "pod": "d"
            },
            "dt_txt": "2024-01-23 12:00:00"
        }
    ],
    "city": {
        "id": 658225,
        "name": "Helsinki",
        "coord": {
            "lat": 60.1699,
            "lon": 24.9384
        },
        "country": "FI",
        "population": 558457,
        "timezone": 7200,
        "sunrise": 1674459600,
        "sunset": 1674486000
    }
}
```

## Implementation

The service is implemented in `services/open_weather_service.py`:

```python
class OpenWeatherService(WeatherService):
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
        self.api_key = config.global_config['api_keys']['weather']['openweather']
        self.db = WeatherDatabase(f'openweather_{region}')
        self.rate_limiter = RateLimiter(max_calls=60, time_window=60)
```

## Weather Codes

OpenWeather uses a proprietary ID system that is mapped to standardized weather codes:

| ID | Description | WMO Code |
|----|-------------|----------|
| 800 | Clear sky | 0 |
| 801-803 | Partly cloudy | 2 |
| 804 | Overcast | 3 |
| 701 | Mist | 45 |
| 741 | Fog | 45 |
| 300-302 | Light drizzle | 51 |
| 500 | Light rain | 61 |
| 501 | Moderate rain | 63 |
| 502-504 | Heavy rain | 65 |
| 600 | Light snow | 71 |
| 601 | Snow | 73 |
| 602 | Heavy snow | 75 |
| 200-202 | Thunderstorm | 95 |
| 221 | Thunderstorm with hail | 96 |

## Error Handling

The service implements comprehensive error handling:

1. Service Errors
   - Network connectivity issues
   - Invalid API key
   - Rate limiting (429 responses)
   - Invalid coordinates
   - Parse errors

2. Recovery Strategies
   - Cache utilization for recent requests
   - Exponential backoff for rate limits
   - Graceful degradation

## Caching

Weather data is cached with the following rules:

1. Cache Duration:
   - Short-term forecasts (0-24h): 1 hour
   - Medium-term forecasts (1-5d): 3 hours

2. Cache Keys:
   ```python
   f"openweather_{region}_{lat:.4f}_{lon:.4f}_{start_time.isoformat()}_{end_time.isoformat()}"
   ```

## Data Mapping

### Units

All data is converted to standard units:
- Temperature: Celsius (using units=metric)
- Wind Speed: m/s
- Precipitation: mm/3h (converted to mm/h)
- Direction: Compass points (converted from degrees)

## Usage Example

```python
service = OpenWeatherService(local_tz, utc_tz, config, region="global")
weather = service.get_weather(
    lat=60.1699,
    lon=24.9384,
    start_time=datetime(...),
    end_time=datetime(...)
)
```

## Rate Limiting

Rate limiting is implemented using a rolling window:
```python
rate_limiter = RateLimiter(
    max_calls=60,
    time_window=60  # 60 seconds
)
```

## Logging

The service implements detailed logging:
```python
self.debug("Cache hit for OpenWeather forecast", coords=(lat, lon))
self.info("Fetching new forecast", coords=(lat, lon))
self.error("Failed to fetch OpenWeather forecast", exc_info=e)
```

## Configuration

Example configuration in `config.yaml`:
```yaml
weather:
  providers:
    openweather:
      api_key: "your-key"
      timeout: 10
      cache_duration: 3600
```

## Related Documentation

- [OpenWeather API Documentation](https://openweathermap.org/api/hourly-forecast)
- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md)
``` 