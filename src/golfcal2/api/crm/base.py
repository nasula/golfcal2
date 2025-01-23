from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging

from golfcal2.api.interfaces import CRMInterface
from golfcal2.api.models.reservation import Reservation, Player, CourseInfo
from golfcal2.models.mixins import (
    APIError, APITimeoutError, APIResponseError, APIAuthError, RequestHandlerMixin
)

class BaseCRM(ABC, RequestHandlerMixin):
    """Base class for CRM implementations."""
    
    def __init__(self, base_url: str, auth_details: Dict[str, Any]) -> None:
        """Initialize CRM client.
        
        Args:
            base_url: Base URL for API requests
            auth_details: Authentication details (varies by implementation)
        """
        self.base_url = base_url
        self.auth_details = auth_details
        self.logger = logging.getLogger(__name__)
        
    @abstractmethod
    def authenticate(self) -> None:
        """Authenticate with the CRM API."""
        pass
        
    @abstractmethod
    def get_reservations(self) -> List[Reservation]:
        """Get list of reservations.
        
        Returns:
            List of Reservation objects
        """
        pass
        
    @abstractmethod
    def get_players(self, reservation: Reservation) -> List[Dict[str, Any]]:
        """Get players for a reservation.
        
        Args:
            reservation: Reservation to get players for
            
        Returns:
            List of player data dictionaries
        """
        pass
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make HTTP request to CRM API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request arguments
            
        Returns:
            Response data as dictionary if successful, None otherwise
            
        Raises:
            APIError: On request failure
            APITimeoutError: On request timeout
            APIResponseError: On invalid response
            APIAuthError: On authentication failure
        """
        try:
            response = super()._make_request(method, endpoint, **kwargs)
            if not response:
                self.logger.error("Request failed: %s %s", method, endpoint)
                return None
                
            return response.json() if response.content else {}
            
        except Exception as e:
            self.logger.error("Request error: %s", str(e))
            return None
            
    def _get_json(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Get JSON response from API endpoint.
        
        Args:
            endpoint: API endpoint
            **kwargs: Additional request arguments
            
        Returns:
            Response data as dictionary
            
        Raises:
            APIError: On request failure
        """
        response = self._make_request('GET', endpoint, **kwargs)
        if not response:
            raise APIError(f"Failed to get data from {endpoint}")
        return response
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        """Each CRM must implement its own reservation fetching logic"""
        pass
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        """Convert raw reservation to standard Reservation model"""
        pass
    
    def _parse_datetime(self, value: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
        """Enhanced datetime parser with timezone handling"""
        try:
            return datetime.strptime(value, fmt)
        except ValueError as e:
            raise APIResponseError(f"Invalid datetime format: {str(e)}") 