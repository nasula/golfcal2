"""
Authentication service for golf calendar application.
"""

from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol
from urllib.parse import urljoin

from golfcal2.config.types import AppConfig
from golfcal2.config.types import ClubConfig
from golfcal2.models.user import Membership
from golfcal2.utils.logging_utils import LoggerMixin


# Use TYPE_CHECKING for imports only needed for type hints
if TYPE_CHECKING:
    from golfcal2.models.golf_club import GolfClub

class AuthStrategy(Protocol):
    """Protocol for authentication strategies."""
    
    @abstractmethod
    def get_auth_header(self) -> dict[str, str]:
        """Get authentication header."""
        ...

    @abstractmethod
    def get_auth_cookie(self) -> dict[str, str]:
        """Get authentication cookie."""
        ...

    @abstractmethod
    def get_auth_token(self) -> str:
        """Get authentication token."""
        ...

    @abstractmethod
    def build_full_url(self, base_url: str, path: str) -> str:
        """Build full URL with authentication."""
        ...

class BasicAuthStrategy(AuthStrategy):
    """Basic authentication strategy."""

    def __init__(self, auth_details: dict[str, Any]) -> None:
        """Initialize basic auth strategy."""
        self.auth_details = auth_details

    def get_auth_header(self) -> dict[str, str]:
        """Get basic auth header."""
        token = self.auth_details.get('token', '')
        return {'Authorization': f'Bearer {token}'} if token else {}

    def get_auth_cookie(self) -> dict[str, str]:
        """Get basic auth cookie."""
        return {}

    def get_auth_token(self) -> str:
        """Get basic auth token."""
        return str(self.auth_details.get('token', ''))

    def build_full_url(self, base_url: str, path: str) -> str:
        """Build full URL with basic auth."""
        return urljoin(base_url, path)

class CookieAuthStrategy(AuthStrategy):
    """Cookie-based authentication strategy."""

    def __init__(self, auth_details: dict[str, Any]) -> None:
        """Initialize cookie auth strategy."""
        self.auth_details = auth_details

    def get_auth_header(self) -> dict[str, str]:
        """Get cookie auth header."""
        return {}

    def get_auth_cookie(self) -> dict[str, str]:
        """Get cookie auth cookie."""
        cookie_value = self.auth_details.get('cookie_value', '')
        return {'Cookie': cookie_value} if cookie_value else {}

    def get_auth_token(self) -> str:
        """Get cookie auth token."""
        return str(self.auth_details.get('cookie_value', ''))

    def build_full_url(self, base_url: str, path: str) -> str:
        """Build full URL with cookie auth."""
        return urljoin(base_url, path)

class QueryAuthStrategy(AuthStrategy):
    """Query parameter-based authentication strategy."""

    def __init__(self, auth_details: dict[str, Any]) -> None:
        """Initialize query auth strategy."""
        self.auth_details = auth_details

    def get_auth_header(self) -> dict[str, str]:
        """Get query auth header."""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        }
        
        # Add If-None-Match header if cookie is present
        if 'cookie' in self.auth_details:
            headers['If-None-Match'] = f'"{self.auth_details["cookie"]}"'
        
        return headers

    def get_auth_cookie(self) -> dict[str, str]:
        """Get query auth cookie."""
        return {}

    def get_auth_token(self) -> str:
        """Get query auth token."""
        return str(self.auth_details.get('token', ''))

    def build_full_url(self, base_url: str, path: str) -> str:
        """Build full URL with query auth."""
        url = urljoin(base_url, path)
        # Token is sent as a query parameter
        if 'token' in self.auth_details:
            url = f"{url}?token={self.auth_details['token']}"
        return url

class TokenAppAuthStrategy(AuthStrategy):
    """Token app authentication strategy for WiseGolf."""

    def __init__(self, auth_details: dict[str, Any]) -> None:
        """Initialize token app auth strategy."""
        self.auth_details = auth_details

    def get_auth_header(self) -> dict[str, str]:
        """Get token app auth header."""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'x-session-type': 'wisegolf'
        }
        
        if 'token' in self.auth_details:
            headers['Authorization'] = f'Bearer {self.auth_details["token"]}'
            
        return headers

    def get_auth_cookie(self) -> dict[str, str]:
        """Get token app auth cookie."""
        return {}

    def get_auth_token(self) -> str:
        """Get token app auth token."""
        return str(self.auth_details.get('token', ''))

    def build_full_url(self, base_url: str, path: str) -> str:
        """Build full URL with token app auth."""
        url = urljoin(base_url, path)
        if 'appauth' in self.auth_details:
            url = f"{url}?appauth={self.auth_details['appauth']}"
        return url

