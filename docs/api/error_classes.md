# Error Classes

## API Errors

### Base Error

```python
class APIError(Exception):
    """Base class for API-related errors."""
    pass
```

### Specific Errors

```python
class APITimeoutError(APIError):
    """Raised when API requests timeout."""
    pass

class APIResponseError(APIError):
    """Raised for invalid API responses."""
    pass

class APIAuthError(APIError):
    """Raised for authentication failures."""
    pass
```

## Usage Examples

### Error Handling in CRM Implementations

```python
def authenticate(self) -> None:
    try:
        response = self._make_request('POST', '/auth')
        if not response.ok:
            raise APIAuthError("Authentication failed")
    except requests.Timeout:
        raise APITimeoutError("Authentication request timed out")
    except requests.RequestException as e:
        raise APIError(f"Authentication failed: {str(e)}")
```

### Error Handling in Weather Services

```python
def get_weather(self, lat: float, lon: float) -> List[WeatherData]:
    try:
        return self._fetch_forecasts(lat, lon)
    except requests.Timeout:
        raise APITimeoutError("Weather service timeout")
    except requests.RequestException as e:
        raise APIError(f"Weather service error: {str(e)}")
```

## Error Recovery

### Retry Logic

```python
def _make_request_with_retry(self, method: str, url: str, max_retries: int = 3) -> Response:
    for attempt in range(max_retries):
        try:
            response = self.session.request(method, url)
            response.raise_for_status()
            return response
        except requests.Timeout:
            if attempt == max_retries - 1:
                raise APITimeoutError("Max retries exceeded")
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise APIError(str(e))
```

### Authentication Refresh

```python
def _handle_auth_error(self, error: APIAuthError) -> None:
    try:
        self.authenticate()  # Try to refresh authentication
    except APIError:
        raise error  # Re-raise original error if refresh fails
``` 