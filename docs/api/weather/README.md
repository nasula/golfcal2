# Weather Service APIs

## Overview

GolfCal2 integrates with multiple weather service providers to ensure reliable weather data across different regions. Each provider is selected based on geographic location and availability.

## Service Selection

The system uses the following logic to select a weather service:

1. Nordic Region (55°N-72°N, 4°E-32°E):
   - Primary: MET.no
   - Fallback: OpenMeteo

2. Iberian Region (Spain and territories):
   - Primary: AEMET
   - Fallback: OpenMeteo

3. All Other Regions:
   - Primary: OpenMeteo
   - Fallback: OpenWeather

## Weather Data Format

All weather services return data in a standardized format:

```python
@dataclass
class WeatherData:
    temperature: float              # Celsius
    precipitation: float           # mm/h
    precipitation_probability: float # 0-100%
    wind_speed: float             # m/s
    wind_direction: str           # Compass direction
    symbol: str                   # Weather code
    elaboration_time: datetime    # UTC
    thunder_probability: float    # 0-100%
    block_duration: timedelta     # Forecast block duration
```

## Service Providers

### [MET.no](met.md)
- **Coverage**: Nordic region
- **Update Frequency**: Hourly
- **Authentication**: User-Agent required
- **Rate Limit**: 1 request/second
- **Forecast Range**: 48 hours (hourly) + 9 days (6-hour blocks)

### [OpenMeteo](openmeteo.md)
- **Coverage**: Global
- **Update Frequency**: Hourly
- **Authentication**: None required
- **Rate Limit**: 10,000 requests/day
- **Forecast Range**: 7 days (hourly)

### [OpenWeather](openweather.md)
- **Coverage**: Global
- **Update Frequency**: 3 hours
- **Authentication**: API key required
- **Rate Limit**: 60 calls/minute (free tier)
- **Forecast Range**: 5 days (3-hour blocks)

### [AEMET](aemet.md)
- **Coverage**: Spain and territories
- **Update Frequency**: 4 times daily
- **Authentication**: API key required
- **Rate Limit**: 30 requests/minute
- **Forecast Range**: 7 days (hourly for first 48h)

## Error Handling

Each service implements the following error handling:

1. Service Errors
   - `WeatherServiceUnavailable`: Service not accessible
   - `WeatherDataError`: Invalid data format
   - `WeatherAPIError`: API communication error

2. Recovery Strategies
   - Automatic service fallback
   - Cache utilization
   - Exponential backoff for rate limits

## Caching

Weather data is cached with the following rules:

1. Cache Duration:
   - Short-term forecasts (0-48h): 1 hour
   - Medium-term forecasts (2-7d): 3 hours
   - Long-term forecasts (>7d): 6 hours

2. Cache Invalidation:
   - On service update schedule
   - On error responses
   - On manual clear command

## Rate Limiting

Each service implements appropriate rate limiting:

1. MET.no:
   ```python
   rate_limiter = RateLimiter(max_calls=1, time_window=1)  # 1 call per second
   ```

2. OpenMeteo:
   ```python
   rate_limiter = RateLimiter(max_calls=10000, time_window=86400)  # 10K per day
   ```

3. OpenWeather:
   ```python
   rate_limiter = RateLimiter(max_calls=60, time_window=60)  # 60 per minute
   ```

4. AEMET:
   ```python
   rate_limiter = RateLimiter(max_calls=30, time_window=60)  # 30 per minute
   ```

## Service Integration

To integrate a new weather service:

1. Implement the base interface:
   ```python
   class WeatherService:
       def get_weather(
           self,
           lat: float,
           lon: float,
           start_time: datetime,
           end_time: datetime
       ) -> WeatherResponse:
           pass
   ```

2. Add service configuration:
   ```yaml
   weather:
     providers:
       new_service:
         api_key: "your-key"
         timeout: 10
         cache_duration: 3600
   ```

3. Implement error handling and caching

4. Add to service selection logic in WeatherManager

## Related Documentation

- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md)
- [Weather Flow Diagrams](../../services/weather/diagrams/weather_flow.md) 