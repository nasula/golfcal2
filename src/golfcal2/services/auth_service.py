"""
Authentication service for golf calendar application.
"""

from typing import Dict, Any, Optional
import logging
from golfcal2.models.user import Membership

class AuthStrategy:
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        raise NotImplementedError

    def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> str:
        raise NotImplementedError

class TokenAppAuthStrategy(AuthStrategy):
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        if 'token' not in auth_details:
            raise ValueError("Missing 'token' in auth_details for token_appauth authentication")
        return {
            'Authorization': auth_details['token'],
            'x-session-type': 'wisegolf',
            'Accept': 'application/json, text/plain, */*'
        }

    def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> str:
        if 'appauth' not in membership.auth_details:
            raise ValueError("Missing 'appauth' in auth_details for token_appauth authentication")
        url = club_details['url']
        return f"{url}&appauth={membership.auth_details['appauth']}"

class CookieAuthStrategy(AuthStrategy):
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        if 'NGLOCALE=fi; JSESSIONID' in cookie_name:
            # NexGolf format with both cookies
            return {'Cookie': f"NGLOCALE=fi; JSESSIONID={auth_details['cookie_value']}"}
        elif 'wisenetwork_session' in cookie_name:
            # WiseGolf format
            return {'Cookie': f"wisenetwork_session={auth_details['cookie_value']}"}
        else:
            # Default format
            return {'Cookie': f"{cookie_name}={auth_details['cookie_value']}"}

    def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> str:
        # For WiseGolf0, use shopURL
        if club_details.get('type') == 'wisegolf0':
            url = club_details.get('shopURL')
            if not url:
                raise ValueError("No shopURL specified for wisegolf0 club")
            return url
        
        # For other types, use standard url
        url = club_details.get('url')
        if not url:
            raise ValueError(f"No url specified for club type {club_details.get('type')}")
        return url

class QueryAuthStrategy(AuthStrategy):
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        }
        
        # Add If-None-Match header if cookie is present
        if 'cookie' in auth_details:
            headers['If-None-Match'] = f'"{auth_details["cookie"]}"'
        
        return headers

    def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> str:
        url = club_details['url']
        # Token is sent as a query parameter
        if 'token' in membership.auth_details:
            url = f"{url}?token={membership.auth_details['token']}"
        return url

class UnsupportedAuthStrategy(AuthStrategy):
    def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
        print("Unsupported authentication type for headers")
        return {}

    def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> Optional[str]:
        print(f"Unsupported authentication type for URL: {club_details['auth_type']}")
        return None

class AuthService:
    """Service for handling authentication."""
    
    def __init__(self):
        """Initialize authentication service."""
        self._strategies = {
            'token_appauth': TokenAppAuthStrategy(),
            'cookie': CookieAuthStrategy(),
            'query': QueryAuthStrategy()
        }
    
    def get_strategy(self, auth_type: str) -> AuthStrategy:
        """Get authentication strategy for given type."""
        return self._strategies.get(auth_type, UnsupportedAuthStrategy())
    
    def create_headers(
        self,
        auth_type: str,
        cookie_name: str,
        auth_details: Dict[str, str]
    ) -> Dict[str, str]:
        """Create headers for API request."""
        strategy = self.get_strategy(auth_type)
        return strategy.create_headers(cookie_name, auth_details)
    
    def build_full_url(
        self,
        auth_type: str,
        club_details: Dict[str, Any],
        membership: Membership
    ) -> Optional[str]:
        """Build full URL with authentication parameters."""
        strategy = self.get_strategy(auth_type)
        return strategy.build_full_url(club_details, membership)
    

    

