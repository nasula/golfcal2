"""
NexGolf API client for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import time
import requests

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.models.mixins import RequestHandlerMixin
from golfcal2.models.mixins import APIError, APITimeoutError, APIResponseError, APIAuthError

class NexGolfAPI(LoggerMixin, RequestHandlerMixin):
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
        # Use headers from auth_details if provided, otherwise use defaults
        headers = self.auth_details.get('headers', {})
        if not headers:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
                'Referer': 'https://pgc.nexgolf.fi/pgc/member/index.html',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }
            
            # Add auth token if provided
            if 'X-Auth-Token' in self.auth_details:
                headers['X-Auth-Token'] = self.auth_details['X-Auth-Token']
            
            # Parse cookies from auth_details
            cookies = {}
            if 'cookie_value' in self.auth_details:
                cookies['JSESSIONID'] = self.auth_details['cookie_value']
            cookies['NGLOCALE'] = 'fi'
            
            # Set cookies in session
            self.session.cookies.update(cookies)
        
        # Update session headers
        self.session.headers.update(headers)
        
        # Log headers for debugging (excluding sensitive values)
        debug_headers = headers.copy()
        for sensitive_key in ['X-Auth-Token', 'Cookie']:
            if sensitive_key in debug_headers:
                debug_headers[sensitive_key] = '***'
        self.debug("Session headers", headers=debug_headers)
    
    def get_reservations(self) -> List[Dict[str, Any]]:
        """Get user's reservations."""
        # Calculate date range (6 months ahead)
        end_date = datetime.now().date() + timedelta(days=180)
        
        params = {
            'noCache': int(time.time() * 1000),  # Current timestamp in milliseconds
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