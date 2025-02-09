# Authentication Service API

## Overview

The Authentication Service API provides a unified interface for managing authentication across different golf club systems and APIs. It implements a strategy pattern for handling various authentication methods including tokens, cookies, query parameters, and basic authentication.

## Service Interface

### Get Auth Headers

```python
def get_auth_headers(
    self,
    club: str,
    user: str,
    refresh: bool = False
) -> Dict[str, str]:
    """Get authentication headers for club API.
    
    Args:
        club: Golf club identifier
        user: User identifier
        refresh: Whether to force token refresh
        
    Returns:
        Dictionary of auth headers
        
    Raises:
        AuthError: Authentication failed
        ValidationError: Invalid parameters
    """
```

### Authenticate

```python
def authenticate(
    self,
    club: str,
    user: str,
    credentials: Dict[str, Any]
) -> AuthToken:
    """Authenticate user with club system.
    
    Args:
        club: Golf club identifier
        user: User identifier
        credentials: Authentication credentials
        
    Returns:
        Authentication token
        
    Raises:
        AuthError: Authentication failed
        ValidationError: Invalid credentials
    """
```

### Refresh Token

```python
def refresh_token(
    self,
    club: str,
    user: str,
    token: AuthToken
) -> AuthToken:
    """Refresh authentication token.
    
    Args:
        club: Golf club identifier
        user: User identifier
        token: Current auth token
        
    Returns:
        New authentication token
        
    Raises:
        AuthError: Token refresh failed
        ValidationError: Invalid token
    """
```

### Validate Token

```python
def validate_token(
    self,
    club: str,
    user: str,
    token: AuthToken
) -> bool:
    """Validate authentication token.
    
    Args:
        club: Golf club identifier
        user: User identifier
        token: Auth token to validate
        
    Returns:
        True if token is valid
        
    Raises:
        AuthError: Validation failed
    """
```

## Data Models

### Auth Token

```python
@dataclass
class AuthToken:
    token: str                     # Token string
    type: TokenType               # Token type
    expires_at: datetime          # Expiry time (UTC)
    refresh_token: Optional[str]  # Refresh token if available
    scope: Optional[str]          # Token scope
    metadata: Dict[str, Any]      # Additional token data
```

### Token Type

```python
class TokenType(str, Enum):
    BEARER = 'bearer'         # Bearer token
    JWT = 'jwt'              # JWT token
    API_KEY = 'api_key'      # API key
    SESSION = 'session'      # Session token
    COOKIE = 'cookie'        # Cookie-based
```

### Auth Strategy

```python
class AuthStrategy(ABC):
    """Base class for auth strategies."""
    
    @abstractmethod
    def authenticate(
        self,
        credentials: Dict[str, Any]
    ) -> AuthToken:
        """Authenticate using strategy."""
        pass
    
    @abstractmethod
    def refresh(
        self,
        token: AuthToken
    ) -> AuthToken:
        """Refresh token using strategy."""
        pass
    
    @abstractmethod
    def validate(
        self,
        token: AuthToken
    ) -> bool:
        """Validate token using strategy."""
        pass
```

## Usage Examples

### Basic Authentication

```python
from datetime import datetime
from zoneinfo import ZoneInfo

# Initialize service
auth_service = AuthService(config={
    'token_dir': '~/.golfcal2/tokens'
})

# Authenticate user
try:
    credentials = {
        'username': 'john.doe',
        'password': 'secure_password'
    }
    
    token = auth_service.authenticate(
        club='Example Golf Club',
        user='john.doe',
        credentials=credentials
    )
    
    print(f"Authenticated: {token.token}")
    print(f"Expires: {token.expires_at}")
except AuthError as e:
    print(f"Authentication failed: {e}")
```

### Get Headers

```python
# Get auth headers
try:
    headers = auth_service.get_auth_headers(
        club='Example Golf Club',
        user='john.doe'
    )
    
    print("Auth headers:")
    for key, value in headers.items():
        print(f"{key}: {value}")
except AuthError as e:
    print(f"Failed to get headers: {e}")
```

### Token Refresh

```python
# Refresh token
try:
    new_token = auth_service.refresh_token(
        club='Example Golf Club',
        user='john.doe',
        token=current_token
    )
    
    print(f"New token: {new_token.token}")
    print(f"New expiry: {new_token.expires_at}")
except AuthError as e:
    print(f"Token refresh failed: {e}")
```

## Error Handling

### Error Types

```python
class AuthError(Exception):
    """Base class for auth errors."""
    pass

class AuthenticationError(AuthError):
    """Authentication failed."""
    pass

class TokenError(AuthError):
    """Token operation failed."""
    pass

class ValidationError(AuthError):
    """Validation failed."""
    pass
```

### Error Handling Example

```python
try:
    token = auth_service.authenticate(club, user, credentials)
except ValidationError as e:
    print(f"Invalid credentials: {e}")
    # Fix credentials
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    # Handle auth failure
except AuthError as e:
    print(f"Auth error: {e}")
    # General error handling
```

## Configuration

```yaml
auth:
  # Token settings
  token_dir: "~/.golfcal2/tokens"
  token_format: "encrypted"
  
  # Strategy settings
  strategies:
    wisegolf:
      type: "token"
      auth_url: "https://example.com/auth"
      token_url: "https://example.com/token"
      client_id: "golfcal2"
    nexgolf:
      type: "cookie"
      login_url: "https://example.com/login"
      session_cookie: "SESSIONID"
  
  # Security settings
  encryption_key_file: "~/.golfcal2/keys/auth.key"
  token_encryption: true
  secure_storage: true
  
  # Refresh settings
  auto_refresh: true
  refresh_threshold: 300  # seconds
```

## Best Practices

1. **Authentication**
   - Use secure credentials
   - Implement token refresh
   - Handle auth failures
   - Monitor token expiry

2. **Security**
   - Encrypt stored tokens
   - Use secure storage
   - Validate credentials
   - Handle sensitive data

3. **Token Management**
   - Track token expiry
   - Implement auto-refresh
   - Handle revocation
   - Monitor usage

4. **Integration**
   - Handle multiple systems
   - Coordinate auth state
   - Monitor auth status
   - Log auth events 