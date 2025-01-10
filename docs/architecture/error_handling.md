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
    """Base class for API-related errors"""
    def __init__(self, message: str, code: ErrorCode, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.context = context or {}
        super().__init__(message)

class APITimeoutError(APIError):
    """Raised when API requests timeout"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.TIMEOUT, context)

class APIResponseError(APIError):
    """Raised for invalid API responses"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.INVALID_RESPONSE, context)

class APIAuthError(APIError):
    """Raised for authentication failures"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTH_FAILED, context)
```

### Weather Service Errors

```python
class WeatherError(APIError):
    """Base class for weather service errors"""
    pass

class WeatherServiceUnavailable(WeatherError):
    """Raised when no suitable weather service is available"""
    def __init__(self, location: Dict[str, float]):
        super().__init__(
            "No weather service available for location",
            ErrorCode.SERVICE_UNAVAILABLE,
            {"coordinates": location}
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
    AUTH_FAILED = "auth_failed"
    
    # Service errors
    SERVICE_UNAVAILABLE = "service_unavailable"
    SERVICE_ERROR = "service_error"
    
    # Data errors
    MISSING_DATA = "missing_data"
    INVALID_DATA = "invalid_data"
    
    # Business logic errors
    RESERVATION_FAILED = "reservation_failed"
    BOOKING_CONFLICT = "booking_conflict"
```

## Error Handling Patterns

### 1. API Request Pattern

```python
def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
    """Enhanced request helper with retry and error handling."""
    if not self.session:
        self.authenticate()
        
    kwargs.setdefault('timeout', self.timeout)
    
    try:
        response = self.session.request(
            method,
            f"{self.url}/{endpoint.lstrip('/')}",
            **kwargs
        )
        response.raise_for_status()
        return response
        
    except requests.Timeout as e:
        raise APITimeoutError(
            f"Request timed out: {str(e)}",
            {"endpoint": endpoint, "method": method}
        )
        
    except requests.HTTPError as e:
        if e.response.status_code == 401:
            # Try to reauthenticate once
            self.authenticate()
            response = self.session.request(
                method,
                f"{self.url}/{endpoint.lstrip('/')}",
                **kwargs
            )
            response.raise_for_status()
            return response
        raise APIResponseError(
            f"HTTP error: {str(e)}",
            {"status_code": e.response.status_code}
        )
```

### 2. Weather Service Pattern

```python
@handle_errors(WeatherError, "weather", "get weather data")
def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
    """Get weather data with error handling."""
    try:
        data = self._fetch_weather_data(lat, lon, start_time, end_time)
        return [self._parse_weather_data(item) for item in data]
    except Exception as e:
        raise WeatherError(
            f"Failed to get weather data: {str(e)}",
            ErrorCode.SERVICE_ERROR,
            {
                "coordinates": {"lat": lat, "lon": lon},
                "timeframe": {"start": start_time, "end": end_time}
            }
        )
```

## Error Aggregation

The system uses an error aggregator to collect and process errors:

```python
def aggregate_error(
    error_message: str,
    component: str,
    reservation_id: Optional[str] = None
) -> None:
    """Aggregate errors for monitoring and analysis."""
    ErrorAggregator.instance().add_error(
        error_message,
        component,
        reservation_id
    )
```

## Best Practices

### 1. Error Types
- Use specific error types for different scenarios
- Include relevant context in error messages
- Maintain proper error hierarchy
- Use error codes consistently

### 2. Recovery Strategies
- Implement retries for transient failures
- Handle authentication refreshes automatically
- Log errors with appropriate severity
- Cache data when possible to handle service outages

### 3. User Experience
- Provide clear, actionable error messages
- Handle errors gracefully without crashing
- Maintain system stability
- Offer fallback options when available

### 4. Monitoring and Debugging
- Log error context for debugging
- Track error frequencies and patterns
- Set up alerts for critical errors
- Maintain error statistics for analysis
``` 