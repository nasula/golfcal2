"""
NexGolf API client for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

import requests

from golfcal.utils.logging_utils import LoggerMixin

class NexGolfAPIError(Exception):
    """NexGolf API error."""
    pass

class NexGolfAPI(LoggerMixin):
    """NexGolf API client."""
    
    def __init__(self, base_url: str, auth_details: Dict[str, str]):
        """Initialize NexGolf API client."""
        self.base_url = base_url.rstrip("/")
        self.auth_details = auth_details
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*"
        })
        
        # Set up authentication
        if "cookie_value" in auth_details:
            # Cookie-based auth (PGC)
            self.session.headers.update({
                "Cookie": f"NGLOCALE=fi; JSESSIONID={auth_details['cookie_value']}"
            })
            if "X-Auth-Token" in auth_details:
                self.session.headers.update({
                    "X-Auth-Token": auth_details["X-Auth-Token"]
                })
        elif "token" in auth_details:
            # Token-based auth (TeeTime)
            self.token = auth_details["token"]
        else:
            raise NexGolfAPIError("No valid authentication details provided")
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, str]] = None,
                     data: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Dict[str, Any]:
        """Make HTTP request to API."""
        url = urljoin(self.base_url, endpoint)
        
        # Log request details
        self.logger.debug(f"Making {method} request to {url}")
        self.logger.debug(f"Headers: {self.session.headers}")
        self.logger.debug(f"Params: {params}")
        self.logger.debug(f"Data: {data}")
        
        try:
            response = self.session.request(method=method, url=url, params=params,
                                         json=data, timeout=timeout)
            response.raise_for_status()
            
            # Log response details
            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response text: {response.text}")
            
            try:
                response_data = response.json()
                return response_data
            except ValueError:
                self.logger.error(f"Failed to parse JSON response: {response.text}")
                raise NexGolfAPIError("Invalid JSON response")
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise NexGolfAPIError(f"Request failed: {str(e)}")
    
    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get user's reservations."""
        # Calculate date range - include past 30 days and future 180 days
        now = datetime.now()
        from_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = (now + timedelta(days=180)).strftime("%Y-%m-%d")
        
        params = {
            "from": from_date,
            "to": to_date
        }
        
        # Add token to query parameters for TeeTime
        if hasattr(self, "token"):
            params["token"] = self.token
        
        # Log request details
        self.logger.debug(f"NexGolf API request to {self.base_url} with params: {params}")
        self.logger.debug(f"Headers: {self.session.headers}")
        
        try:
            # Use the correct endpoint path for NexGolf
            response = self._make_request("GET", "/pgc/member/api/flight/own", params=params)
            self.logger.debug(f"NexGolf API raw response: {response}")
            
            if isinstance(response, dict):
                if "rows" in response:
                    rows = response["rows"]
                    self.logger.debug(f"Found {len(rows)} reservations in 'rows'")
                    return rows
                elif "reservations" in response:
                    reservations = response["reservations"]
                    self.logger.debug(f"Found {len(reservations)} reservations in 'reservations'")
                    return reservations
                else:
                    self.logger.warning(f"Response does not contain 'rows' or 'reservations' key. Keys: {response.keys()}")
                    return []
            elif isinstance(response, list):
                self.logger.debug(f"Found {len(response)} reservations in list response")
                return response
            else:
                self.logger.error(f"Unexpected response type: {type(response)}")
                return []
            
        except Exception as e:
            self.logger.error(f"Error fetching reservations: {e}")
            raise