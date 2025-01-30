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
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Union[Dict[str, Any], Any]):
        """Initialize base WiseGolf API client."""
        super().__init__(base_url, auth_service, club_details, membership)
        self._setup_auth_headers()
        
    def _setup_auth_headers(self):
        """Setup authentication headers based on auth type."""
        if 'token' in self.auth_details:
            self._setup_token_auth()
        elif 'cookie_value' in self.auth_details:
            self._setup_cookie_auth()
            
    def _setup_token_auth(self):
        """Setup token-based authentication."""
        self.session.headers.update({
            'Authorization': self.auth_details['token'],
            'x-session-type': 'wisegolf'
        })
        
    def _setup_cookie_auth(self):
        """Setup cookie-based authentication."""
        self.session.headers.update({
            'Cookie': f"wisenetwork_session={self.auth_details['cookie_value']}",
            'x-session-type': 'wisegolf0'
        })
        
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


class WiseGolfAPI(BaseWiseGolfAPI):
    """WiseGolf API client implementation."""
    
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
    
    def __init__(self, base_url: str, auth_service: AuthService, club_details: Dict[str, Any], membership: Union[Dict[str, Any], Any]):
        """Initialize WiseGolf0 API client."""
        super().__init__(base_url, auth_service, club_details, membership)
        
        # Set REST URL from club details
        self.rest_url = club_details.get('restUrl')
        if not self.rest_url:
            self.logger.warning("No restUrl found in club_details")
            
        self.logger.debug("WiseGolf0API final headers:")
        self.logger.debug(f"Final headers: {dict(self.session.headers)}")
    
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
            return {"reservationsGolfPlayers": []}
        
        # Update headers for cross-origin request
        self.session.headers.update({
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
            "Sec-Fetch-Site": "same-site"
        })
        
        try:
            response = self.session.get(
                self.rest_url + "/reservations/",
                params=params,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            # Validate response status code
            if response.status_code != 200:
                raise WiseGolfResponseError(f"Request failed with status {response.status_code}")
            
            # Parse JSON response
            try:
                data = response.json()
            except ValueError as e:
                raise WiseGolfResponseError(f"Invalid JSON response: {str(e)}")
            
            # Validate response structure
            if not isinstance(data, dict):
                raise WiseGolfResponseError("Invalid response format")
            
            if 'reservationsGolfPlayers' not in data:
                raise WiseGolfResponseError("Missing 'reservationsGolfPlayers' field in response")
            
            return data
            
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            return {"reservationsGolfPlayers": []}
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
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