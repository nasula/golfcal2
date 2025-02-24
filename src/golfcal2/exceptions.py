"""Centralized error definitions for golf calendar application."""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from typing import TypeVar

import requests

from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.error_codes import ErrorCode


logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class GolfCalError(Exception):
    """Base exception for all golf calendar errors."""
    message: str
    code: ErrorCode
    details: dict[str, Any] | None = None
    
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
        response: requests.Response | None = None,
        details: dict[str, Any] | None = None
    ):
        super().__init__(message, code, details)
        self.response = response

class LegacyAPIError(Exception):
    """Legacy API error class for backward compatibility."""
    def __init__(self, message: str):
        super().__init__(message)

class APITimeoutError(APIError):
    """API timeout error."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.TIMEOUT, details=details)

class APIRateLimitError(APIError):
    """API rate limit error."""
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message, ErrorCode.RATE_LIMITED, details={"retry_after": retry_after})

class APIResponseError(APIError):
    """API response error."""
    def __init__(self, message: str, response: requests.Response | None = None):
        super().__init__(message, ErrorCode.INVALID_RESPONSE, response=response)

class APIValidationError(APIError):
    """API validation error."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.VALIDATION_FAILED, details=details)

class AuthError(GolfCalError):
    """Authentication error."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.AUTH_FAILED, details)

class ConfigError(GolfCalError):
    """Configuration error."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.CONFIG_INVALID, details)

class ValidationError(GolfCalError):
    """Validation error."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.VALIDATION_FAILED, details)

class CalendarError(GolfCalError):
    """Calendar service error."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.SERVICE_ERROR, details: dict[str, Any] | None = None):
        super().__init__(message, code, details)

class CalendarWriteError(CalendarError):
    """Calendar write error."""
    def __init__(self, message: str, file_path: str):
        super().__init__(message, ErrorCode.SERVICE_ERROR, {"file_path": file_path})

class CalendarEventError(CalendarError):
    """Calendar event error."""
    def __init__(self, message: str, event_type: str, details: dict[str, Any] | None = None):
        details = details or {}
        details["event_type"] = event_type
        super().__init__(message, ErrorCode.VALIDATION_FAILED, details)

@contextmanager
def handle_errors(
    error_type: type[GolfCalError],
    service: str,
    operation: str,
    fallback: Callable[[], T] | None = None
) -> AbstractContextManager[T | None]:
    """Handle errors in a context manager.
    
    Args:
        error_type: The error type to catch
        service: The service name
        operation: The operation name
        fallback: Optional fallback function to call if error occurs
        
    Returns:
        Optional result from fallback function if called
    """
    try:
        yield
    except error_type as e:
        # Pass the actual traceback object
        aggregate_error(str(e), service, e.__traceback__)
        
        if fallback:
            return fallback()
        raise
    except Exception as e:
        # Log unexpected error with traceback
        logger.error(
            f"Unexpected error in {service}.{operation}: {e}",
            exc_info=True
        )
        # Pass the actual traceback object
        aggregate_error(str(e), service, e.__traceback__)
        
        if fallback:
            return fallback()
        raise 