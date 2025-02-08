# Weather Service APIs

## Overview

GolfCal2 implements a strategy pattern for weather services, integrating with two primary providers to ensure reliable weather data across different regions. Each strategy is selected based on geographic location and availability.

## Strategy Selection

The system uses the following logic to select a weather strategy:

1. Nordic and Baltic Regions:
   - Nordic (55°N-71°N, 4°E-32°E):
     - Norway, Sweden, Finland, Denmark
   - Baltic (53°N-59°N, 21°E-28°E):
     - Estonia, Latvia, Lithuania
   - Primary: Met.no
   - Fallback: OpenMeteo

2. All Other Regions:
   - Primary: OpenMeteo
   - No fallback needed (reliable global coverage)

## Weather Data Format

All weather strategies return data in a standardized format:

```python
@dataclass
class WeatherData:
    temperature: float              # Celsius
    precipitation: float           # mm/h
    precipitation_probability: Optional[float] # 0-100%
    wind_speed: float             # m/s
    wind_direction: Optional[float] # Degrees (0-360)
    symbol: WeatherCode           # Weather code enum
    elaboration_time: datetime    # UTC
    block_size: BlockSize         # Block size enum
    thunder_probability: Optional[float] = None  # 0-100%
```

## Strategy Interface

Base strategy implementation:

```python
class WeatherStrategy(ABC):
    """Base strategy for weather services."""
    
    service_type: str = "base"  # Should be overridden by subclasses
    
    def __init__(self, context: WeatherContext):
        self.context = context
    
    @abstractmethod
    def get_weather(self) -> Optional[WeatherResponse]:
        """Get weather data for the given context."""
        pass
    
    @abstractmethod
    def get_expiry_time(self) -> datetime:
        """Get expiry time for cached weather data."""
        pass

    @abstractmethod
    def get_block_size(self, hours_ahead: float) -> BlockSize:
        """Get block size for forecast range."""
        pass
```

## Strategy Implementations

### [Met.no Strategy](met.md)
- **Coverage**: Nordic and Baltic regions
- **Update Frequency**: Hourly
- **Authentication**: User-Agent required
- **Rate Limit**: 1 request/second (courtesy)
- **Block Sizes**:
  - 0-48h: BlockSize.ONE_HOUR
  - 48h-7d: BlockSize.SIX_HOURS
  - >7d: BlockSize.TWELVE_HOURS

### [OpenMeteo Strategy](openmeteo.md)
- **Coverage**: Global
- **Update Frequency**: 3 hours
- **Authentication**: None required
- **Rate Limit**: 10,000 requests/day
- **Block Sizes**:
  - 0-48h: BlockSize.ONE_HOUR
  - 48h-7d: BlockSize.THREE_HOURS
  - >7d: BlockSize.SIX_HOURS

## Error Handling

Each strategy implements the following error handling:

1. Strategy Errors
   - `WeatherServiceUnavailable`: Service not accessible
   - `WeatherDataError`: Invalid data format
   - `WeatherAPIError`: API communication error
   - `WeatherServiceRateLimited`: Rate limit exceeded
   - `WeatherLocationError`: Invalid coordinates

2. Recovery Mechanisms
   - Automatic strategy fallback
   - Cache utilization
   - Exponential backoff
   - Graceful degradation

## Caching

Weather data is cached with the following rules:

1. Met.no Strategy:
   - Cache Duration: 1 hour
   - Invalidation: 5 minutes before next hour
   - Key Format: "{lat},{lon}:met:{block_size}"

2. OpenMeteo Strategy:
   - Cache Duration: 3 hours
   - Invalidation: 5 minutes before next 3-hour mark
   - Key Format: "{lat},{lon}:openmeteo:{block_size}"

## Rate Limiting

Each strategy implements appropriate rate limiting:

1. Met.no:
   ```python
   @rate_limit(requests_per_second=1)
   def _fetch_data(self):
       """Fetch data with courtesy rate limit."""
       pass
   ```

2. OpenMeteo:
   ```python
   @rate_limit(requests_per_day=10000)
   def _fetch_data(self):
       """Fetch data with free tier limit."""
       pass
   ```

## Strategy Integration

To implement a new weather strategy:

1. Implement the strategy interface:
   ```python
   class NewWeatherStrategy(WeatherStrategy):
       service_type: str = "new_service"
       
       def get_weather(self) -> Optional[WeatherResponse]:
           """Implement weather data fetching."""
           pass
       
       def get_expiry_time(self) -> datetime:
           """Implement cache expiry logic."""
           pass
       
       def get_block_size(self, hours_ahead: float) -> BlockSize:
           """Implement block size selection."""
           pass
   ```

2. Add strategy configuration:
   ```yaml
   weather:
     providers:
       new_service:
         timeout: 10
         cache_duration: 3600
         block_sizes: ["1h", "3h", "6h"]
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
- [Strategy Pattern Guide](../../guidelines/strategy.md) 