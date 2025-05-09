"""
TeeTime API client for golf calendar application.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urljoin

import requests

from golfcal2.models.mixins import (
    APIAuthError,
    APIError,
    APIResponseError,
    APITimeoutError,
    RequestHandlerMixin,
)
from golfcal2.services.auth_service import AuthService
from golfcal2.utils.logging_utils import LoggerMixin

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from golfcal2.models.golf_club import GolfClub

class TeeTimeAPIError(Exception):
    """TeeTime API error."""
    pass

class TeeTimeAPI(LoggerMixin, RequestHandlerMixin):
    """TeeTime API client implementation."""
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: dict[str, Any], membership: dict[str, Any] | Any, club: Optional['GolfClub'] = None):
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
        
    def _setup_session(self) -> None:
        """Set up session headers."""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-GB,en;q=0.9',
            'Connection': 'keep-alive',
            'Priority': 'u=3, i',
            'Referer': 'https://www.teetime.fi/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15'
        }
        self.session.headers.update(headers)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> dict[str, Any]:
        """Make an API request with proper error handling."""
        try:
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
        """Get reservations from TeeTime API."""
        try:
            # Get token from auth details
            token = self.auth_details.get('token')
            if not token:
                self.logger.error("No token found in auth details")
                return []

            # Calculate date range (from today to end of year)
            from_date = datetime.now().strftime('%Y-%m-%d')
            to_date = (datetime.now().replace(month=12, day=31)).strftime('%Y-%m-%d')

            # Add required query parameters
            params = {
                'from': from_date,
                'to': to_date,
                'token': token
            }

            # Make the request to the correct endpoint with parameters
            response = self._make_request("GET", "/backend/player/flight", params=params)
            
            # Response should be a list of tee times wrapped in a dict with 'data' key
            tee_times = response.get('data', [])
            if not isinstance(tee_times, list):
                self.logger.error(f"Invalid response format: expected list in 'data', got {type(tee_times)}")
                return []
            
            # Convert tee times to reservations format
            reservations = []
            for tee_time in tee_times:
                # Skip if no reservations
                if not tee_time.get('reservations'):
                    continue
                    
                # Get course information
                course_info = tee_time.get('course', {})
                club_info = course_info.get('club', {})
                
                # Create a reservation entry
                reservation = {
                    'startTime': tee_time.get('startTime'),
                    'status': tee_time.get('status'),
                    'id': tee_time.get('id'),
                    'course': {
                        'name': course_info.get('name'),
                        'id': course_info.get('id'),
                        'club': {
                            'name': club_info.get('name'),
                            'abbreviation': club_info.get('abbrevitation'),  # Note: API uses 'abbrevitation'
                            'number': club_info.get('number')
                        }
                    },
                    'players': []
                }
                
                # Add player information
                for res in tee_time.get('reservations', []):
                    player_data = res.get('player', {})
                    if player_data:
                        player = {
                            'id': res.get('id'),
                            'handicap': player_data.get('handicap', 0.0),
                            'gender': player_data.get('gender'),
                            'holes': player_data.get('holes', 18),
                            'idHash': player_data.get('idHash')
                        }
                        reservation['players'].append(player)
                
                # Add settings if available
                if 'settings' in tee_time:
                    reservation['settings'] = tee_time['settings']
                
                reservations.append(reservation)
            
            # Filter out non-confirmed reservations if needed
            return [r for r in reservations if r.get('status') != 'CANCELLED']
            
        except APITimeoutError as e:
            raise TeeTimeAPIError(f"Request timed out: {e!s}")
        except APIResponseError as e:
            raise TeeTimeAPIError(f"Request failed: {e!s}")
        except APIAuthError as e:
            raise TeeTimeAPIError(f"Authentication failed: {e!s}")
        except Exception as e:
            raise TeeTimeAPIError(f"Unexpected error: {e!s}")

    def get_club_info(self, club_number: str) -> dict[str, Any] | None:
        """Get club information from TeeTime API."""
        try:
            # Get token from auth details
            token = self.auth_details.get('token')
            if not token:
                self.logger.error("No token found in auth details")
                return None

            # Build request URL with token
            endpoint = f"/backend/clubs/{club_number}"
            params = {'token': token}
            
            # Make request
            response = self._make_request("GET", endpoint, params=params)
            return response
            
        except APITimeoutError as e:
            raise TeeTimeAPIError(f"Request timed out: {e!s}")
        except APIResponseError as e:
            raise TeeTimeAPIError(f"Request failed: {e!s}")
        except APIAuthError as e:
            raise TeeTimeAPIError(f"Authentication failed: {e!s}")
        except Exception as e:
            raise TeeTimeAPIError(f"Unexpected error: {e!s}") 