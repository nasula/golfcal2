"""Base API client for golf calendar application."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import requests
from urllib.parse import urljoin, urlencode

from ..models.golf_club import GolfClub
from ..models.user import User
from ..models.reservation import Reservation
from ..models.player import Player
from ..services.auth_service import AuthService
from ..config.models import ClubConfig, AuthDetails

class BaseGolfClub(GolfClub, ABC):
    """Base class for golf club API implementations."""
    
    def __init__(self, name: str, auth_details: Dict[str, Any], club_details: Dict[str, Any], membership: Dict[str, Any], *args, **kwargs):
        """Initialize base golf club.
        
        Args:
            name: Club name
            auth_details: Authentication details
            club_details: Club configuration details
            membership: User's membership details
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        # Convert auth_details dictionary to AuthDetails object
        auth_details_obj = AuthDetails(**auth_details)
        super().__init__(name=name, auth_details=auth_details_obj, *args, **kwargs)
        self.auth_service = AuthService()
        self.club_details = club_details
        self.membership = membership
    
    @abstractmethod
    def get_reservations(self, user: User) -> List[Reservation]:
        """Get reservations for user.
        
        Args:
            user: User to get reservations for
            
        Returns:
            List of reservations
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_reservations")
    
    def _make_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str] = None,
        params: Dict[str, str] = None,
        json: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            headers: Optional request headers
            params: Optional query parameters
            json: Optional JSON body
            
        Returns:
            Response data as dictionary
            
        Raises:
            requests.RequestException: If request fails
            ValueError: If response is not valid JSON
        """
        # Initialize headers if not provided
        if headers is None:
            headers = {}
        
        # Initialize params if not provided
        if params is None:
            params = {}
        
        # Get auth strategy based on auth type
        auth_strategy = self.auth_service.get_strategy(self.auth_details.auth_type)
        
        # Build headers and URL using strategy
        auth_headers = auth_strategy.create_headers(
            self.auth_details.cookie_name if hasattr(self.auth_details, 'cookie_name') else None,
            self.auth_details.to_dict()
        )
        headers.update(auth_headers)
        
        # Build full URL if needed
        full_url = auth_strategy.build_full_url(self.club_details, self.membership)
        if full_url:
            url = full_url
        
        # Add default content type if not set
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        # Make request
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json
        )
        response.raise_for_status()
        
        # Parse response as JSON
        try:
            return response.json()
        except ValueError as e:
            # Log the response content for debugging
            print(f"Failed to parse JSON response from {url}")
            print(f"Response status code: {response.status_code}")
            print(f"Response headers: {response.headers}")
            print(f"Response content: {response.text}")
            raise ValueError(f"Invalid JSON response from {url}: {str(e)}")