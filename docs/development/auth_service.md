# Authentication Service

## Overview

The Authentication Service provides a flexible authentication framework supporting multiple authentication strategies for different CRM systems. It uses the Strategy pattern to handle various authentication methods while maintaining a consistent interface.

## Core Components

### 1. AuthService Class

```python
class AuthService:
    """Service for handling authentication."""
    
    def __init__(self):
        self._strategies = {
            'token_appauth': TokenAppAuthStrategy(),
            'cookie': CookieAuthStrategy(),
            'query': QueryAuthStrategy()
        }
    
    def get_strategy(self, auth_type: str) -> AuthStrategy:
        """Get authentication strategy for given type."""
        return self._strategies.get(auth_type, UnsupportedAuthStrategy())
```

### 2. Authentication Strategies

#### TokenAppAuthStrategy
```python
class TokenAppAuthStrategy(AuthStrategy):
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        return {
            'Authorization': auth_details['token'],
            'x-session-type': 'wisegolf',
            'Accept': 'application/json, text/plain, */*'
        }

    def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> str:
        url = club_details['url']
        return f"{url}&appauth={membership.auth_details['appauth']}"
```

#### CookieAuthStrategy
```python
class CookieAuthStrategy(AuthStrategy):
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        if 'NGLOCALE=fi; JSESSIONID' in cookie_name:
            # NexGolf format
            return {'Cookie': f"NGLOCALE=fi; JSESSIONID={auth_details['cookie_value']}"}
        elif 'wisenetwork_session' in cookie_name:
            # WiseGolf format
            return {'Cookie': f"wisenetwork_session={auth_details['cookie_value']}"}
        else:
            # Default format
            return {'Cookie': f"{cookie_name}={auth_details['cookie_value']}"}
```

#### QueryAuthStrategy
```python
class QueryAuthStrategy(AuthStrategy):
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        }
        if 'cookie' in auth_details:
            headers['If-None-Match'] = f'"{auth_details["cookie"]}"'
        return headers

    def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> str:
        url = club_details['url']
        if 'token' in membership.auth_details:
            url = f"{url}?token={membership.auth_details['token']}"
        return url
```

## Authentication Types

### 1. Token Authentication (token_appauth)
- Used by: WiseGolf, TeeTime
- Flow:
  - Initial token request with credentials
  - Token stored in auth_details
  - Token included in Authorization header
  - Automatic token refresh when expired
- Headers:
  ```python
  {
      'Authorization': 'Bearer <token>',
      'Content-Type': 'application/json'
  }
  ```

### 2. Cookie Authentication (cookie)
- Used by: NexGolf
- Flow:
  - Session creation with credentials
  - Cookie stored in auth_details
  - Cookie included in subsequent requests
  - CSRF token handling where required
- Headers:
  ```python
  {
      'Cookie': '<session_cookie>',
      'X-CSRF-Token': '<csrf_token>'
  }
  ```

### 3. Query Authentication (query)
- Used by: Legacy systems
- Flow:
  - Credentials included as URL parameters
  - Session maintained through query params
  - Less secure, used only for legacy support
- URL Format:
  - `https://api.example.com/endpoint?token=<token>`

## Configuration

### User Configuration Example
```json
{
  "Example User": {
    "name": "Example User",
    "email": "user@example.com",
    "handicap": 24.5,
    "memberships": [
      {
        "club": "Example Golf Club",
        "clubAbbreviation": "EGC",
        "auth_details": {
          "username": "your_username",
          "password": "your_password"
        }
      }
    ]
  }
}
```

### Club Configuration
```json
{
  "Example Golf Club": {
    "type": "wisegolf",
    "name": "Example Golf Club",
    "url": "https://api.example.com",
    "auth_type": "token_appauth",
    "cookie_name": "session_cookie"
  }
}
```

## Error Handling

### 1. Authentication Errors
- Token Expired
  - Attempt token refresh
  - Request new credentials
  - Fall back to alternative auth method

- Invalid Credentials
  - Clear stored credentials
  - Prompt for new credentials
  - Verify club configuration

- Session Expired
  - Create new session
  - Handle CSRF token refresh
  - Maintain cookie jar

### 2. Recovery Strategies
- Rate Limiting
  - Implement exponential backoff
  - Rotate credentials if available
  - Cache successful tokens

- Invalid Token Format
  - Validate token format
  - Check auth strategy compatibility
  - Verify API version

- Permission Denied
  - Verify membership status
  - Check booking privileges
  - Validate club access rights

## Best Practices

1. **Security**
   - Never store raw credentials
   - Use secure token storage
   - Implement token rotation
   - Handle session expiry

2. **Error Recovery**
   - Implement automatic retries
   - Use exponential backoff
   - Cache valid credentials
   - Handle rate limits

3. **Configuration**
   - Validate auth configuration
   - Check required fields
   - Verify endpoint URLs
   - Test auth flows

4. **Monitoring**
   - Log authentication attempts
   - Track token expiry
   - Monitor rate limits
   - Alert on failures

## Implementation Example

Example of implementing a new authentication strategy:

```python
class CustomAuthStrategy(AuthStrategy):
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        return {
            'X-Custom-Auth': auth_details['custom_token'],
            'X-API-Version': '2.0',
            'Accept': 'application/json'
        }

    def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> str:
        base_url = club_details['url']
        api_key = membership.auth_details.get('api_key')
        if api_key:
            return f"{base_url}?key={api_key}"
        return base_url

class CustomAuthAPI(BaseAPI):
    def __init__(self, club_details: Dict[str, Any], membership: Dict[str, Any]):
        auth_service = AuthService()
        auth_service._strategies['custom'] = CustomAuthStrategy()
        super().__init__(
            base_url="https://api.example.com",
            auth_service=auth_service,
            club_details=club_details,
            membership=membership
        )
``` 