# Weather Service Interface

## Overview

The weather service interface defines the standard contract that all weather service implementations must follow. It provides a consistent way to fetch and process weather data from different providers while maintaining uniform data formats and error handling.

## Base Class

```python
class WeatherService(EnhancedLoggerMixin):
    """Base class for all weather services."""
    
    def __init__(self, local_tz, utc_tz):
        """Initialize weather service with timezone information.
        
        Args:
            local_tz: Local timezone object
            utc_tz: UTC timezone object
        """
        super().__init__()
        self.local_tz = local_tz
        self.utc_tz = utc_tz
        self.set_correlation_id()  # Generate unique ID for this service instance
    
    @log_execution(level='DEBUG')
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Get weather data for location and time range.
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            start_time: Start time for forecast
            end_time: End time for forecast
            
        Returns:
            List of WeatherData objects containing forecast data
        """
        pass
    
    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Abstract method to be implemented by subclasses for actual API calls.
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            start_time: Start time for forecast
            end_time: End time for forecast
            
        Returns:
            List of WeatherData objects containing forecast data
        """
        raise NotImplementedError("Subclasses must implement _fetch_forecasts")
    
    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size based on forecast time.
        
        Args:
            hours_ahead: Number of hours ahead of current time
            
        Returns:
            Block size in hours (e.g., 1 for hourly forecasts)
        """
        raise NotImplementedError("Subclasses must implement get_block_size")
```

## Data Models

### WeatherData Class

```python
@dataclass
class WeatherData:
    """Weather data container for standardized forecast data."""
    temperature: float
    precipitation: float
    precipitation_probability: Optional[float]
    wind_speed: float
    wind_direction: Optional[str]
    symbol: str
    elaboration_time: datetime
    thunder_probability: Optional[float] = None
```

### Weather Codes

```python
class WeatherCode(str, Enum):
    """Standard weather codes used across all weather services."""
    CLEARSKY_DAY = 'clearsky_day'
    CLEARSKY_NIGHT = 'clearsky_night'
    FAIR_DAY = 'fair_day'
    FAIR_NIGHT = 'fair_night'
    PARTLY_CLOUDY_DAY = 'partlycloudy_day'
    PARTLY_CLOUDY_NIGHT = 'partlycloudy_night'
    CLOUDY = 'cloudy'
    FOG = 'fog'
    LIGHTRAIN = 'lightrain'
    RAIN = 'rain'
    HEAVYRAIN = 'heavyrain'
    # ... and many more weather conditions
```

## Error Handling

The interface includes comprehensive error handling through specialized exception classes:

```python
from golfcal2.exceptions import (
    WeatherError,          # Base class for weather-specific errors
    APIError,             # Base class for API-related errors
    APITimeoutError,      # For request timeouts
    APIRateLimitError,    # For rate limit violations
    APIResponseError,     # For invalid API responses
    ErrorCode,            # Enumeration of error codes
    handle_errors         # Context manager for error handling
)
```

## Logging

The interface inherits from `EnhancedLoggerMixin` which provides:

1. **Correlation IDs**: Unique identifiers for tracking requests across services
2. **Context Logging**: Ability to add context to log messages
3. **Log Levels**:
   - DEBUG: API interactions and detailed processing
   - INFO: Service operations
   - WARNING: Service issues
   - ERROR: Critical failures

## Implementation Requirements

When implementing a new weather service:

1. **Required Methods**:
   - `_fetch_forecasts()`: Implement actual API calls
   - `get_block_size()`: Define forecast block sizes
   - Optional: Override `get_weather()` for custom behavior

2. **Error Handling**:
   - Use provided exception classes
   - Implement proper rate limiting
   - Handle API-specific errors

3. **Data Conversion**:
   - Convert provider-specific weather codes to standard codes
   - Convert units to metric system
   - Handle timezone conversions

4. **Caching**:
   - Implement appropriate caching strategy
   - Handle cache invalidation
   - Respect provider's caching requirements

5. **Testing**:
   - Unit tests for data conversion
   - Integration tests for API calls
   - Error handling tests
