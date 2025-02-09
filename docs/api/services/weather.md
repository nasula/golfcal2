# Weather Service API

## Overview

The Weather Service API provides a unified interface for accessing weather data from multiple providers using a strategy pattern. It handles data fetching, caching, and error handling while abstracting away the complexities of individual weather data providers.

## Service Interface

### Get Weather Data

```python
def get_weather(
    self,
    location: Location,
    datetime_start: datetime,
    datetime_end: Optional[datetime] = None,
    block_size: Optional[int] = None,
    strategy: Optional[str] = None
) -> WeatherData:
    """Fetch weather data for location and time period.
    
    Args:
        location: Location coordinates and metadata
        datetime_start: Start time for weather data (UTC)
        datetime_end: Optional end time (UTC)
        block_size: Optional block size in hours
        strategy: Optional strategy name to use
        
    Returns:
        Weather data for requested period
        
    Raises:
        WeatherError: Weather data fetch failed
        StrategyError: Strategy error occurred
        ValidationError: Invalid parameters
    """
```

### Register Strategy

```python
def register_strategy(
    self,
    name: str,
    strategy: Type[WeatherStrategy],
    config: Optional[Dict[str, Any]] = None
) -> None:
    """Register new weather data strategy.
    
    Args:
        name: Strategy identifier
        strategy: Strategy class
        config: Optional strategy configuration
        
    Raises:
        StrategyError: Strategy registration failed
    """
```

### List Strategies

```python
def list_strategies(self) -> List[str]:
    """List available weather strategies.
    
    Returns:
        List of registered strategy names
    """
```

### Clear Cache

```python
def clear_cache(
    self,
    strategy: Optional[str] = None,
    older_than: Optional[datetime] = None
) -> None:
    """Clear weather data cache.
    
    Args:
        strategy: Optional strategy to clear cache for
        older_than: Optional timestamp to clear older entries
        
    Raises:
        CacheError: Cache operation failed
    """
```

## Data Models

### Weather Data

```python
@dataclass
class WeatherData:
    temperature: float              # Temperature in Celsius
    precipitation: float           # Precipitation in mm
    wind_speed: float             # Wind speed in m/s
    wind_direction: float         # Wind direction in degrees
    cloud_cover: Optional[float]  # Cloud cover percentage
    humidity: Optional[float]     # Relative humidity percentage
    pressure: Optional[float]     # Air pressure in hPa
    block_size: Optional[int]     # Data block size in hours
    source: str                   # Data source identifier
    timestamp: datetime           # Data timestamp (UTC)
```

### Location

```python
@dataclass
class Location:
    latitude: float               # Latitude in decimal degrees
    longitude: float             # Longitude in decimal degrees
    altitude: Optional[float]    # Altitude in meters
    name: Optional[str]          # Location name
    country: Optional[str]       # Country code
    timezone: Optional[str]      # Timezone identifier
```

## Strategy Implementation

### Base Strategy

```python
class WeatherStrategy(ABC):
    @abstractmethod
    def get_weather(
        self,
        location: Location,
        datetime_start: datetime,
        datetime_end: Optional[datetime] = None,
        block_size: Optional[int] = None
    ) -> WeatherData:
        """Fetch weather data using strategy implementation."""
        pass
    
    @abstractmethod
    def validate_parameters(
        self,
        location: Location,
        datetime_start: datetime,
        datetime_end: Optional[datetime] = None,
        block_size: Optional[int] = None
    ) -> None:
        """Validate input parameters."""
        pass
```

### Example Strategy

```python
class MetWeatherStrategy(WeatherStrategy):
    def get_weather(
        self,
        location: Location,
        datetime_start: datetime,
        datetime_end: Optional[datetime] = None,
        block_size: Optional[int] = None
    ) -> WeatherData:
        # Validate parameters
        self.validate_parameters(location, datetime_start, datetime_end, block_size)
        
        # Build API request
        params = self._build_request_params(
            location, datetime_start, datetime_end, block_size
        )
        
        try:
            # Make API request
            response = self._make_request(params)
            
            # Parse response
            weather_data = self._parse_response(response)
            
            return weather_data
            
        except Exception as e:
            raise WeatherError(f"Failed to fetch weather data: {e}")
```

## Usage Examples

### Basic Usage

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Initialize service
weather_service = WeatherService(config={
    'cache_dir': '~/weather_cache',
    'default_strategy': 'met'
})

# Get weather data
try:
    location = Location(
        latitude=60.1699,
        longitude=24.9384,
        name='Helsinki'
    )
    
    weather = weather_service.get_weather(
        location=location,
        datetime_start=datetime.now(ZoneInfo('UTC')),
        block_size=1
    )
    
    print(f"Temperature: {weather.temperature}°C")
    print(f"Wind: {weather.wind_speed} m/s")
except WeatherError as e:
    print(f"Failed to get weather: {e}")
```

### Custom Strategy

```python
# Register custom strategy
try:
    weather_service.register_strategy(
        name='custom',
        strategy=CustomWeatherStrategy,
        config={'api_key': 'your-api-key'}
    )
    
    # Use custom strategy
    weather = weather_service.get_weather(
        location=location,
        datetime_start=datetime.now(ZoneInfo('UTC')),
        strategy='custom'
    )
except StrategyError as e:
    print(f"Strategy error: {e}")
```

## Error Handling

### Error Types

```python
class WeatherError(Exception):
    """Base class for weather service errors."""
    pass

class StrategyError(WeatherError):
    """Strategy related errors."""
    pass

class ValidationError(WeatherError):
    """Parameter validation errors."""
    pass

class CacheError(WeatherError):
    """Cache operation errors."""
    pass
```

### Error Handling Example

```python
try:
    weather = weather_service.get_weather(location, datetime_start)
except ValidationError as e:
    print(f"Invalid parameters: {e}")
    # Fix parameters
except StrategyError as e:
    print(f"Strategy error: {e}")
    # Try different strategy
except WeatherError as e:
    print(f"Weather error: {e}")
    # General error handling
```

## Configuration

```yaml
weather:
  # Strategy settings
  default_strategy: 'met'
  fallback_strategy: 'openmeteo'
  
  # Cache settings
  cache_dir: "~/weather_cache"
  cache_ttl: 3600  # seconds
  
  # Request settings
  timeout: 30  # seconds
  max_retries: 3
  
  # Data settings
  default_block_size: 1  # hours
  max_forecast_days: 10
```

## Best Practices

1. **Strategy Selection**
   - Use appropriate strategy for location
   - Handle strategy failures gracefully
   - Configure fallback strategies
   - Monitor strategy performance

2. **Data Handling**
   - Validate input parameters
   - Use appropriate block sizes
   - Handle missing data points
   - Convert units consistently

3. **Caching**
   - Implement efficient caching
   - Clear old cache entries
   - Handle cache failures
   - Monitor cache performance

4. **Error Management**
   - Use specific error types
   - Implement retry logic
   - Log error details
   - Monitor error rates 