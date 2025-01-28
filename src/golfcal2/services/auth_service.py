"""
Authentication service for golf calendar application.
"""

from typing import Dict, Any, Optional, Protocol, Union
from abc import ABC, abstractmethod
from urllib.parse import urljoin
from golfcal2.models.user import Membership
from golfcal2.config.settings import AppConfig

class AuthStrategy(Protocol):
    """Protocol for authentication strategies."""
    
    @abstractmethod
    def get_auth_header(self) -> Dict[str, str]:
        """Get authentication header."""
        ...

    @abstractmethod
    def get_auth_cookie(self) -> Dict[str, str]:
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

    def __init__(self, auth_details: Dict[str, Any]) -> None:
        """Initialize basic auth strategy."""
        self.auth_details = auth_details

    def get_auth_header(self) -> Dict[str, str]:
        """Get basic auth header."""
        token = self.auth_details.get('token', '')
        return {'Authorization': f'Bearer {token}'} if token else {}

    def get_auth_cookie(self) -> Dict[str, str]:
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

    def __init__(self, auth_details: Dict[str, Any]) -> None:
        """Initialize cookie auth strategy."""
        self.auth_details = auth_details

    def get_auth_header(self) -> Dict[str, str]:
        """Get cookie auth header."""
        return {}

    def get_auth_cookie(self) -> Dict[str, str]:
        """Get cookie auth cookie."""
        cookie = self.auth_details.get('cookie', '')
        return {'Cookie': cookie} if cookie else {}

    def get_auth_token(self) -> str:
        """Get cookie auth token."""
        return str(self.auth_details.get('cookie', ''))

    def build_full_url(self, base_url: str, path: str) -> str:
        """Build full URL with cookie auth."""
        return urljoin(base_url, path)

class QueryAuthStrategy(AuthStrategy):
    """Query parameter-based authentication strategy."""

    def __init__(self, auth_details: Dict[str, Any]) -> None:
        """Initialize query auth strategy."""
        self.auth_details = auth_details

    def get_auth_header(self) -> Dict[str, str]:
        """Get query auth header."""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        }
        
        # Add If-None-Match header if cookie is present
        if 'cookie' in self.auth_details:
            headers['If-None-Match'] = f'"{self.auth_details["cookie"]}"'
        
        return headers

    def get_auth_cookie(self) -> Dict[str, str]:
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

class UnsupportedAuthStrategy(AuthStrategy):
    """Fallback strategy for unsupported authentication types."""

    def get_auth_header(self) -> Dict[str, str]:
        """Get unsupported auth header."""
        return {}

    def get_auth_cookie(self) -> Dict[str, str]:
        """Get unsupported auth cookie."""
        return {}

    def get_auth_token(self) -> str:
        """Get unsupported auth token."""
        return ""

    def build_full_url(self, base_url: str, path: str) -> str:
        """Build full URL with unsupported auth."""
        return urljoin(base_url, path)

class AuthService:
    """Service for handling authentication."""
    
    def __init__(self, auth_details: Union[Dict[str, Any], object]) -> None:
        """Initialize auth service.
        
        Args:
            auth_details: Authentication details dictionary or object
        """
        if isinstance(auth_details, dict):
            self.auth_details = auth_details
        else:
            self.auth_details = getattr(auth_details, 'auth_details', {})
        self.strategy: AuthStrategy = self._get_strategy(self.auth_details)
    
    def _get_strategy(self, auth_details: Dict[str, Any]) -> AuthStrategy:
        """Get appropriate auth strategy based on auth details."""
        auth_type = auth_details.get('type', '')
        if auth_type == 'cookie':
            return CookieAuthStrategy(auth_details)
        elif auth_type == 'query':
            return QueryAuthStrategy(auth_details)
        return BasicAuthStrategy(auth_details)
    
    def get_auth_header(self) -> Dict[str, str]:
        """Get authentication header."""
        return self.strategy.get_auth_header()
    
    def get_auth_cookie(self) -> Dict[str, str]:
        """Get authentication cookie."""
        return self.strategy.get_auth_cookie()
    
    def get_auth_token(self) -> str:
        """Get authentication token."""
        return self.strategy.get_auth_token()
    
    def build_full_url(
        self,
        auth_type: str,
        club_details: Dict[str, Any],
        membership: Membership
    ) -> str:
        """Build full URL with authentication.
        
        Args:
            auth_type: Type of authentication
            club_details: Club details dictionary
            membership: Membership object
            
        Returns:
            Full URL with authentication parameters
        """
        # Get base URL from club details
        base_url = club_details.get('url', '')
        if not base_url:
            base_url = club_details.get('shopURL', '')  # Fallback for WiseGolf0
            if not base_url:
                raise ValueError("No URL found in club details")
        
        # For WiseGolf0, use shopURL
        if club_details.get('type') == 'wisegolf0':
            base_url = club_details.get('shopURL', base_url)
        
        # Build the URL using the strategy
        return self.strategy.build_full_url(base_url, '')
    
    def create_headers(
        self,
        auth_type: str,
        cookie_name: str,
        auth_details: Dict[str, str]
    ) -> Dict[str, str]:
        """Create headers for API request.
        
        Args:
            auth_type: Type of authentication
            cookie_name: Name of cookie for cookie-based auth
            auth_details: Authentication details
            
        Returns:
            Dictionary of headers
        """
        headers = {}
        
        # Get auth header
        auth_header = self.get_auth_header()
        headers.update(auth_header)
        
        # Get cookie header if cookie name is provided
        if cookie_name:
            cookie_header = self.get_auth_cookie()
            headers.update(cookie_header)
            
        # Add common headers
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        })
        
        return headers
    

    

