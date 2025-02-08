# Weather Service APIs

## Overview

GolfCal2 integrates with two primary weather service providers to ensure reliable weather data across different regions. Each provider is selected based on geographic location and availability.

## Service Selection

The system uses the following logic to select a weather service:

1. Nordic and Baltic Regions:
   - Nordic (55°N-71°N, 4°E-32°E):
     - Norway, Sweden, Finland, Denmark
   - Baltic (53°N-59°N, 21°E-28°E):
     - Estonia, Latvia, Lithuania
   - Primary: Met.no
   - Fallback: OpenMeteo

2. All Other Regions:
   - Primary: OpenMeteo
   - Fallback: Met.no

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
    weather_code: WeatherCode     # Standardized weather code
    time: datetime                # UTC
    block_duration: timedelta     # Forecast block duration
```

## Service Providers

### [Met.no](met.md)
- **Coverage**: Nordic and Baltic regions
- **Update Frequency**: Hourly
- **Authentication**: User-Agent required
- **Rate Limit**: 1 request/second (courtesy)
- **Block Sizes**:
  - 0-48h: 1-hour blocks
  - 48h-7d: 6-hour blocks
  - >7d: 12-hour blocks

### [OpenMeteo](openmeteo.md)
- **Coverage**: Global
- **Update Frequency**: 3 hours
- **Authentication**: None required
- **Rate Limit**: 10,000 requests/day
- **Block Sizes**:
  - 0-48h: 1-hour blocks
  - 48h-7d: 3-hour blocks
  - >7d: 6-hour blocks

## Error Handling

Each service implements the following error handling:

1. Service Errors
   - `WeatherServiceUnavailable`: Service not accessible
   - `WeatherDataError`: Invalid data format
   - `WeatherAPIError`: API communication error
   - `WeatherServiceRateLimited`: Rate limit exceeded

2. Recovery Strategies
   - Automatic service fallback
   - Cache utilization
   - Exponential backoff for rate limits

## Caching

Weather data is cached with the following rules:

1. Met.no:
   - Cache Duration: 1 hour
   - Invalidation: 5 minutes before next hour

2. OpenMeteo:
   - Cache Duration: 3 hours
   - Invalidation: 5 minutes before next 3-hour mark

## Rate Limiting

Each service implements appropriate rate limiting:

1. Met.no:
   ```python
   # Courtesy rate limit
   time.sleep(1.0)  # 1 second between requests
   ```

2. OpenMeteo:
   ```python
   # Free tier limit
   if daily_requests >= 10000:
       raise WeatherServiceRateLimited()
   ```

## Service Integration

To integrate a new weather service:

1. Implement the strategy interface:
   ```python
   class NewWeatherStrategy(WeatherStrategy):
       service_type: str = "new_service"
       
       def get_weather(self) -> Optional[WeatherResponse]:
           pass
       
       def get_expiry_time(self) -> datetime:
           pass
       
       def get_block_size(self, hours_ahead: float) -> int:
           pass
   ```

2. Add service configuration:
   ```yaml
   weather:
     providers:
       new_service:
         timeout: 10
         cache_duration: 3600
   ```

3. Register the strategy:
   ```python
   weather_service.register_strategy('new_service', NewWeatherStrategy)
   ```

## Testing

The service includes comprehensive test coverage:

1. Time ranges:
   - Short range (<48h)
   - Medium range (48h-7d)
   - Long range (>7d)

2. Geographical coverage:
   - Nordic region (Met.no primary)
   - Mediterranean (OpenMeteo primary)
   - Different timezones (e.g., Canary Islands)

## Related Documentation

- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md)
- [Weather Flow Diagrams](../../services/weather/diagrams/weather_flow.md) 