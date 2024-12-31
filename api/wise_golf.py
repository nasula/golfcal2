"""
WiseGolf API client for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from urllib.parse import urljoin
import time

from golfcal2.api.base_api import BaseAPI, APIError, APIResponseError
from golfcal2.services.auth_service import AuthService

class WiseGolfAPIError(APIError):
    """WiseGolf API error."""
    pass

class WiseGolfAuthError(WiseGolfAPIError):
    """Authentication error for WiseGolf API."""
    pass

class WiseGolfResponseError(WiseGolfAPIError):
    """Response error for WiseGolf API."""
    pass

class WiseGolfAPI(BaseAPI):
    """WiseGolf API client implementation.
    
    This class handles communication with the WiseGolf API, including:
    - User authentication
    - Fetching reservations
    - Getting player details
    """
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Dict[str, Any]):
        """Initialize WiseGolf API client.
        
        Args:
            base_url: Base URL for the API
            auth_service: Authentication service instance
            club_details: Club configuration details
            membership: User's membership details
            
        Raises:
            WiseGolfAuthError: If authentication fails
        """
        try:
            super().__init__(base_url, auth_service, club_details, membership)
            self.session.headers.update({
                "x-session-type": "wisegolf",
                "Accept": "application/json, text/plain, */*"
            })
        except Exception as e:
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
            
            if isinstance(response, dict):
                if "rows" in response:
                    return response["rows"]
                elif "reservations" in response:
                    return response["reservations"]
                else:
                    self.logger.warning(f"Unexpected response format. Keys: {list(response.keys())}")
            elif isinstance(response, list):
                return response
            
            return []
            
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

class WiseGolf0API(BaseAPI):
    """WiseGolf0 API client."""
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Dict[str, Any]):
        """Initialize WiseGolf0 API client."""
        init_start_time = time.time()
        super().__init__(base_url, auth_service, club_details, membership)
        
        # Extract auth details from membership
        self.auth_details = getattr(membership, 'auth_details', {})
        
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Priority": "u=3, i",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15"
        })
        
        # Log configuration
        self.logger.debug(f"WiseGolf0API initialized with:")
        self.logger.debug(f"Base URL: {self.base_url}")
        self.logger.debug(f"Headers: {dict(self.session.headers)}")
    
    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get user's reservations."""
        start_time = time.time()
        
        try:
            # Get date range for reservations
            now = datetime.now()
            start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")
            
            # Build request URL with correct parameter names
            params = {
                "controller": "ajax",
                "reservations": "getusergolfreservations"
            }
            
            # Add token to params if present
            if 'token' in self.auth_details:
                params['token'] = self.auth_details['token']
            
            # Log request details
            self.logger.debug("Making WiseGolf0 reservations request:")
            self.logger.debug(f"URL: {self.base_url}")
            self.logger.debug(f"Headers: {dict(self.session.headers)}")
            self.logger.debug(f"Params: {params}")
            
            # Make the request
            endpoint = "/pd/simulaattorit/18/simulaattorit/"
            self.logger.info(f"WiseGolf0API: Making request to {self.base_url}{endpoint} with params: {params}")
            response = self._make_request("GET", endpoint, params=params)
            self.logger.info(f"WiseGolf0API: Got response type: {type(response)}")
            
            if isinstance(response, dict):
                if "rows" in response:
                    self.logger.info(f"WiseGolf0API: Found {len(response['rows'])} rows in response")
                    return response["rows"]
                elif "reservations" in response:
                    self.logger.info(f"WiseGolf0API: Found {len(response['reservations'])} reservations in response")
                    return response["reservations"]
                else:
                    self.logger.warning(f"WiseGolf0API: Response has no rows or reservations. Keys: {list(response.keys())}")
            elif isinstance(response, list):
                self.logger.info(f"WiseGolf0API: Got list response with {len(response)} items")
                return response
            
            self.logger.warning("WiseGolf0API: No reservations found in response")
            return []
            
        except Exception as e:
            end_time = time.time()
            self.logger.error(f"WiseGolf0API: Error fetching reservations after {end_time - start_time:.2f} seconds: {e}", exc_info=True)
            self.logger.error(f"WiseGolf0API: Base URL: {self.base_url}")
            self.logger.error(f"WiseGolf0API: Headers: {dict(self.session.headers)}")
            self.logger.error(f"WiseGolf0API: Auth details: {self.auth_details}")
            raise WiseGolfAPIError(str(e))
    
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
        self.logger.debug("WiseGolf0API: Starting get_players")
        
        # Update headers for cross-origin request
        self.session.headers.update({
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
            "Sec-Fetch-Site": "same-site"
        })
        
        # Log request details
        self.logger.debug("Making WiseGolf0 players request:")
        self.logger.debug(f"URL: {self.base_url}")
        self.logger.debug(f"Headers: {dict(self.session.headers)}")
        
        params = {
            "productid": product_id,
            "date": date,
            "golf": 1
        }
        if order_id:
            params["orderid"] = order_id
        
        self.logger.debug(f"WiseGolf0API: Making request to {self.base_url}/api/1.0/reservations/ with params: {params}")
        self.logger.debug(f"WiseGolf0API: Using cookies: {self.session.cookies}")
        
        response = self._make_request("GET", "/api/1.0/reservations/", params=params)
        self.logger.debug(f"WiseGolf0API: Got response: {response}")
        return response
    
    def get_player_details(self, reservation_id: str) -> List[Dict[str, Any]]:
        """Get player details for reservation."""
        self.logger.debug("WiseGolf0API: Starting get_player_details")
        
        # Log request details
        self.logger.debug("Making WiseGolf0 player details request:")
        self.logger.debug(f"URL: {self.base_url}")
        self.logger.debug(f"Headers: {dict(self.session.headers)}")
        
        endpoint = f"/api/1.0/reservations/{reservation_id}/players"
        self.logger.debug(f"WiseGolf0API: Making request to {self.base_url}{endpoint}")
        response = self._make_request("GET", endpoint)
        self.logger.debug(f"WiseGolf0API: Got response: {response}")
        return response