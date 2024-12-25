"""
TeeTime API client.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import requests

from golfcal.utils.logging_utils import LoggerMixin

class TeeTimeAPI(LoggerMixin):
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
        
        # For now, don't use If-None-Match to ensure we always get fresh data
        # if 'cookie' in auth_details:
        #     self.session.headers['If-None-Match'] = f'"{auth_details["cookie"]}"'
        #     self.logger.debug(f"TeeTimeAPI: Added If-None-Match header: {self.session.headers['If-None-Match']}")
    
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
            response = self.session.get(self.base_url, params=params)
            
            if response.status_code == 404:
                self.logger.error(f"TeeTimeAPI: 404 Not Found for URL: {response.url}")
                return []
            
            # Handle 304 Not Modified
            if response.status_code == 304:
                return []
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            if not isinstance(data, list):
                self.logger.warning(f"TeeTimeAPI: Unexpected response format: {data}")
                return []
            
            # Filter out non-confirmed reservations
            reservations = [r for r in data if r.get('confirmed') == 'CONFIRMED']
            
            return reservations
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"TeeTimeAPI: Request failed: {str(e)}")
            self.logger.error(f"TeeTimeAPI: Request URL was: {self.base_url}")
            self.logger.error(f"TeeTimeAPI: Request params were: {params}")
            return []
        except Exception as e:
            self.logger.error(f"TeeTimeAPI: Unexpected error: {str(e)}", exc_info=True)
            return []
    
    def get_club_info(self, club_number: str) -> Optional[Dict[str, Any]]:
        """Get club information from TeeTime API."""
        try:
            # Build request URL
            url = f"{self.base_url}/club/{club_number}"
            params = {}
            
            # Add token to params if present
            if 'token' in self.auth_details:
                params['token'] = self.auth_details['token']
            
            # Make request
            response = self.session.get(url, params=params)
            
            if response.status_code == 404:
                self.logger.error(f"TeeTimeAPI: Club not found: {club_number}")
                return None
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            if not isinstance(data, dict):
                self.logger.warning(f"TeeTimeAPI: Unexpected response format: {data}")
                return None
            
            return data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"TeeTimeAPI: Request failed: {str(e)}")
            self.logger.error(f"TeeTimeAPI: Request URL was: {url}")
            self.logger.error(f"TeeTimeAPI: Request params were: {params}")
            return None
        except Exception as e:
            self.logger.error(f"TeeTimeAPI: Unexpected error: {str(e)}", exc_info=True)
            return None 