"""Tests for the base API implementation."""

import pytest
from unittest.mock import Mock, patch
from requests.exceptions import Timeout, ConnectionError, RequestException
from golfcal2.exceptions import APIError, APITimeoutError, APIResponseError, APIValidationError

@pytest.fixture
def auth_service():
    """Create a mock auth service."""
    mock = Mock()
    mock.create_headers.return_value = {"Authorization": "Bearer test-token"}
    mock.build_full_url.return_value = None  # Don't override base_url
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
    from golfcal2.api.base_api import BaseAPI
    return BaseAPI(
        base_url="https://api.test.com",
        auth_service=auth_service,
        club_details=club_details,
        membership=membership
    )

def test_base_api_initialization(auth_service, club_details, membership):
    """Test BaseAPI initialization."""
    from golfcal2.api.base_api import BaseAPI
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
    assert dict(api.session.headers) == {"Authorization": "Bearer test-token"}

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
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
    
    with pytest.raises(APIResponseError) as exc_info:
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
    if response_text and response_text != "null":
        mock_response.json.return_value = expected_result
    result = base_api._parse_response(mock_response)
    assert result == expected_result

def test_parse_response_invalid_format(base_api):
    """Test parsing invalid JSON format."""
    mock_response = Mock()
    mock_response.text = "invalid json"
    mock_response.json.side_effect = ValueError("Invalid JSON")
    
    with pytest.raises(APIValidationError) as exc_info:
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
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    
    with patch("requests.Session.request") as mock_request:
        mock_request.return_value = mock_response
        result = base_api._make_request("GET", "/test")
        assert result == {"success": True}

def test_make_request_custom_timeout(base_api):
    """Test request with custom timeout."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    
    with patch("requests.Session.request") as mock_request:
        mock_request.return_value = mock_response
        base_api._make_request("GET", "/test", timeout=30)
        mock_request.assert_called_with(
            "GET",
            "https://api.test.com/test",
            timeout=30,
            headers={"Authorization": "Bearer test-token"}
        )

def test_make_request_with_params_and_data(base_api):
    """Test request with query parameters and data."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    
    params = {"key": "value"}
    data = {"field": "test"}
    
    with patch("requests.Session.request") as mock_request:
        mock_request.return_value = mock_response
        base_api._make_request("POST", "/test", params=params, data=data)
        mock_request.assert_called_with(
            "POST",
            "https://api.test.com/test",
            params=params,
            data=data,
            timeout=10,
            headers={"Authorization": "Bearer test-token"}
        )

def test_auth_type_handling(auth_service, club_details, membership):
    """Test different authentication types."""
    from golfcal2.api.base_api import BaseAPI
    
    # Test token auth
    club_details["auth_type"] = "token"
    api = BaseAPI("https://api.test.com", auth_service, club_details, membership)
    assert dict(api.session.headers) == {"Authorization": "Bearer test-token"}
    
    # Test cookie auth
    club_details["auth_type"] = "cookie"
    api = BaseAPI("https://api.test.com", auth_service, club_details, membership)
    assert dict(api.session.cookies) == {"test_cookie": "test-token"}
    
    # Test app auth
    club_details["auth_type"] = "appauth"
    api = BaseAPI("https://api.test.com", auth_service, club_details, membership)
    assert dict(api.session.headers) == {"X-API-Key": "test_key"} 