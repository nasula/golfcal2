"""
Base API client for golf calendar application.
"""

import json
import time
from typing import Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from golfcal2.exceptions import APIError
from golfcal2.exceptions import APIResponseError
from golfcal2.exceptions import APITimeoutError
from golfcal2.exceptions import APIValidationError
from golfcal2.utils.logging_utils import LoggerMixin


class BaseAPI(LoggerMixin):
    """Base class for API clients."""
    
    # Default timeouts (connection timeout, read timeout)
    DEFAULT_TIMEOUT = (7, 20)
    
    # Default retry settings
    DEFAULT_RETRY_TOTAL = 3
    DEFAULT_RETRY_BACKOFF_FACTOR = 0.5
    DEFAULT_RETRY_STATUS_FORCELIST = [408, 429, 500, 502, 503, 504]
    
    def __init__(
        self,
        base_url: str,
        auth_service: Any | None = None,
        club_details: dict[str, Any] | None = None,
        membership: dict[str, Any] | Any | None = None
    ):
        """Initialize API client.

        Args:
            base_url: Base URL for API
            auth_service: Optional authentication service
            club_details: Optional club details dictionary
            membership: Optional membership details (dict or object)
        """
        super().__init__()  # Initialize LoggerMixin
        
        init_start_time = time.time()
        self.base_url = base_url.rstrip("/")
        self.auth_service = auth_service
        self.club_details = club_details or {}
        self.membership = membership
        
        # Get auth details from membership
        self.auth_details = {}
        if membership is not None:
            if isinstance(membership, dict):
                self.auth_details = membership.get('auth_details', {})
            else:
                self.auth_details = getattr(membership, 'auth_details', {})

        # Create session with retry strategy
        self.session = self._create_session()
        
        # Get authentication strategy and create headers
        auth_type = self.club_details.get('auth_type', 'token_appauth')
        cookie_name = self.club_details.get('cookie_name', '')
        
        # Create headers using auth details
        if auth_service:
            self.headers = auth_service.create_headers(auth_type, cookie_name, self.auth_details)
            self.session.headers.update(self.headers)
            
            # Build full URL with authentication parameters
            if membership is not None:
                # Convert dict to Membership object if needed
                from golfcal2.models.user import Membership
                if isinstance(membership, dict):
                    membership_obj = Membership(
                        club=membership.get('club', ''),
                        club_abbreviation=membership.get('club_abbreviation', ''),
                        duration=membership.get('duration', {'hours': 4}),
                        auth_details=membership.get('auth_details', {})
                    )
                else:
                    membership_obj = membership
                
                self.full_url = auth_service.build_full_url(auth_type, self.club_details, membership_obj)
                if self.full_url:
                    self.base_url = self.full_url
        
        init_end_time = time.time()
        self.logger.debug(f"BaseAPI: Total initialization took {init_end_time - init_start_time:.2f} seconds")
        self.logger.debug(f"BaseAPI: Final base_url: {self.base_url}")
        self.logger.debug(f"BaseAPI: Final headers: {dict(self.session.headers)}")
        self.logger.debug(f"BaseAPI: Final cookies: {dict(self.session.cookies)}")
    
    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry strategy.
        
        Returns:
            Session with configured retry strategy
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.DEFAULT_RETRY_TOTAL,
            backoff_factor=self.DEFAULT_RETRY_BACKOFF_FACTOR,
            status_forcelist=self.DEFAULT_RETRY_STATUS_FORCELIST,
            allowed_methods=["GET", "POST"]  # Allow retries for GET and POST
        )
        
        # Mount retry strategy to both HTTP and HTTPS
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _validate_response(self, response: requests.Response) -> None:
        """
        Validate response and raise appropriate errors.
        
        Args:
            response: Response to validate
            
        Raises:
            APIResponseError: If response status code indicates an error
            APIValidationError: If response content is invalid
        """
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_msg = error_data.get('message', error_data.get('error', str(e)))
            except (ValueError, AttributeError):
                error_msg = response.text or str(e)
            
            raise APIResponseError(f"Request failed: {error_msg}")
    
    def _parse_response(self, response: requests.Response) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Parse response content.
        
        Args:
            response: Response object to parse
            
        Returns:
            Parsed response data or None if empty
            
        Raises:
            APIValidationError: If response cannot be parsed
        """
        try:
            # Try to parse as JSON first
            result: dict[str, Any] | list[dict[str, Any]] = response.json()
            return result
        except ValueError:
            # If JSON parsing fails, try to handle other formats
            content = response.text.strip()
            
            # Handle empty response
            if not content:
                return None
            
            # Handle text that looks like a JSON array
            if content.startswith("[") and content.endswith("]"):
                try:
                    array_result: list[dict[str, Any]] = json.loads(content)
                    return array_result
                except json.JSONDecodeError:
                    pass
            
            # Handle "null" response
            if content == "null":
                return None
            
            # If we can't parse the content, raise an error
            raise APIValidationError(f"Failed to parse response: {content[:100]}...")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        timeout: tuple[int, int] | None = None,
        validate_response: bool = True
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """
        Make an API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            timeout: Request timeout (connection timeout, read timeout)
            validate_response: Whether to validate the response
            
        Returns:
            Response data
            
        Raises:
            APITimeoutError: If request times out
            APIResponseError: If request fails
            APIValidationError: If response validation fails
            APIError: For other errors
        """
        start_time = time.time()
        url = urljoin(self.base_url, endpoint)
        
        # Use default timeout if not specified
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=timeout
            )
            
            # Validate response if requested
            if validate_response:
                self._validate_response(response)
            
            # Parse and return response data
            result = self._parse_response(response)
            
            return result
            
        except requests.exceptions.Timeout as e:
            elapsed = time.time() - start_time
            self.logger.error(f"BaseAPI: Request timed out after {elapsed:.2f} seconds with timeout settings {timeout}: {e}")
            raise APITimeoutError(f"Request timed out after {elapsed:.2f} seconds: {e!s}")
            
        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            self.logger.error(f"BaseAPI: Request failed after {elapsed:.2f} seconds: {e}")
            raise APIResponseError(f"Request failed after {elapsed:.2f} seconds: {e!s}")
            
        except (APIResponseError, APIValidationError) as e:
            elapsed = time.time() - start_time
            self.logger.error(f"BaseAPI: API error after {elapsed:.2f} seconds: {e}")
            raise
            
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"BaseAPI: Unexpected error after {elapsed:.2f} seconds: {e}")
            raise APIError(f"Unexpected error after {elapsed:.2f} seconds: {e!s}") 