# Error Handling System

## Overview

The weather service system uses a comprehensive error handling framework that provides consistent error reporting, aggregation, and recovery mechanisms across all weather services.

## Error Types

### Base Error Classes

1. **GolfCalError**:
   ```python
   @dataclass
   class GolfCalError(Exception):
       message: str
       code: ErrorCode
       details: Optional[Dict[str, Any]] = None
   ```
   Base exception for all application errors with standardized error codes and details.

2. **APIError**:
   ```python
   class APIError(GolfCalError):
       def __init__(self, message: str, code: ErrorCode, response: Optional[requests.Response] = None)
   ```
   Base class for all API-related errors, including response context.

### Weather-Specific Errors

1. **WeatherError**:
   ```python
   class WeatherError(GolfCalError):
       def __init__(self, message: str, code: ErrorCode = ErrorCode.SERVICE_ERROR)
   ```
   Specific to weather service operations.

2. **API-Related Errors**:
   - `APITimeoutError`: Request timeout errors
   - `APIRateLimitError`: Rate limiting violations
   - `APIResponseError`: Invalid API responses

### Error Codes

```python
class ErrorCode(Enum):
    # Authentication Errors
    AUTH_FAILED = "auth_failed"
    TOKEN_EXPIRED = "token_expired"
    INVALID_CREDENTIALS = "invalid_credentials"
    
    # API Errors
    REQUEST_FAILED = "request_failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    
    # Data Errors
    INVALID_RESPONSE = "invalid_response"
    MISSING_DATA = "missing_data"
    VALIDATION_FAILED = "validation_failed"
    
    # Configuration Errors
    CONFIG_INVALID = "config_invalid"
    CONFIG_MISSING = "config_missing"
    
    # Service Errors
    SERVICE_UNAVAILABLE = "service_unavailable"
    SERVICE_ERROR = "service_error"
```

## Error Handling Utilities

### Context Manager

The `handle_errors` context manager provides consistent error handling across the application:

```python
@contextmanager
def handle_errors(
    error_type: Type[GolfCalError],
    service: str,
    operation: str,
    fallback: Optional[Callable[[], T]] = None
) -> Optional[T]:
    """Handle errors with optional fallback.
    
    Args:
        error_type: Type of error to catch
        service: Service name for error aggregation
        operation: Operation description
        fallback: Optional fallback function
    """
```

Usage example:
```python
with handle_errors(WeatherError, "weather", "fetch forecast", lambda: cached_data):
    return weather_service.get_forecast(lat, lon)
```

## Error Handling Patterns

### 1. API Error Handling

```python
try:
    response = requests.get(url, headers=headers, timeout=10)
    
    if response.status_code == 429:
        raise APIRateLimitError("Rate limit exceeded")
    response.raise_for_status()
    
    data = response.json()
    if not data:
        raise APIResponseError("Empty response")
        
except requests.Timeout:
    raise APITimeoutError("Request timed out")
except requests.RequestException as e:
    raise APIError(f"Request failed: {str(e)}")
```

### 2. Data Validation

```python
if not all(required_fields):
    raise ValidationError(
        "Missing required fields",
        details={"missing": missing_fields}
    )
```

### 3. Service Recovery

```python
with handle_errors(WeatherError, "weather", "get cached data"):
    cached_data = cache.get_weather_data(location, time)
    if cached_data:
        return cached_data
    
    # Fallback to API if cache miss
    with handle_errors(APIError, "weather", "fetch from api"):
        return api.get_weather_data(location, time)
```

## Error Aggregation

Errors are automatically aggregated for monitoring and debugging:

1. **Error Context**:
   - Service name
   - Operation description
   - Stack trace
   - Original error details

2. **Aggregation Methods**:
   ```python
   aggregate_error(
       message: str,
       service: str,
       traceback: Optional[TracebackType]
   )
   ```

## Usage Guidelines

1. **Error Types**:
   - Use specific error types when possible
   - Include relevant context in error details
   - Maintain error hierarchy

2. **Error Handling**:
   - Use context managers for consistent handling
   - Implement appropriate fallbacks
   - Log errors with context

3. **Recovery Strategies**:
   - Cache fallbacks for API errors
   - Retry logic for transient failures
   - Graceful degradation

4. **Error Reporting**:
   - Include sufficient context
   - Use appropriate error codes
   - Maintain error aggregation

## Testing

1. **Unit Tests**:
   - Test error construction
   - Test error handling
   - Test recovery mechanisms

2. **Integration Tests**:
   - Test error propagation
   - Test fallback behavior
   - Test error aggregation

3. **Error Scenarios**:
   - API failures
   - Validation errors
   - Recovery patterns
``` 