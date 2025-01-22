"""Error codes for the golf calendar application."""

from enum import Enum

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
    
    # Weather Service Errors
    WEATHER_ERROR = "weather_error"
    WEATHER_SERVICE_ERROR = "weather_service_error"
    WEATHER_PARSE_ERROR = "weather_parse_error"
    WEATHER_REQUEST_ERROR = "weather_request_error"
    WEATHER_TIMEOUT_ERROR = "weather_timeout_error"
    WEATHER_AUTH_ERROR = "weather_auth_error"
    WEATHER_LOCATION_ERROR = "weather_location_error" 