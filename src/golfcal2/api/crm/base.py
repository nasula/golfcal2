from abc import abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import requests

from api.interfaces import CRMInterface
from api.models.reservation import Reservation, Player, CourseInfo
from models.mixins import APIError, APITimeoutError, APIResponseError, APIAuthError

class BaseCRMImplementation(CRMInterface):
    """Enhanced base class for CRM implementations with common functionality"""
    
    def __init__(self, url: str, auth_details: Dict[str, Any]):
        self.url = url.rstrip('/')
        self.auth_details = auth_details
        self.session: Optional[requests.Session] = None
        self.timeout = 30
        self._retry_count = 3
        
    @abstractmethod
    def authenticate(self) -> None:
        """Each CRM must implement its own authentication"""
        pass
    
    def get_reservations(self) -> List[Reservation]:
        """Template method that handles retries and conversion to standard model"""
        if not self.session:
            self.authenticate()
        
        for attempt in range(self._retry_count):
            try:
                raw_reservations = self._fetch_reservations()
                return [self.parse_reservation(res) for res in raw_reservations]
            except requests.Timeout as e:
                if attempt == self._retry_count - 1:
                    raise APITimeoutError(f"Timeout fetching reservations: {str(e)}")
            except requests.RequestException as e:
                if attempt == self._retry_count - 1:
                    raise APIError(f"Error fetching reservations: {str(e)}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Enhanced request helper with better error handling"""
        if not self.session:
            self.authenticate()
            
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            response = self.session.request(
                method,
                f"{self.url}/{endpoint.lstrip('/')}",
                **kwargs
            )
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                # Try to reauthenticate once
                self.authenticate()
                response = self.session.request(
                    method,
                    f"{self.url}/{endpoint.lstrip('/')}",
                    **kwargs
                )
                response.raise_for_status()
                return response
            raise APIResponseError(f"HTTP error: {str(e)}")
    
    @abstractmethod
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        """Each CRM must implement its own reservation fetching logic"""
        pass
    
    @abstractmethod
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        """Convert raw reservation to standard Reservation model"""
        pass
    
    def _parse_datetime(self, value: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
        """Enhanced datetime parser with timezone handling"""
        try:
            return datetime.strptime(value, fmt)
        except ValueError as e:
            raise APIResponseError(f"Invalid datetime format: {str(e)}") 