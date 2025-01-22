"""
WiseGolf API client for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Union
from urllib.parse import urljoin
import time
import requests

from golfcal2.api.base_api import BaseAPI, APIError, APIResponseError
from golfcal2.services.auth_service import AuthService
from golfcal2.models.mixins import RequestHandlerMixin

class WiseGolfAPIError(APIError):
    """WiseGolf API error."""
    pass

class WiseGolfAuthError(WiseGolfAPIError):
    """Authentication error for WiseGolf API."""
    pass

class WiseGolfResponseError(WiseGolfAPIError):
    """Response error for WiseGolf API."""
    pass

class WiseGolfAPI(BaseAPI, RequestHandlerMixin):
    """WiseGolf API client implementation.
    
    This class handles communication with the WiseGolf API, including:
    - User authentication
    - Fetching reservations
    - Getting player details
    """
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Union[Dict[str, Any], Any]):
        """Initialize WiseGolf API client.
        
        Args:
            base_url: Base URL for the API
            auth_service: Authentication service instance
            club_details: Club configuration details
            membership: User's membership details (can be a dict or an object)
            
        Raises:
            WiseGolfAuthError: If authentication fails
        """
        try:
            # Initialize base API first
            super().__init__(base_url, auth_service, club_details, membership)
            
            # Debug logging
            self.logger.debug("WiseGolfAPI initialization:")
            self.logger.debug(f"Base URL: {base_url}")
            self.logger.debug(f"Club details: {club_details}")
            
            # Update session headers
            self.session.headers.update({
                "x-session-type": "wisegolf",
                "Accept": "application/json, text/plain, */*"
            })
            
            # Debug logging after header update
            self.logger.debug("WiseGolfAPI final headers:")
            self.logger.debug(f"Final headers: {dict(self.session.headers)}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WiseGolf API: {str(e)}")
            raise WiseGolfAuthError(f"Failed to initialize WiseGolf API: {str(e)}")
    
    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get user's reservations.
        
        Returns:
            List of reservation dictionaries
            
        Raises:
            WiseGolfResponseError: If API request fails
            WiseGolfAuthError: If authentication is invalid
        """
        params = {
            "reservations": "getusergolfreservations"
        }
        
        try:
            response = self._make_request("GET", "", params=params)
            return self._extract_data_from_response(response)
            
        except APIResponseError as e:
            if "401" in str(e) or "403" in str(e):
                raise WiseGolfAuthError("Invalid or expired authentication")
            raise WiseGolfResponseError(f"Failed to fetch reservations: {str(e)}")
        except Exception as e:
            raise WiseGolfResponseError(f"Unexpected error fetching reservations: {str(e)}")

    def get_players(self, product_id: str, date: str) -> Dict[str, Any]:
        """Get players for a specific reservation.
        
        Args:
            product_id: Product ID for the reservation
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary containing player information
            
        Raises:
            WiseGolfResponseError: If API request fails
            WiseGolfAuthError: If authentication is invalid
        """
        try:
            endpoint = f"/reservations/?productid={product_id}&date={date}&golf=1"
            return self._make_request("GET", endpoint)
        except APIResponseError as e:
            if "401" in str(e) or "403" in str(e):
                raise WiseGolfAuthError("Invalid or expired authentication")
            raise WiseGolfResponseError(f"Failed to fetch players: {str(e)}")
        except Exception as e:
            raise WiseGolfResponseError(f"Unexpected error fetching players: {str(e)}")

