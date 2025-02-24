# api_utils.py

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing import TypeGuard

import requests


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
    response: requests.Response | None = None
    details: dict[str, Any] | None = None

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
    data: dict[str, Any] | None = None
    errors: list[str] | None = None
    raw_response: requests.Response | None = None

def _single_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    timeout: tuple[int, int] = (7, 20),
    verify_ssl: bool = True
) -> APIResponse:
    """Make a single API request without retries."""
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

        # Handle HTTP errors
        if response.status_code == 404:
            raise APIError(
                message=f"Resource not found at {url}",
                code=APIErrorCode.NOT_FOUND,
                response=response
            )
        if response.status_code == 401:
            raise APIAuthenticationError(
                message="Authentication failed",
                code=APIErrorCode.AUTHENTICATION_FAILED,
                response=response
            )
        response.raise_for_status()

        # Parse JSON response
        json_response = response.json()

        # Check response success flag
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
        raise APITimeoutError(
            message=str(e),
            code=APIErrorCode.TIMEOUT
        )
    except requests.exceptions.ConnectionError as e:
        raise APIConnectionError(
            message=str(e),
            code=APIErrorCode.CONNECTION_ERROR
        )
    except Exception as e:
        if isinstance(e, APIError | APIAuthenticationError | APITimeoutError | APIConnectionError):
            raise
        raise APIError(
            message=f"Unexpected error: {e}",
            code=APIErrorCode.INVALID_RESPONSE
        ) from e

def make_api_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    timeout: tuple[int, int] = (7, 20),
    retry_count: int = 3,
    retry_delay: int = 5,
    verify_ssl: bool = True
) -> APIResponse:
    """
    Make an API request with retries.

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
    if logger.isEnabledFor(logging.ERROR):
        logger.error(f"Making {method} request to {url}")

    last_error = None
    for attempt in range(retry_count):
        try:
            return _single_request(
                method=method,
                url=url,
                headers=headers,
                data=data,
                params=params,
                timeout=timeout,
                verify_ssl=verify_ssl
            )
        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            if attempt < retry_count - 1:
                logger.warning(f"Request failed (attempt {attempt + 1}/{retry_count}): {e!s}")
                time.sleep(retry_delay * (2 ** attempt))
            else:
                raise
        except (APIError, APIAuthenticationError):
            raise

    # This should never be reached as the last retry will raise an exception
    assert last_error is not None
    raise last_error

def is_dict_response(data: Any) -> TypeGuard[dict[str, Any]]:
    """Type guard to verify if data is a dictionary response."""
    return isinstance(data, dict)

def is_list_response(data: Any) -> TypeGuard[list[dict[str, Any]]]:
    """Type guard to verify if data is a list of dictionaries response."""
    if not isinstance(data, list):
        return False
    return all(isinstance(x, dict) for x in data)

def _validate_wisegolf_response(data: dict[str, Any]) -> bool:
    """Validate WiseGolf API response."""
    if 'success' in data and not data['success']:
        logger.error(f"WiseGolf API error: {data.get('errors', ['Unknown error'])}")
        return False
    return True

def _validate_nexgolf_response(data: list[dict[str, Any]], required_keys: set | None = None) -> bool:
    """Validate NexGolf API response."""
    if required_keys is None:
        return True

    for item in data:
        missing = required_keys - set(item.keys())
        if missing:
            logger.error(f"Missing required keys in NexGolf response: {missing}")
            return False
    return True

def _validate_dict_response(data: dict[str, Any], required_keys: set) -> bool:
    """Validate dictionary response against required keys."""
    missing = required_keys - set(data.keys())
    if missing:
        logger.error(f"Missing required keys in response: {missing}")
        return False
    return True

def _validate_list_response(data: list[dict[str, Any]], required_keys: set) -> bool:
    """Validate list response against required keys."""
    for item in data:
        missing = required_keys - set(item.keys())
        if missing:
            logger.error(f"Missing required keys in response item: {missing}")
            return False
    return True

def validate_api_response(
    data: dict[str, Any] | list[dict[str, Any]] | None,
    required_keys: set | None = None,
    response_type: str | None = None
) -> bool:
    """
    Validate API response data structure.

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
        # Handle WiseGolf response
        if response_type == 'wisegolf':
            if not is_dict_response(data):
                logger.error("Invalid WiseGolf response structure: not a dictionary")
                return False
            return _validate_wisegolf_response(data)

        # Handle NexGolf response
        if response_type == 'nexgolf':
            if not is_list_response(data):
                logger.error("Invalid NexGolf response structure: not a list")
                return False
            return _validate_nexgolf_response(data, required_keys)

        # Handle generic response
        if not required_keys:
            return True

        if is_dict_response(data):
            return _validate_dict_response(data, required_keys)
        if is_list_response(data):
            return _validate_list_response(data, required_keys)

        logger.error(f"Invalid response type: {type(data)}")
        return False

    except Exception as e:
        logger.error(f"Error validating API response: {e!s}")
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
            error_message = str(error_data.get('message', ''))
            error_details = str(error_data.get('details', ''))
            error_code = str(error_data.get('code', ''))
            return f"Code: {error_code}, Message: {error_message}, Details: {error_details}"
    except Exception:
        # Fall through to return truncated response text
        pass
    
    # Ensure we return a string by explicitly converting response.text
    text = str(response.text)
    return text[:200] + "..." if len(text) > 200 else text

