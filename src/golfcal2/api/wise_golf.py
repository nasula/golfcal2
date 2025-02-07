"""
WiseGolf API client for golf calendar application.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from urllib.parse import urljoin
import time
import requests
from abc import ABC, abstractmethod

from golfcal2.api.base_api import BaseAPI
from golfcal2.models.mixins import (
    RequestHandlerMixin,
    APIError,
    APIResponseError,
    APITimeoutError,
    APIAuthError
)
from golfcal2.services.auth_service import AuthService
from golfcal2.utils.api_handler import APIResponseValidator

__all__ = ['WiseGolfAPI', 'WiseGolf0API']

class WiseGolfAPIError(APIError):
    """WiseGolf API error."""
    pass

class WiseGolfAuthError(WiseGolfAPIError):
    """Authentication error for WiseGolf API."""
    pass

class WiseGolfResponseError(WiseGolfAPIError):
    """Response error for WiseGolf API."""
    pass

class BaseWiseGolfAPI(BaseAPI, RequestHandlerMixin):
    """Base class for WiseGolf API implementations."""
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Union[Dict[str, Any], Any], club: Optional['GolfClub'] = None):
        """Initialize base WiseGolf API client."""
        self.auth_service = auth_service  # Set auth_service before super().__init__
        self.club = club
        super().__init__(base_url, auth_service, club_details, membership)
        self._setup_auth_headers()
        
    def _setup_auth_headers(self):
        """Setup authentication headers based on auth type."""
        try:
            # Add common headers first
            self.session.headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json'
            })
            
            if not self.club:
                self.logger.warning("No club instance available for auth headers")
                return
                
            if not self.auth_service:
                self.logger.warning("No auth service available")
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
        
    def get_players(self, reservation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get players for a specific reservation.
        
        Args:
            reservation_data: Dictionary containing reservation details
                
        Returns:
            Dictionary containing player information
        """
        try:
            self.logger.debug("WiseGolf0API.get_players - Starting with reservation data:")
            self.logger.debug(f"WiseGolf0API.get_players - {reservation_data}")
            
            # Extract date from dateTimeStart
            date = datetime.strptime(
                reservation_data["dateTimeStart"],
                "%Y-%m-%d %H:%M:%S"
            ).strftime("%Y-%m-%d")
                
            # Get product ID from reservation
            product_id = reservation_data.get("productId")
            if not product_id and 'resources' in reservation_data:
                resources = reservation_data.get('resources', [{}])
                if resources:
                    product_id = resources[0].get('resourceId')
                    
            if not product_id:
                raise WiseGolfResponseError("No productId found in reservation")
                
            params = {
                "productid": str(product_id),
                "date": date,
                "golf": 1,
                "orderid": str(reservation_data.get('orderId'))
            }
            
            self.logger.debug(f"WiseGolf0API.get_players - Calling _fetch_players with params: {params}")
            response = self._fetch_players(params)
            self.logger.debug(f"WiseGolf0API.get_players - Got response: {response}")
            
            # Return the response directly - it should contain reservationsGolfPlayers
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to fetch players: {e}", exc_info=True)
            return {"reservationsGolfPlayers": []}
            
    @abstractmethod
    def _fetch_players(self, params: Dict[str, str]) -> Dict[str, Any]:
        """
        Fetch players from API with given parameters.
        Must be implemented by subclasses.
        """
        raise NotImplementedError

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an API request with proper error handling."""
        try:
            # Ensure we have auth headers
            if not self.session.headers.get('Authorization') and not self.session.headers.get('Cookie'):
                self._setup_auth_headers()
                
            return super()._make_request(method, endpoint, **kwargs)
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            raise

class WiseGolfAPI(BaseWiseGolfAPI):
    """WiseGolf API client implementation."""
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Union[Dict[str, Any], Any], club: Optional['GolfClub'] = None):
        """Initialize WiseGolf API client."""
        super().__init__(base_url, auth_service, club_details, membership, club)
        self.logger.debug(f"WiseGolfAPI initialized with headers: {dict(self.session.headers)}")

    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get user's reservations."""
        try:
            params = {
                "controller": "ajax",
                "reservations": "getusergolfreservations"
            }
            
            # Get raw response from request
            raw_response = self._make_request("GET", "", params=params)
            self.logger.debug(f"WiseGolfAPI response data: {raw_response}")
            
            # Validate the response data structure
            if not isinstance(raw_response, dict):
                raise WiseGolfResponseError("Invalid response format")
            
            if 'success' not in raw_response:
                raise WiseGolfResponseError("Missing 'success' field in response")
            
            if not raw_response['success']:
                raise WiseGolfResponseError("Request was not successful")
            
            if 'rows' not in raw_response:
                raise WiseGolfResponseError("Missing 'rows' field in response")
            
            rows = raw_response['rows']
            if not isinstance(rows, list):
                return []
            
            self.logger.debug(f"Found {len(rows)} reservations")
            return rows
            
        except APIResponseError as e:
            if "401" in str(e) or "403" in str(e):
                raise WiseGolfAuthError("Invalid or expired authentication")
            raise WiseGolfResponseError(f"Failed to fetch reservations: {str(e)}")
        except Exception as e:
            raise WiseGolfResponseError(f"Unexpected error fetching reservations: {str(e)}")
            
    def _fetch_players(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Fetch players from WiseGolf API."""
        rest_url = self.club_details.get('restUrl')
        if not rest_url:
            return {"reservationsGolfPlayers": []}
            
        response = self._make_request("GET", "/reservations/", params=params)
        return response if isinstance(response, dict) else {"reservationsGolfPlayers": []}


class WiseGolf0API(BaseWiseGolfAPI):
    """WiseGolf0 API client implementation."""
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Union[Dict[str, Any], Any], club: Optional['GolfClub'] = None):
        """Initialize WiseGolf0 API client."""
        # Ensure auth_details has the correct type and cookie_name
        if isinstance(membership, dict):
            auth_details = membership.get('auth_details', {})
            auth_details['type'] = 'wisegolf0'
            auth_details['cookie_name'] = club_details.get('cookie_name', 'wisenetwork_session')
            membership['auth_details'] = auth_details
        else:
            auth_details = getattr(membership, 'auth_details', {})
            auth_details['type'] = 'wisegolf0'
            auth_details['cookie_name'] = club_details.get('cookie_name', 'wisenetwork_session')
            setattr(membership, 'auth_details', auth_details)
            
        super().__init__(base_url, auth_service, club_details, membership, club)
        
        # Set REST URL from club details and ensure it doesn't end with slash
        self.rest_url = club_details.get('restUrl', '').rstrip('/')
        if not self.rest_url:
            self.logger.warning("No restUrl found in club_details")
            
        self.logger.debug("WiseGolf0API final headers:")
        self.logger.debug(f"Final headers: {dict(self.session.headers)}")
    
    def _setup_auth_headers(self):
        """Setup authentication headers specific to WiseGolf0."""
        try:
            if not self.club or not self.auth_service:
                self.logger.warning("Missing club or auth_service for auth headers")
                return
                
            # Get auth headers using get_auth_headers
            auth_headers = self.auth_service.get_auth_headers(self.club, self.auth_details)
            
            # Add common headers
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': self.base_url,
                'Referer': self.base_url + "/",
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }
            
            # Combine headers, letting auth headers take precedence
            headers.update(auth_headers)
            
            # Update session headers
            self.session.headers.update(headers)
            self.logger.debug(f"Set up auth headers: {dict(self.session.headers)}")
                
        except Exception as e:
            self.logger.error(f"Failed to set up auth headers: {e}")
    
    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get user's reservations."""
        try:
            params = {
                "controller": "ajax",
                "reservations": "getusergolfreservations"
            }
            
            endpoint = "/pd/simulaattorit/18/simulaattorit/"
            raw_response = self._make_request("GET", endpoint, params=params)
            
            # Validate the response data structure
            if not isinstance(raw_response, dict):
                raise WiseGolfResponseError("Invalid response format")
            
            if 'success' not in raw_response:
                raise WiseGolfResponseError("Missing 'success' field in response")
            
            if not raw_response['success']:
                raise WiseGolfResponseError("Request was not successful")
            
            if 'rows' not in raw_response:
                raise WiseGolfResponseError("Missing 'rows' field in response")
            
            rows = raw_response['rows']
            if not isinstance(rows, list):
                return []
            
            self.logger.debug(f"Found {len(rows)} reservations")
            return rows
            
        except APIResponseError as e:
            raise WiseGolfResponseError(f"Request failed: {str(e)}")
        except Exception as e:
            raise WiseGolfResponseError(f"Unexpected error: {str(e)}")
    
    def _fetch_players(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Fetch players from WiseGolf0 API."""
        if not self.rest_url:
            self.logger.warning("No restUrl available for fetching players")
            return {"reservationsGolfPlayers": []}
        
        try:
            # Use the existing session instead of creating a new one
            # Construct the full URL for the REST API call
            endpoint = "/api/1.0/reservations/"
            full_url = urljoin(self.rest_url, endpoint)
            
            self.logger.debug(f"Fetching players from {full_url} with params: {params}")
            self.logger.debug(f"Using headers: {dict(self.session.headers)}")
            
            # Make the request using the existing session
            response = self.session.get(
                full_url,
                params=params,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            # Validate response status code
            if response.status_code != 200:
                self.logger.error(f"Player fetch failed with status {response.status_code}: {response.text}")
                raise WiseGolfResponseError(f"Request failed with status {response.status_code}")
            
            # Parse JSON response
            try:
                data = response.json()
                self.logger.debug(f"Got player data response: {data}")
            except ValueError as e:
                self.logger.error(f"Invalid JSON in player response: {response.text}")
                raise WiseGolfResponseError(f"Invalid JSON response: {str(e)}")
            
            # Validate response structure
            if not isinstance(data, dict):
                raise WiseGolfResponseError("Invalid response format")
            
            if 'reservationsGolfPlayers' not in data:
                self.logger.warning("No reservationsGolfPlayers in response")
                return {"reservationsGolfPlayers": []}
            
            return data
            
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            return {"reservationsGolfPlayers": []}
        except Exception as e:
            self.logger.error(f"Unexpected error in _fetch_players: {str(e)}", exc_info=True)
            return {"reservationsGolfPlayers": []}

    def _extract_data_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract reservation data from API response.
        
        Args:
            response: API response dictionary
            
        Returns:
            List of reservation dictionaries
            
        Raises:
            WiseGolfResponseError: If response format is invalid
        """
        try:
            if not isinstance(response, dict) or 'success' not in response:
                raise WiseGolfResponseError("Invalid response format")
                
            if not response['success']:
                raise WiseGolfResponseError("Request was not successful")
                
            if 'rows' not in response:
                return []
                
            rows = response['rows']
            if not isinstance(rows, list):
                return []
                
            self.logger.debug(f"Found {len(rows)} items in 'rows'")
            
            # Extract relevant fields for each reservation
            reservations = []
            for row in rows:
                reservation = {
                    'dateTimeStart': row.get('dateTimeStart'),
                    'dateTimeEnd': row.get('dateTimeEnd'),
                    'firstName': row.get('firstName'),
                    'familyName': row.get('familyName'),
                    'clubAbbreviation': row.get('clubAbbreviation'),
                    'handicapActive': row.get('handicapActive'),
                    'productName': row.get('productName'),
                    'variantName': row.get('variantName'),
                    'status': row.get('status'),
                    'inFuture': row.get('inFuture'),
                    'orderId': row.get('orderId'),
                    'reservationId': row.get('reservationId'),
                    'reservationTimeId': row.get('reservationTimeId'),
                    'productId': row.get('productId')
                }
                reservations.append(reservation)
                
            return reservations
            
        except Exception as e:
            raise WiseGolfResponseError(f"Failed to extract data from response: {str(e)}")