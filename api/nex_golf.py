"""
NexGolf API client for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import requests

from golfcal2.models.mixins import RequestHandlerMixin
from golfcal2.models.mixins import APIError, APITimeoutError, APIResponseError, APIAuthError

class NexGolfAPI(RequestHandlerMixin):
    """NexGolf API client."""
    
    def __init__(self, base_url: str, auth_details: Dict[str, str]):
        """Initialize API client."""
        super().__init__()
        self.base_url = base_url
        self.auth_details = auth_details
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self) -> None:
        """Set up session with authentication."""
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Add auth details if provided
        if self.auth_details:
            self.session.headers.update({
                'Authorization': f"Bearer {self.auth_details.get('token', '')}"
            })
    
    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get user's reservations."""
        # Calculate date range (6 months ahead)
        start_date = datetime.now().date() - timedelta(days=30)
        end_date = datetime.now().date() + timedelta(days=180)
        
        params = {
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d')
        }
        
        try:
            response = self._make_request("GET", "/pgc/member/api/flight/own", params=params)
            return self._extract_data_from_response(response)
            
        except APITimeoutError as e:
            self.logger.error(f"Request timed out: {e}")
            return []
            
        except APIResponseError as e:
            self.logger.error(f"Request failed: {e}")
            return []
            
        except APIAuthError as e:
            self.logger.error(f"Authentication failed: {e}")
            return []
            
        except APIError as e:
            self.logger.error(f"API error: {e}")
            return []