"""
TeeTime API client.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import requests

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.models.mixins import RequestHandlerMixin

class TeeTimeAPIError(Exception):
    """TeeTime API error."""
    pass

class TeeTimeAPI(LoggerMixin, RequestHandlerMixin):
    """TeeTime API client."""
    
    def __init__(self, base_url: str, auth_details: Dict[str, str]):
        """Initialize TeeTime API client."""
        self.base_url = base_url.rstrip('/')
        self.auth_details = auth_details
        self.session = requests.Session()
        
        # Set up session headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        })
        
        # Add token to headers if present
        if 'token' in auth_details:
            self.token = auth_details['token']
            self.session.headers['Authorization'] = f'Bearer {self.token}'

    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get reservations from TeeTime API."""
        try:
            # Get date range for reservations
            now = datetime.now()
            start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            end_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")
            
            # Build request URL with correct parameter names
            params = {
                "from": start_date,
                "to": end_date
            }
            
            # Add token to params if present
            if 'token' in self.auth_details:
                params['token'] = self.auth_details['token']
            
            # Make the request
            response = self._make_request("GET", "", params=params)
            
            # Filter out non-confirmed reservations
            if isinstance(response, list):
                return [r for r in response if r.get('confirmed') == 'CONFIRMED']
            
            return []
            
        except APITimeoutError as e:
            raise TeeTimeAPIError(f"Request timed out: {str(e)}")
        except APIResponseError as e:
            raise TeeTimeAPIError(f"Request failed: {str(e)}")
        except APIAuthError as e:
            raise TeeTimeAPIError(f"Authentication failed: {str(e)}")
        except Exception as e:
            raise TeeTimeAPIError(f"Unexpected error: {str(e)}")

    def get_club_info(self, club_number: str) -> Optional[Dict[str, Any]]:
        """Get club information from TeeTime API."""
        try:
            # Build request URL
            endpoint = f"/club/{club_number}"
            params = {}
            
            # Add token to params if present
            if 'token' in self.auth_details:
                params['token'] = self.auth_details['token']
            
            # Make request
            response = self._make_request("GET", endpoint, params=params)
            
            if isinstance(response, dict):
                return response
            
            return None
            
        except APITimeoutError as e:
            raise TeeTimeAPIError(f"Request timed out: {str(e)}")
        except APIResponseError as e:
            raise TeeTimeAPIError(f"Request failed: {str(e)}")
        except APIAuthError as e:
            raise TeeTimeAPIError(f"Authentication failed: {str(e)}")
        except Exception as e:
            raise TeeTimeAPIError(f"Unexpected error: {str(e)}") 