import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import requests

from golfcal2.api.models.reservation import Reservation
from golfcal2.models.mixins import APIError, APIResponseError, RequestHandlerMixin


class BaseCRM(ABC, RequestHandlerMixin):
    """Base class for CRM implementations."""
    
    def __init__(self, base_url: str, auth_details: dict[str, Any]) -> None:
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
        raise NotImplementedError
        
    @abstractmethod
    def get_reservations(self) -> list[Reservation]:
        """Get list of reservations.
        
        Returns:
            List of Reservation objects
        """
        raise NotImplementedError
        
    @abstractmethod
    def get_players(self, reservation: Reservation) -> list[dict[str, Any]]:
        """Get players for a reservation.
        
        Args:
            reservation: Reservation to get players for
            
        Returns:
            List of player data dictionaries
        """
        raise NotImplementedError
        
    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> dict[str, Any]:
        """Make HTTP request to CRM API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request arguments
            
        Returns:
            Response data as dictionary
            
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
                return {}
                
            if isinstance(response, requests.Response):
                return response.json() if response.content else {}
            return response
            
        except Exception as e:
            self.logger.error("Request error: %s", str(e))
            return {}
            
    def _get_json(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
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
    
    @abstractmethod
    def _fetch_reservations(self) -> list[dict[str, Any]]:
        """Each CRM must implement its own reservation fetching logic.
        
        Returns:
            List of raw reservation dictionaries
        """
        raise NotImplementedError
    
    @abstractmethod
    def parse_reservation(self, raw_reservation: dict[str, Any]) -> Reservation:
        """Convert raw reservation to standard Reservation model.
        
        Args:
            raw_reservation: Raw reservation data from API
            
        Returns:
            Standardized Reservation object
        """
        raise NotImplementedError
    
    def _parse_datetime(self, value: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
        """Enhanced datetime parser with timezone handling.
        
        Args:
            value: Datetime string to parse
            fmt: Expected datetime format
            
        Returns:
            Parsed datetime object
            
        Raises:
            APIResponseError: If datetime format is invalid
        """
        try:
            return datetime.strptime(value, fmt)
        except ValueError as e:
            raise APIResponseError(f"Invalid datetime format: {e!s}") 