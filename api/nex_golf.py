"""
NexGolf API client for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

import requests

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.models.mixins import RequestHandlerMixin

class NexGolfAPIError(Exception):
    """NexGolf API error."""
    pass

class NexGolfAPI(LoggerMixin, RequestHandlerMixin):
    """NexGolf API client."""
    
    def __init__(self, base_url: str, auth_details: Dict[str, str]):
        """Initialize NexGolf API client."""
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
        """Get user's reservations."""
        try:
            # Calculate date range - include past 30 days and future 180 days
            now = datetime.now()
            from_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            to_date = (now + timedelta(days=180)).strftime("%Y-%m-%d")
            
            params = {
                "from": from_date,
                "to": to_date
            }
            
            # Add token to query parameters if needed
            if hasattr(self, "token"):
                params["token"] = self.token
            
            # Use the correct endpoint path for NexGolf
            response = self._make_request("GET", "/pgc/member/api/flight/own", params=params)
            return self._extract_data_from_response(response)
            
        except APITimeoutError as e:
            raise NexGolfAPIError(f"Request timed out: {str(e)}")
        except APIResponseError as e:
            raise NexGolfAPIError(f"Request failed: {str(e)}")
        except APIAuthError as e:
            raise NexGolfAPIError(f"Authentication failed: {str(e)}")
        except Exception as e:
            raise NexGolfAPIError(f"Unexpected error: {str(e)}")