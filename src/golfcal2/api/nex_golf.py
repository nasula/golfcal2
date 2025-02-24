"""
NexGolf API client for golf calendar application.
"""

import time
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urljoin

import requests

from golfcal2.models.mixins import APIError, APIResponseError, RequestHandlerMixin
from golfcal2.services.auth_service import AuthService
from golfcal2.utils.logging_utils import LoggerMixin

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from golfcal2.models.golf_club import GolfClub

class NexGolfAPI(LoggerMixin, RequestHandlerMixin):
    """NexGolf API client implementation."""
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: dict[str, Any], membership: dict[str, Any] | Any, club: Optional['GolfClub'] = None):
        """Initialize NexGolf API client."""
        super().__init__()
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
        self.auth_service = auth_service
        self.club = club
        
        # Extract auth details from membership
        if isinstance(membership, dict):
            self.auth_details = membership.get('auth_details', {})
            # Ensure auth type and cookie name are set for NexGolf
            self.auth_details['type'] = 'nexgolf'
            self.auth_details['cookie_name'] = 'JSESSIONID'
        else:
            self.auth_details = getattr(membership, 'auth_details', {})
            self.auth_details['type'] = 'nexgolf'
            self.auth_details['cookie_name'] = 'JSESSIONID'
            
        self.club_details = club_details
        self.session = requests.Session()
        self._setup_session()
        self._setup_auth_headers()
    
    def _setup_session(self) -> None:
        """Set up session with authentication."""
        # Set up basic session headers
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-GB,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15',
            'Referer': f"{self.base_url}/pgc/member/index.html",
            'Priority': 'u=3, i',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        # Clear any existing headers and cookies
        self.session.headers.clear()
        self.session.cookies.clear()
        
        # Update session headers
        self.session.headers.update(headers)
        
        # Set default cookies
        domain = self.base_url.split('//')[1].split('/')[0]  # Extract domain without path
        self.session.cookies.set('NGLOCALE', 'fi', domain=domain)
        
        # Log headers for debugging (excluding sensitive values)
        debug_headers = dict(self.session.headers)
        for sensitive_key in ['X-Auth-Token', 'Cookie']:
            if sensitive_key in debug_headers:
                debug_headers[sensitive_key] = '***'
        self.debug("Session headers", headers=debug_headers)
    
    def _setup_auth_headers(self) -> None:
        """Setup authentication headers."""
        try:
            if not self.auth_service:
                self.logger.warning("No auth service available")
                return
                
            if not self.club:
                self.logger.warning("No club instance available for auth headers")
                return
                
            # Get auth headers from auth service
            auth_headers = self.auth_service.get_auth_headers(self.club, self.auth_details)
            
            # Update session headers
            if auth_headers:
                # Handle Cookie header separately
                if 'Cookie' in auth_headers:
                    cookie_str = auth_headers.pop('Cookie')
                    domain = self.base_url.split('//')[1].split('/')[0]  # Extract domain without path
                    for cookie in cookie_str.split('; '):
                        if '=' in cookie:
                            name, value = cookie.split('=', 1)
                            self.session.cookies.set(name, value, domain=domain)
                
                # Update remaining headers
                self.session.headers.update(auth_headers)
                
                # Log actual headers being used (with sensitive data masked)
                debug_headers = dict(self.session.headers)
                debug_cookies = {name: '***' for name in self.session.cookies.keys()}
                for sensitive_key in ['X-Auth-Token', 'Cookie']:
                    if sensitive_key in debug_headers:
                        debug_headers[sensitive_key] = '***'
                self.logger.debug(f"Set up auth headers: {debug_headers}")
                self.logger.debug(f"Set up cookies: {debug_cookies}")
            else:
                self.logger.warning("No auth headers returned from auth service")
                
        except Exception as e:
            self.logger.error(f"Failed to set up auth headers: {e}")
            
    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> dict[str, Any]:
        """Make an API request with proper error handling."""
        try:
            # Log actual request headers and cookies before making the request
            debug_headers = dict(self.session.headers)
            debug_cookies = {name: '***' for name in self.session.cookies.keys()}
            for sensitive_key in ['X-Auth-Token', 'Cookie']:
                if sensitive_key in debug_headers:
                    debug_headers[sensitive_key] = '***'
            self.logger.debug(f"Making request with headers: {debug_headers}")
            self.logger.debug(f"Making request with cookies: {debug_cookies}")
            
            url = urljoin(self.base_url, endpoint)
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            result = response.json()
            
            # Convert list responses to dict format
            if isinstance(result, list):
                return {"data": result}
            elif isinstance(result, dict):
                return result
            else:
                raise APIResponseError(f"Unexpected response type: {type(result)}")
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error: {e}")
            raise APIResponseError(f"HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise APIError(f"Request failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise

    def get_reservations(self) -> list[dict[str, Any]]:
        """Get user's reservations."""
        try:
            # Build the URL based on club configuration
            endpoint = "/pgc/member/api/flight/own"
                
            # Use the same date as the working example
            to_date = "2025-02-05"
                
            params = {
                'noCache': str(int(time.time() * 1000)),
                'to': to_date
            }
            
            # Log headers for debugging
            self.logger.debug(f"Session headers | Context: headers={dict(self.session.headers)}")
            
            # Make request to get reservations using the correct endpoint
            response = self._make_request("GET", endpoint, params=params)
            
            # Handle different response formats
            result: list[dict[str, Any]] = []
            
            if "data" in response and isinstance(response["data"], list):
                # Convert tee times to reservations
                for tee_time in response["data"]:
                    if isinstance(tee_time, dict) and 'reservations' in tee_time and tee_time['reservations']:
                        # Create a single reservation for the tee time
                        reservation = {
                            'startTime': tee_time.get('startTime'),
                            'comment': tee_time.get('comment'),
                            'status': tee_time.get('status'),
                            'players': tee_time['reservations']  # Store all players in the reservation
                        }
                        result.append(reservation)
            elif "reservations" in response and isinstance(response["reservations"], list):
                result = response["reservations"]
            elif "rows" in response and isinstance(response["rows"], list):
                result = response["rows"]
            else:
                self.logger.error(f"Invalid response format: {response}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get reservations: {e}")
            return []