class UnsupportedAuthStrategy(AuthStrategy):
    """Fallback strategy for unsupported authentication types."""

    def get_auth_header(self) -> dict[str, str]:
        """Get unsupported auth header."""
        return {}

    def get_auth_cookie(self) -> dict[str, str]:
        """Get unsupported auth cookie."""
        return {}

    def get_auth_token(self) -> str:
        """Get unsupported auth token."""
        return ""

    def build_full_url(self, base_url: str, path: str) -> str:
        """Build full URL with unsupported auth."""
        return urljoin(base_url, path)

class AuthService(LoggerMixin):
    """Service for handling authentication."""
    
    def __init__(self, config: AppConfig):
        """Initialize service."""
        super().__init__()
        self.config = config
        self.strategy: AuthStrategy | None = None
        self._current_auth_details: dict[str, Any] | None = None
    
    def _ensure_strategy(self, auth_details: dict[str, Any]) -> None:
        """Ensure strategy is initialized with current auth details."""
        # Only initialize if auth details have changed or strategy is not set
        if (self.strategy is None or 
            self._current_auth_details != auth_details):
            self.strategy = self._get_strategy(auth_details)
            self._current_auth_details = auth_details.copy()
    
    def get_auth_headers(self, club: 'GolfClub', auth_details: dict[str, Any]) -> dict[str, str]:
        """Get authentication headers for a club."""
        try:
            # Get club configuration and ensure it's a dict
            config_value: ClubConfig | dict[str, Any] = self.config.clubs.get(club.name, {})
            club_config: dict[str, Any] = dict(config_value) if isinstance(config_value, dict) else {}
            
            # Get auth type from auth_details first, fall back to club config
            auth_type = auth_details.get('type') or club_config.get('auth_type', 'none')
            
            # Initialize strategy based on auth type
            self._ensure_strategy(auth_details)
            
            # Handle different authentication types
            if auth_type == 'basic':
                return self._get_basic_auth_headers(auth_details)
            elif auth_type == 'token':
                return self._get_token_auth_headers(auth_details)
            elif auth_type == 'token_appauth':
                return self._get_token_app_auth_headers(auth_details)
            elif auth_type in ['cookie', 'wisegolf0', 'nexgolf']:
                return self._get_cookie_auth_headers(auth_details)
            else:
                self.logger.debug(f"No authentication required for club {club.name}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Failed to get auth headers for club {club.name}: {e}")
            return {}
    
    def _get_basic_auth_headers(self, auth_details: dict[str, Any]) -> dict[str, str]:
        """Get headers for basic authentication."""
        headers = {}
        if 'username' in auth_details and 'password' in auth_details:
            import base64
            auth_string = f"{auth_details['username']}:{auth_details['password']}"
            auth_bytes = auth_string.encode('ascii')
            base64_bytes = base64.b64encode(auth_bytes)
            base64_string = base64_bytes.decode('ascii')
            headers['Authorization'] = f'Basic {base64_string}'
        return headers
    
    def _get_token_auth_headers(self, auth_details: dict[str, Any]) -> dict[str, str]:
        """Get headers for token authentication."""
        headers = {}
        if 'token' in auth_details:
            headers['Authorization'] = f'Bearer {auth_details["token"]}'
        return headers
    
    def _get_token_app_auth_headers(self, auth_details: dict[str, Any]) -> dict[str, str]:
        """Get headers for token app authentication."""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'x-session-type': 'wisegolf'
        }
        
        if 'token' in auth_details:
            headers['Authorization'] = f'Bearer {auth_details["token"]}'
            
        return headers
    
    def _get_cookie_auth_headers(self, auth_details: dict[str, Any]) -> dict[str, str]:
        """Get headers for cookie authentication."""
        headers = {}
        if 'cookie_value' in auth_details:
            auth_type = auth_details.get('type', '')
            cookie_name = auth_details.get('cookie_name', '')
            cookie_value = auth_details['cookie_value']
            
            self.logger.debug(f"Processing cookie auth with type: {auth_type}, name: {cookie_name}, value: {cookie_value}")
            
            # For WiseGolf0, we need to prefix with wisenetwork_session=
            if auth_type == 'wisegolf0':
                cookie_name = cookie_name or 'wisenetwork_session'
                # Ensure cookie value is properly formatted
                if not cookie_value.startswith(f"{cookie_name}="):
                    headers['Cookie'] = f'{cookie_name}={cookie_value}'
                else:
                    headers['Cookie'] = cookie_value
            elif auth_type == 'nexgolf':
                # For NexGolf, use JSESSIONID and include X-Auth-Token if available
                cookie_name = cookie_name or 'JSESSIONID'
                headers['Cookie'] = f'NGLOCALE=fi; {cookie_name}={cookie_value}'
                # Add X-Auth-Token if available (from token field)
                if 'X-Auth-Token' in auth_details:
                    headers['X-Auth-Token'] = auth_details['X-Auth-Token']
                elif 'token' in auth_details:
                    headers['X-Auth-Token'] = auth_details['token']
                elif 'x_auth_token' in auth_details:
                    headers['X-Auth-Token'] = auth_details['x_auth_token']
                self.logger.debug(f"Generated headers for NexGolf: {headers}")
            # For other cookie-based auth, use the cookie value as is
            elif cookie_name:
                headers['Cookie'] = f'{cookie_name}={cookie_value}'
            else:
                headers['Cookie'] = cookie_value
                
            self.logger.debug(f"Generated cookie header: {headers}")
        return headers
    
    def _get_strategy(self, auth_details: dict[str, Any]) -> AuthStrategy:
        """Get appropriate auth strategy based on auth details."""
        auth_type = auth_details.get('type', '')
        if auth_type == 'cookie':
            return CookieAuthStrategy(auth_details)
        elif auth_type == 'query':
            return QueryAuthStrategy(auth_details)
        elif auth_type == 'token_appauth':
            return TokenAppAuthStrategy(auth_details)
        return BasicAuthStrategy(auth_details)
    
    def get_auth_header(self) -> dict[str, str]:
        """Get authentication header."""
        if not self.strategy:
            self.logger.error("No authentication strategy initialized")
            return {}
        return self.strategy.get_auth_header()
    
    def get_auth_cookie(self) -> dict[str, str]:
        """Get authentication cookie."""
        if not self.strategy:
            self.logger.error("No authentication strategy initialized")
            return {}
        return self.strategy.get_auth_cookie()
    
    def get_auth_token(self) -> str:
        """Get authentication token."""
        if not self.strategy:
            self.logger.error("No authentication strategy initialized")
            return ""
        return self.strategy.get_auth_token()
    
    def build_full_url(
        self,
        auth_type: str,
        club_details: dict[str, Any],
        membership: Membership
    ) -> str:
        """Build full URL with authentication."""
        # Get base URL from club details
        base_url = club_details.get('url', '')
        if not base_url:
            base_url = club_details.get('shopURL', '')  # Fallback for WiseGolf0
            if not base_url:
                raise ValueError("No URL found in club details")
        
        # For WiseGolf0, use shopURL
        if club_details.get('type') == 'wisegolf0':
            base_url = str(club_details.get('shopURL', base_url))
        
        # Ensure strategy is initialized with membership auth details
        self._ensure_strategy(membership.auth_details)
        
        # Build the URL using the strategy
        if self.strategy:
            result = self.strategy.build_full_url(base_url, '')
            return str(result)
        return str(base_url)
    
    def create_headers(
        self,
        auth_type: str,
        cookie_name: str,
        auth_details: dict[str, str]
    ) -> dict[str, str]:
        """Create headers for API request."""
        # Ensure strategy is initialized with current auth details
        self._ensure_strategy(auth_details)
        
        headers = {}
        
        # Get auth header
        if self.strategy:
            auth_header = self.strategy.get_auth_header()
            headers.update(auth_header)
            
            # Get cookie header if cookie name is provided
            if cookie_name:
                # For WiseGolf0, we need to prefix with wisenetwork_session=
                if auth_type == 'wisegolf0':
                    cookie_value = auth_details.get('cookie_value', '')
                    if cookie_value:
                        headers['Cookie'] = f'wisenetwork_session={cookie_value}'
                else:
                    cookie_header = self.strategy.get_auth_cookie()
                    headers.update(cookie_header)
        
        # Add common headers
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        })
        
        return headers
    

    

