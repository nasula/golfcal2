# Base API Implementation

## Overview

The Base API provides a foundation for all API clients in the application, implementing common functionality like authentication, request handling, and error management.

## Core Components

### 1. BaseAPI Class

```python
class BaseAPI(LoggerMixin):
    DEFAULT_TIMEOUT = (7, 20)  # (connection timeout, read timeout)
    DEFAULT_RETRY_TOTAL = 3
    DEFAULT_RETRY_BACKOFF_FACTOR = 0.5
    DEFAULT_RETRY_STATUS_FORCELIST = [408, 429, 500, 502, 503, 504]
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Dict[str, Any]):
        # Initialize API client with authentication and configuration
        pass
```

### 2. Request Handling

The base implementation provides robust request handling with:

1. **Retry Configuration**
   ```python
   retry_strategy = Retry(
       total=DEFAULT_RETRY_TOTAL,
       backoff_factor=DEFAULT_RETRY_BACKOFF_FACTOR,
       status_forcelist=DEFAULT_RETRY_STATUS_FORCELIST,
       allowed_methods=["GET", "POST"]
   )
   ```

2. **Session Management**
   - Automatic retry handling
   - Connection pooling
   - Cookie persistence
   - Header management

3. **Response Validation**
   ```python
   def _validate_response(self, response: requests.Response) -> None:
       try:
           response.raise_for_status()
       except requests.exceptions.HTTPError as e:
           error_msg = f"HTTP {response.status_code}"
           try:
               error_data = response.json()
               if isinstance(error_data, dict):
                   error_msg = error_data.get('message', error_data.get('error', str(e)))
           except (ValueError, AttributeError):
               error_msg = response.text or str(e)
           
           raise APIResponseError(f"Request failed: {error_msg}")
   ```

## Error Handling

### 1. Error Classes

```python
class GolfCalError(Exception):
    """Base error class for all application errors."""
    def __init__(self, message: str, code: ErrorCode, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

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
```

### 2. Error Codes

Common error codes used throughout the application:

- `AUTH_FAILED`: Authentication failures
- `CONFIG_INVALID`: Configuration issues
- `VALIDATION_FAILED`: Data validation errors
- `SERVICE_ERROR`: General service errors
- `REQUEST_FAILED`: API request failures

### 3. Error Recovery

The system implements multiple layers of error recovery:

1. **Request Level**
   - Automatic retries for transient failures
   - Exponential backoff
   - Status code based retry decisions

2. **Authentication Level**
   - Token refresh on expiry
   - Session renewal
   - Credential rotation

3. **Service Level**
   - Fallback implementations
   - Cached data usage
   - Degraded mode operation

## Authentication Integration

### 1. Authentication Service

The BaseAPI integrates with the AuthService for credential management:

```python
def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Dict[str, Any]):
    self.auth_service = auth_service
    auth_type = club_details.get('auth_type', 'token_appauth')
    cookie_name = club_details.get('cookie_name', '')
    self.headers = auth_service.create_headers(auth_type, cookie_name, membership.auth_details)
```

### 2. Authentication Strategies

Supports multiple authentication methods:

1. **Token Authentication**
   ```python
   headers = {
       'Authorization': auth_details['token'],
       'Accept': 'application/json'
   }
   ```

2. **Cookie Authentication**
   ```python
   headers = {
       'Cookie': f"{cookie_name}={auth_details['cookie_value']}",
       'Accept': 'application/json'
   }
   ```

3. **Query Authentication**
   ```python
   url = f"{base_url}?token={auth_details['token']}"
   ```

## Best Practices

1. **Request Handling**
   - Use appropriate timeouts
   - Implement retry strategies
   - Validate responses thoroughly

2. **Error Management**
   - Use specific error types
   - Include detailed error messages
   - Provide recovery options

3. **Authentication**
   - Secure credential storage
   - Implement token refresh
   - Handle session expiry

4. **Logging**
   - Log request/response details
   - Track authentication status
   - Monitor error patterns

## Implementation Example

Example of implementing a new API client:

```python
class CustomAPI(BaseAPI):
    def __init__(self, club_details: Dict[str, Any], membership: Dict[str, Any]):
        super().__init__(
            base_url="https://api.example.com/v1",
            auth_service=AuthService(),
            club_details=club_details,
            membership=membership
        )
    
    def get_data(self) -> Dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/data",
                timeout=self.DEFAULT_TIMEOUT
            )
            self._validate_response(response)
            return response.json()
        except requests.Timeout as e:
            raise APITimeoutError("Request timed out") from e
        except requests.RequestException as e:
            raise APIError(f"Request failed: {str(e)}") from e
``` 