# Error Handling

## Overview

The application uses a hierarchical error system for consistent error handling across all components. Error handling is designed to be:
- Type-safe and predictable
- Context-aware
- Recoverable where possible
- User-friendly

## Error Classes

### Base Errors

```python
class APIError(Exception):
    """Base class for API-related errors."""
    def __init__(self, message: str, code: ErrorCode, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.context = context or {}
        super().__init__(message)

class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.RATE_LIMITED, context)

class APITimeoutError(APIError):
    """Raised when API requests timeout."""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.TIMEOUT, context)

class APIResponseError(APIError):
    """Raised for invalid API responses."""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.INVALID_RESPONSE, context)
```

### Weather Service Errors

```python
class WeatherError(APIError):
    """Base class for weather service errors."""
    def __init__(self, message: str, service_type: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            ErrorCode.WEATHER_SERVICE_ERROR,
            {'service_type': service_type, **(context or {})}
        )

class WeatherServiceUnavailable(WeatherError):
    """Raised when weather service is unavailable."""
    def __init__(self, message: str, service_type: str):
        super().__init__(
            message,
            service_type,
            {'error_type': 'service_unavailable'}
        )

class WeatherServiceRateLimited(WeatherError):
    """Raised when weather service rate limit is exceeded."""
    def __init__(self, message: str, service_type: str):
        super().__init__(
            message,
            service_type,
            {'error_type': 'rate_limited'}
        )

class WeatherLocationError(WeatherError):
    """Raised for invalid location coordinates."""
    def __init__(self, message: str, service_type: str):
        super().__init__(
            message,
            service_type,
            {'error_type': 'invalid_location'}
        )
```

### CRM Errors

```python
class CRMError(APIError):
    """Base class for CRM-related errors"""
    pass

class ReservationError(CRMError):
    """Raised for reservation-related errors"""
    pass
```

## Error Codes

```python
class ErrorCode(Enum):
    # General API errors
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"
    RATE_LIMITED = "rate_limited"
    
    # Service errors
    WEATHER_SERVICE_ERROR = "weather_service_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    
    # Data errors
    INVALID_LOCATION = "invalid_location"
    INVALID_PARAMETERS = "invalid_parameters"
    
    # Cache errors
    CACHE_ERROR = "cache_error"
    CACHE_EXPIRED = "cache_expired"
```

## Error Handling Patterns

### 1. Strategy Pattern Error Handling

```python
class WeatherStrategy(ABC):
    """Base strategy for weather services."""
    
    def get_weather(self) -> Optional[WeatherResponse]:
        """Get weather data with error handling."""
        try:
            response = self._fetch_forecasts(
                self.context.lat,
                self.context.lon,
                self.context.start_time,
                self.context.end_time
            )
            
            if response:
                return self._parse_response(response)
            return None
            
        except APIError as e:
            self.error(f"Weather service error: {str(e)}")
            raise WeatherError(str(e), self.service_type)
            
        except Exception as e:
            self.error(f"Unexpected error: {str(e)}")
            raise WeatherServiceUnavailable(str(e), self.service_type)
```

### 2. Service Level Error Handling

```python
class WeatherService:
    """Weather service with fallback handling."""
    
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        service_type: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data with fallback handling."""
        try:
            # Try primary service
            service_type = service_type or self._select_service_for_location(lat, lon)
            strategy = self._get_strategy(service_type)
            response = strategy.get_weather()
            
            # Try fallback if primary fails
            if not response and service_type == 'openmeteo':
                met_strategy = self._get_strategy('met')
                response = met_strategy.get_weather()
            
            return response
            
        except Exception as e:
            aggregate_error(str(e), "weather_service", str(e.__traceback__))
            return None
```

## Error Aggregation

The system uses an error aggregator for monitoring and analysis:

```python
def aggregate_error(
    error_message: str,
    component: str,
    traceback: Optional[str] = None
) -> None:
    """Aggregate errors for monitoring."""
    ErrorAggregator.instance().add_error(
        error_message=error_message,
        component=component,
        traceback=traceback,
        timestamp=datetime.now(ZoneInfo('UTC'))
    )
```

## Best Practices

### 1. Error Types
- Use specific error types for different scenarios
- Include service type and context in errors
- Maintain proper error hierarchy
- Use error codes consistently

### 2. Recovery Strategies
- Implement service fallbacks
- Use caching for resilience
- Handle rate limiting gracefully
- Log errors with appropriate context

### 3. User Experience
- Provide clear error messages
- Handle errors without crashing
- Offer fallback options
- Maintain system stability

### 4. Monitoring
- Aggregate errors for analysis
- Track error patterns
- Monitor service health
- Set up appropriate alerts
``` 