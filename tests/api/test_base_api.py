"""Tests for the base API implementation."""

import pytest
from unittest.mock import Mock, patch
from requests.exceptions import Timeout, ConnectionError, RequestException
from golfcal2.api.base_api import BaseAPI
from golfcal2.exceptions import APIError, APITimeoutError, APIResponseError

@pytest.fixture
def auth_service():
    """Create a mock auth service."""
    mock = Mock()
    mock.create_headers.return_value = {"Authorization": "Bearer test-token"}
    mock.build_full_url.return_value = "https://api.test.com/v1"
    return mock

@pytest.fixture
def club_details():
    """Create test club details."""
    return {
        "club_id": "test_club",
        "api_key": "test_key",
        "auth_type": "token_appauth",
        "cookie_name": "test_cookie"
    }

@pytest.fixture
def membership():
    """Create test membership details."""
    return {
        "user_id": "test_user",
        "auth_details": {
            "token": "test-token",
            "refresh_token": "test-refresh"
        }
    }

@pytest.fixture
def base_api(auth_service, club_details, membership):
    """Create a BaseAPI instance for testing."""
    return BaseAPI(
        base_url="https://api.test.com",
        auth_service=auth_service,
        club_details=club_details,
        membership=membership
    )

def test_base_api_initialization(auth_service, club_details, membership):
    """Test BaseAPI initialization."""
    api = BaseAPI(
        base_url="https://api.test.com",
        auth_service=auth_service,
        club_details=club_details,
        membership=membership
    )
    assert api.base_url == "https://api.test.com"
    assert api.auth_service == auth_service
    assert api.club_details == club_details
    assert api.membership == membership
    assert api.headers == {"Authorization": "Bearer test-token"}

def test_create_session_retry_config(base_api):
    """Test session creation with retry configuration."""
    session = base_api._create_session()
    assert session.adapters["https://"].max_retries.total == 3
    assert session.adapters["http://"].max_retries.total == 3

@pytest.mark.parametrize("status_code,response_text,expected_error", [
    (400, '{"error": "Bad Request"}', "Request failed: Bad Request"),
    (401, '{"message": "Unauthorized"}', "Request failed: Unauthorized"),
    (500, "Internal Server Error", "Request failed: Internal Server Error")
])
def test_validate_response_errors(base_api, status_code, response_text, expected_error):
    """Test response validation with different error scenarios."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.text = response_text
    
    with pytest.raises(APIError) as exc_info:
        base_api._validate_response(mock_response)
    assert str(exc_info.value) == expected_error

@pytest.mark.parametrize("response_text,expected_result", [
    ('{"key": "value"}', {"key": "value"}),
    ('[{"id": 1}, {"id": 2}]', [{"id": 1}, {"id": 2}]),
    ("", None),
    ("null", None)
])
def test_parse_response_formats(base_api, response_text, expected_result):
    """Test parsing different response formats."""
    mock_response = Mock()
    mock_response.text = response_text
    result = base_api._parse_response(mock_response)
    assert result == expected_result

def test_parse_response_invalid_format(base_api):
    """Test parsing invalid JSON response."""
    mock_response = Mock()
    mock_response.text = "Invalid JSON"
    with pytest.raises(APIError) as exc_info:
        base_api._parse_response(mock_response)
    assert "Failed to parse response" in str(exc_info.value)

@pytest.mark.parametrize("exception_class,expected_error", [
    (Timeout, APITimeoutError),
    (ConnectionError, APIResponseError),
    (RequestException, APIResponseError),
    (Exception, APIError)
])
def test_make_request_error_handling(base_api, exception_class, expected_error):
    """Test error handling in make_request method."""
    with patch("requests.Session.request") as mock_request:
        mock_request.side_effect = exception_class("Test error")
        with pytest.raises(expected_error):
            base_api._make_request("GET", "/test")

def test_make_request_success(base_api):
    """Test successful request."""
    with patch("requests.Session.request") as mock_request:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test"}'
        mock_request.return_value = mock_response
        
        result = base_api._make_request("GET", "/test")
        assert result == {"data": "test"}
        mock_request.assert_called_once()

def test_make_request_custom_timeout(base_api):
    """Test request with custom timeout."""
    with patch("requests.Session.request") as mock_request:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{}'
        mock_request.return_value = mock_response
        
        base_api._make_request("GET", "/test", timeout=30)
        mock_request.assert_called_with(
            "GET",
            "https://api.test.com/test",
            headers=base_api.headers,
            timeout=30,
            params=None,
            json=None
        )

def test_make_request_with_params_and_data(base_api):
    """Test request with query parameters and JSON data."""
    with patch("requests.Session.request") as mock_request:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{}'
        mock_request.return_value = mock_response
        
        params = {"filter": "test"}
        data = {"key": "value"}
        base_api._make_request("POST", "/test", params=params, json=data)
        mock_request.assert_called_with(
            "POST",
            "https://api.test.com/test",
            headers=base_api.headers,
            timeout=10,
            params=params,
            json=data
        )

def test_auth_type_handling(auth_service, club_details, membership):
    """Test handling of different authentication types."""
    # Test with different auth_type
    club_details["auth_type"] = "basic_auth"
    auth_service.create_headers.return_value = {"Authorization": "Basic test"}
    auth_service.build_full_url.return_value = "https://api.test.com/v2"

    api = BaseAPI(
        base_url="https://api.test.com",
        auth_service=auth_service,
        club_details=club_details,
        membership=membership
    )
    
    auth_service.create_headers.assert_called_with(
        "basic_auth",
        "test_cookie",
        membership["auth_details"]
    )
    assert api.headers == {"Authorization": "Basic test"} 