class WiseGolf0API(BaseAPI, RequestHandlerMixin):
    """WiseGolf0 API client implementation.
    
    This class handles communication with the WiseGolf0 API, including:
    - User authentication
    - Fetching reservations
    - Getting player details
    """
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Union[Dict[str, Any], Any]):
        """Initialize WiseGolf0 API client.
        
        Args:
            base_url: Base URL for the API
            auth_service: Authentication service instance
            club_details: Club configuration details
            membership: User's membership details (can be a dict or an object)
            
        Raises:
            WiseGolfAuthError: If authentication fails
        """
        try:
            # Initialize base API first
            super().__init__(base_url, auth_service, club_details, membership)
            
            # Debug logging
            self.logger.debug("WiseGolf0API initialization:")
            self.logger.debug(f"Base URL: {base_url}")
            self.logger.debug(f"Club details: {club_details}")
            
            # Update session headers
            self.session.headers.update({
                "x-session-type": "wisegolf0",
                "Accept": "application/json, text/plain, */*"
            })
            
            # Debug logging after header update
            self.logger.debug("WiseGolf0API final headers:")
            self.logger.debug(f"Final headers: {dict(self.session.headers)}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WiseGolf0 API: {str(e)}")
            raise WiseGolfAuthError(f"Failed to initialize WiseGolf0 API: {str(e)}")
    
    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get user's reservations."""
        try:
            # Build request URL with correct parameter names
            params = {
                "controller": "ajax",
                "reservations": "getusergolfreservations"
            }
            
            # Add cookie value to headers
            if 'cookie_value' in self.auth_details:
                self.session.headers.update({
                    'Cookie': f"wisenetwork_session={self.auth_details['cookie_value']}"
                })
            
            # Make the request to the shop URL path
            endpoint = "/pd/simulaattorit/18/simulaattorit/"
            response = self._make_request("GET", endpoint, params=params)
            return self._extract_data_from_response(response)
            
        except APIResponseError as e:
            raise WiseGolfResponseError(f"Request failed: {str(e)}")
        except Exception as e:
            raise WiseGolfResponseError(f"Unexpected error: {str(e)}")
    
    def get_players(self, product_id: str, date: str, order_id: str = None) -> Dict[str, Any]:
        """
        Get players for a specific reservation.
        
        Args:
            product_id: Product ID
            date: Date in YYYY-MM-DD format
            order_id: Optional order ID to filter players
            
        Returns:
            Dictionary containing player information
        """
        try:
            # Update headers for cross-origin request
            self.session.headers.update({
                "Origin": self.base_url,
                "Referer": self.base_url + "/",
                "Sec-Fetch-Site": "same-site"
            })
            
            params = {
                "productid": product_id,
                "date": date,
                "golf": 1
            }
            if order_id:
                params["orderid"] = order_id
            
            # Use the REST URL for player details
            if not self.rest_url:
                return {"reservationsGolfPlayers": []}
            
            # Make request to REST API
            response = requests.get(
                self.rest_url + "/reservations/",
                params=params,
                headers=self.session.headers,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            # Extract relevant data from response
            if response.ok and isinstance(response.json(), dict):
                return response.json()
            
            return {"reservationsGolfPlayers": []}
            
        except APIResponseError as e:
            raise WiseGolfResponseError(f"Request failed: {str(e)}")
        except Exception as e:
            raise WiseGolfResponseError(f"Unexpected error: {str(e)}")
    
    def get_player_details(self, reservation_id: str) -> List[Dict[str, Any]]:
        """Get player details for reservation."""
        self.logger.debug("WiseGolf0API: Starting get_player_details")
        
        # Log request details
        self.logger.debug("Making WiseGolf0 player details request:")
        self.logger.debug(f"URL: {self.rest_url}")
        self.logger.debug(f"Headers: {dict(self.session.headers)}")
        
        if not self.rest_url:
            return []
        
        endpoint = f"/reservations/{reservation_id}/players"
        self.logger.debug(f"WiseGolf0API: Making request to {self.rest_url}{endpoint}")
        
        # Make request to REST API
        response = requests.get(
            self.rest_url + endpoint,
            headers=self.session.headers,
            timeout=self.DEFAULT_TIMEOUT
        )
        
        self.logger.debug(f"WiseGolf0API: Got response: {response.text}")
        if response.ok:
            return response.json()
        return []