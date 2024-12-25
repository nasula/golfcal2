# api_utils.py

from __future__ import annotations

import logging
import json
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List, Union
import requests
from enum import Enum

logger = logging.getLogger(__name__)

class APIErrorCode(Enum):
    """Enumeration of possible API error codes."""
    AUTHENTICATION_FAILED = "auth_failed"
    NOT_FOUND = "not_found"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"

@dataclass
class APIError(Exception):
    """Base exception for API-related errors."""
    message: str
    code: APIErrorCode
    response: Optional[requests.Response] = None
    details: Optional[Dict[str, Any]] = None

class APITimeoutError(APIError):
    """Raised when an API request times out."""
    pass

class APIAuthenticationError(APIError):
    """Raised when authentication fails."""
    pass

class APIConnectionError(APIError):
    """Raised when there's a network connection error."""
    pass

@dataclass
class APIResponse:
    """Structured response from API requests."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    raw_response: Optional[requests.Response] = None

def make_api_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, str]] = None,
    timeout: Tuple[int, int] = (7, 20),
    retry_count: int = 3,
    retry_delay: int = 5,
    verify_ssl: bool = True
) -> APIResponse:
    """
    Make an API request with comprehensive error handling and retries.

    Args:
        method: HTTP method to use (GET, POST, etc.)
        url: Target URL for the request
        headers: Optional HTTP headers
        data: Optional request body data
        params: Optional URL parameters
        timeout: Tuple of (connect timeout, read timeout)
        retry_count: Number of retries on failure
        retry_delay: Delay between retries in seconds
        verify_ssl: Whether to verify SSL certificates

    Returns:
        APIResponse object containing the response data and metadata

    Raises:
        APIAuthenticationError: When authentication fails
        APITimeoutError: When request times out
        APIConnectionError: When network connection fails
        APIError: For other API-related errors
    """
    safe_headers = {k: v for k, v in (headers or {}).items() if 'cookie' not in k.lower()}
    if logger.isEnabledFor(logging.ERROR):
        logger.error(f"Making {method} request to {url}")

    for attempt in range(retry_count):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=timeout,
                verify=verify_ssl
            )

            if response.status_code == 404:
                raise APIError(
                    message=f"Resource not found at {url}",
                    code=APIErrorCode.NOT_FOUND,
                    response=response
                )

            if response.status_code == 401:
                error_msg = "Authentication failed"
                if 'error' in response.headers:
                    error_msg += f": {response.headers['error']}"
                raise APIAuthenticationError(
                    message=error_msg,
                    code=APIErrorCode.AUTHENTICATION_FAILED,
                    response=response
                )

            response.raise_for_status()

            try:
                json_response = response.json()
                if not json_response.get('success', True):
                    return APIResponse(
                        success=False,
                        errors=json_response.get('errors', []),
                        raw_response=response
                    )

                return APIResponse(
                    success=True,
                    data=json_response,
                    raw_response=response
                )

            except json.JSONDecodeError as e:
                raise APIError(
                    message=f"Failed to decode JSON response: {e}",
                    code=APIErrorCode.INVALID_RESPONSE,
                    response=response,
                    details={"raw_text": response.text}
                )

        except requests.exceptions.Timeout as e:
            if attempt == retry_count - 1:
                raise APITimeoutError(
                    message=f"Request timed out after {retry_count} retries: {e}",
                    code=APIErrorCode.TIMEOUT
                )
            logger.warning(f"Request timed out (attempt {attempt + 1}/{retry_count})")
            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
            continue

        except requests.exceptions.ConnectionError as e:
            if attempt == retry_count - 1:
                raise APIConnectionError(
                    message=f"Connection failed after {retry_count} retries: {e}",
                    code=APIErrorCode.CONNECTION_ERROR
                )
            logger.warning(f"Connection error (attempt {attempt + 1}/{retry_count})")
            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
            continue

        except Exception as e:
            raise APIError(
                message=f"Unexpected error: {e}",
                code=APIErrorCode.INVALID_RESPONSE
            )

    return APIResponse(success=False, errors=["Max retries exceeded"])

def validate_api_response(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    required_keys: Optional[set] = None,
    response_type: Optional[str] = None
) -> bool:
    """
    Validate API response structure and required keys.

    Args:
        data: Response data to validate
        required_keys: Set of required keys in the response
        response_type: Expected type of response ('wisegolf' or 'nexgolf')

    Returns:
        bool: True if response is valid, False otherwise
    """
    if data is None:
        logger.error("Response data is None")
        return False

    try:
        if response_type == 'wisegolf':
            if not isinstance(data, dict):
                logger.error("Invalid WiseGolf response structure: not a dictionary")
                return False
            if 'success' in data and not data['success']:
                logger.error(f"WiseGolf API error: {data.get('errors', ['Unknown error'])}")
                return False
            return True

        elif response_type == 'nexgolf':
            if not isinstance(data, list):
                logger.error("Invalid NexGolf response structure: not a list")
                return False
            
            if required_keys:
                missing_keys = set()
                for item in data:
                    if not isinstance(item, dict):
                        logger.error("Invalid NexGolf response item: not a dictionary")
                        return False
                    missing = required_keys - set(item.keys())
                    if missing:
                        missing_keys.update(missing)
                
                if missing_keys:
                    logger.error(f"Missing required keys in NexGolf response: {missing_keys}")
                    return False
            return True

        # Generic validation
        if required_keys:
            if isinstance(data, dict):
                missing = required_keys - set(data.keys())
                if missing:
                    logger.error(f"Missing required keys in response: {missing}")
                    return False
            elif isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        logger.error("Invalid response item: not a dictionary")
                        return False
                    missing = required_keys - set(item.keys())
                    if missing:
                        logger.error(f"Missing required keys in response item: {missing}")
                        return False

        return True

    except Exception as e:
        logger.error(f"Error validating API response: {str(e)}")
        return False

def get_error_details(response: requests.Response) -> str:
    """
    Extract detailed error information from a response.

    Args:
        response: The requests.Response object

    Returns:
        str: Formatted error details
    """
    try:
        error_data = response.json()
        if isinstance(error_data, dict):
            error_message = error_data.get('message', '')
            error_details = error_data.get('details', '')
            error_code = error_data.get('code', '')
            return f"Code: {error_code}, Message: {error_message}, Details: {error_details}"
    except:
        pass
    
    return response.text[:200] + "..." if len(response.text) > 200 else response.text

