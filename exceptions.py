"""Centralized error definitions for golf calendar application."""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Type, Callable, TypeVar, ContextManager
from enum import Enum
import requests
from contextlib import contextmanager

T = TypeVar('T')

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

class LegacyAPIError(Exception):
    """Legacy API error class for backward compatibility."""
    def __init__(self, message: str):
        super().__init__(message)

class APITimeoutError(APIError):
    """API timeout error."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.TIMEOUT, details=details)

class APIRateLimitError(APIError):
    """API rate limit error."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, ErrorCode.RATE_LIMITED, details={"retry_after": retry_after})

class APIResponseError(APIError):
    """API response error."""
    def __init__(self, message: str, response: Optional[requests.Response] = None):
        super().__init__(message, ErrorCode.INVALID_RESPONSE, response=response)

class AuthError(GolfCalError):
    """Authentication error."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTH_FAILED, details)

class ConfigError(GolfCalError):
    """Configuration error."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.CONFIG_INVALID, details)

class ValidationError(GolfCalError):
    """Validation error."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.VALIDATION_FAILED, details)

class WeatherError(GolfCalError):
    """Weather service error."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.SERVICE_ERROR, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, details)

class WeatherServiceUnavailable(WeatherError):
    """Weather service unavailable error."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.SERVICE_UNAVAILABLE, details)

class WeatherDataError(WeatherError):
    """Weather data error."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.INVALID_RESPONSE, details)

class CalendarError(GolfCalError):
    """Calendar service error."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.SERVICE_ERROR, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, details)

class CalendarWriteError(CalendarError):
    """Calendar write error."""
    def __init__(self, message: str, file_path: str, details: Optional[Dict[str, Any]] = None):
        if details is None:
            details = {}
        details["file_path"] = file_path
        super().__init__(message, ErrorCode.SERVICE_ERROR, details)

class CalendarEventError(CalendarError):
    """Calendar event error."""
    def __init__(self, message: str, event_type: str, details: Optional[Dict[str, Any]] = None):
        if details is None:
            details = {}
        details["event_type"] = event_type
        super().__init__(message, ErrorCode.VALIDATION_FAILED, details)

@contextmanager
def handle_errors(
    error_type: Type[GolfCalError],
    service: str,
    operation: str,
    fallback: Optional[Callable[[], T]] = None
) -> Optional[T]:
    """Context manager for handling errors and providing fallback behavior."""
    try:
        yield
    except error_type as e:
        from golfcal2.config.error_aggregator import aggregate_error
        aggregate_error(str(e), service, e.__traceback__)
        if fallback:
            return fallback()
        raise
    except Exception as e:
        from golfcal2.config.error_aggregator import aggregate_error
        aggregate_error(f"Unexpected error during {operation}: {str(e)}", service, e.__traceback__)
        if fallback:
            return fallback()
        raise 