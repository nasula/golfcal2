"""
TeeTime API client for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING
from urllib.parse import urljoin
import time
import requests

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.models.mixins import RequestHandlerMixin
from golfcal2.models.mixins import APIError, APITimeoutError, APIResponseError, APIAuthError
from golfcal2.services.auth_service import AuthService

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from golfcal2.models.golf_club import GolfClub

class TeeTimeAPIError(Exception):
    """TeeTime API error."""
    pass

class TeeTimeAPI(LoggerMixin, RequestHandlerMixin):
    """TeeTime API client implementation."""
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Union[Dict[str, Any], Any], club: Optional['GolfClub'] = None):
        """Initialize TeeTime API client."""
        super().__init__()
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
        self.auth_service = auth_service
        self.club = club
        
        # Extract auth details from membership
        if isinstance(membership, dict):
            self.auth_details = membership.get('auth_details', {})
        else:
            self.auth_details = getattr(membership, 'auth_details', {})
            
        self.club_details = club_details
        self.session = requests.Session()
        self._setup_session()
        self._setup_auth_headers()
        
    def _setup_session(self):
        """Set up session headers."""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': f"{self.base_url}/",
            'Origin': self.base_url,
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        self.session.headers.update(headers)

    def _setup_auth_headers(self):
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
                self.session.headers.update(auth_headers)
                self.logger.debug(f"Set up auth headers: {dict(self.session.headers)}")
            else:
                self.logger.warning("No auth headers returned from auth service")
                
        except Exception as e:
            self.logger.error(f"Failed to set up auth headers: {e}")
            
    def _verify_credentials(self) -> bool:
        """Verify API credentials."""
        try:
            response = self._make_request("GET", "/api/verify")
            return response.get('status') == 'ok'
        except Exception as e:
            self.logger.error(f"Failed to verify credentials: {e}")
            return False

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an API request with proper error handling."""
        try:
            # Ensure we have auth headers
            if 'X-API-Key' not in self.session.headers:
                self._setup_auth_headers()
                
            url = urljoin(self.base_url, endpoint)
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error: {e}")
            raise APIResponseError(f"HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise APIError(f"Request failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise

    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get reservations from TeeTime API."""
        try:
            # Verify credentials first
            if not self._verify_credentials():
                self.logger.error("Failed to verify API credentials")
                return []
            
            # Get member ID from auth details
            if 'member_id' not in self.auth_details:
                self.logger.error("No member ID found in auth details")
                return []
            
            # Build request URL with correct parameter names
            params = {
                'member_id': self.auth_details['member_id']
            }
            
            # Make the request to the correct endpoint
            response = self._make_request("GET", "/api/bookings", params=params)
            
            # Check if response is valid
            if not isinstance(response, dict) or 'data' not in response:
                self.logger.error(f"Invalid response format: {response}")
                return []
            
            # Filter out non-confirmed reservations if needed
            bookings = response['data']
            return [b for b in bookings if b.get('status', 'confirmed') == 'confirmed']
            
        except APITimeoutError as e:
            raise TeeTimeAPIError(f"Request timed out: {str(e)}")
        except APIResponseError as e:
            raise TeeTimeAPIError(f"Request failed: {str(e)}")
        except APIAuthError as e:
            raise TeeTimeAPIError(f"Authentication failed: {str(e)}")
        except Exception as e:
            raise TeeTimeAPIError(f"Unexpected error: {str(e)}")

    def get_club_info(self, club_number: str) -> Optional[Dict[str, Any]]:
        """Get club information from TeeTime API."""
        try:
            # Build request URL
            endpoint = f"/api/v1/clubs/{club_number}"
            
            # Make request
            response = self._make_request("GET", endpoint)
            
            if isinstance(response, dict):
                return response
            
            return None
            
        except APITimeoutError as e:
            raise TeeTimeAPIError(f"Request timed out: {str(e)}")
        except APIResponseError as e:
            raise TeeTimeAPIError(f"Request failed: {str(e)}")
        except APIAuthError as e:
            raise TeeTimeAPIError(f"Authentication failed: {str(e)}")
        except Exception as e:
            raise TeeTimeAPIError(f"Unexpected error: {str(e)}") 