"""Centralized error definitions for golf calendar application."""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum
import requests

class ErrorCode(Enum):
    """Enumeration of all possible error codes."""
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

@dataclass
class GolfCalError(Exception):
    """Base exception for all golf calendar errors."""
    message: str
    code: ErrorCode
    details: Optional[Dict[str, Any]] = None
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Code: {self.code.value}, Details: {self.details})"
        return f"{self.message} (Code: {self.code.value})"

# Keep old APIError for compatibility but inherit from GolfCalError
class APIError(GolfCalError):
    """Base class for API-related errors."""
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.REQUEST_FAILED,
        response: Optional[requests.Response] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, details)
        self.response = response

# Legacy compatibility classes - these maintain the old behavior
class LegacyAPIError(Exception):
    """Legacy API error for backward compatibility."""
    def __init__(self, message: str):
        super().__init__(message)

class APITimeoutError(APIError):
    """Request timeout errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.TIMEOUT, details=details)

class APIRateLimitError(APIError):
    """Rate limiting errors."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(message, ErrorCode.RATE_LIMITED, details=details)

class APIResponseError(APIError):
    """Invalid API response errors."""
    def __init__(self, message: str, response: Optional[requests.Response] = None):
        super().__init__(message, ErrorCode.INVALID_RESPONSE, response=response)

class AuthError(GolfCalError):
    """Authentication-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTH_FAILED, details)

class ConfigError(GolfCalError):
    """Configuration-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.CONFIG_INVALID, details)

class ValidationError(GolfCalError):
    """Data validation errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.VALIDATION_FAILED, details)

class WeatherError(GolfCalError):
    """Weather service specific errors."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.SERVICE_ERROR, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, details)

class CalendarError(GolfCalError):
    """Calendar service specific errors."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.SERVICE_ERROR, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, details)

class CalendarWriteError(CalendarError):
    """Error writing calendar to file."""
    def __init__(self, message: str, file_path: str, details: Optional[Dict[str, Any]] = None):
        error_details = {"file_path": file_path}
        if details:
            error_details.update(details)
        super().__init__(message, ErrorCode.SERVICE_ERROR, error_details)

class CalendarEventError(CalendarError):
    """Error creating or processing calendar events."""
    def __init__(self, message: str, event_type: str, details: Optional[Dict[str, Any]] = None):
        error_details = {"event_type": event_type}
        if details:
            error_details.update(details)
        super().__init__(message, ErrorCode.INVALID_RESPONSE, error_details)

# Error handling utilities
from contextlib import contextmanager
from typing import Type, TypeVar, Callable
from golfcal2.config.error_aggregator import aggregate_error

T = TypeVar('T')

@contextmanager
def handle_errors(
    error_type: Type[GolfCalError],
    service: str,
    operation: str,
    fallback: Optional[Callable[[], T]] = None
) -> Optional[T]:
    """Context manager for consistent error handling.
    
    Args:
        error_type: Type of error to catch and convert
        service: Service name for error aggregation
        operation: Description of the operation being performed
        fallback: Optional fallback function to call on error
        
    Yields:
        None if no fallback provided, or the result of the fallback function
        
    Example:
        with handle_errors(APIError, "weather", "fetch forecast", lambda: cached_data):
            return weather_service.get_forecast(lat, lon)
    """
    try:
        yield
    except error_type as e:
        aggregate_error(str(e), service, getattr(e, "__traceback__", None))
        if fallback:
            return fallback()
        raise
    except Exception as e:
        error = error_type(
            f"Unexpected error during {operation}: {str(e)}",
            ErrorCode.SERVICE_ERROR,
            details={"original_error": str(e)}
        )
        aggregate_error(str(error), service, getattr(e, "__traceback__", None))
        if fallback:
            return fallback()
        raise error from e 