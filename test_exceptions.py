import unittest
from unittest.mock import patch
from exceptions import (
    GolfCalError,
    APIError,
    LegacyAPIError,
    APITimeoutError,
    APIRateLimitError,
    APIResponseError,
    AuthError,
    ConfigError,
    ValidationError,
    WeatherError,
    WeatherServiceUnavailable,
    WeatherDataError,
    CalendarError,
    CalendarWriteError,
    CalendarEventError,
    ErrorCode,
    handle_errors
)
import requests
from typing import Optional

class TestExceptions(unittest.TestCase):
    def test_golfcal_error_with_details(self):
        details = {"field": "temperature", "value": "invalid"}
        error = GolfCalError("Validation failed", ErrorCode.VALIDATION_FAILED, details)
        self.assertEqual(error.message, "Validation failed")
        self.assertEqual(error.code, ErrorCode.VALIDATION_FAILED)
        self.assertEqual(error.details, details)
        self.assertIn("Details:", str(error))

    def test_api_error_with_response(self):
        response = requests.Response()
        response.status_code = 404
        details = {"error": "Not found"}
        
        error = APIError(
            "API request failed",
            code=ErrorCode.REQUEST_FAILED,
            response=response,
            details=details
        )
        
        self.assertEqual(error.message, "API request failed")
        self.assertEqual(error.code, ErrorCode.REQUEST_FAILED)
        self.assertEqual(error.response, response)
        self.assertEqual(error.details, details)

    def test_legacy_api_error(self):
        message = "Legacy error"
        error = LegacyAPIError(message)
        self.assertEqual(str(error), message)
        self.assertIsInstance(error, Exception)

    def test_api_timeout_error(self):
        details = {"timeout": 30}
        error = APITimeoutError("Request timed out", details)
        self.assertEqual(error.message, "Request timed out")
        self.assertEqual(error.code, ErrorCode.TIMEOUT)
        self.assertEqual(error.details, details)

    def test_api_rate_limit_error(self):
        retry_after = 60
        error = APIRateLimitError("Rate limit exceeded", retry_after)
        self.assertEqual(error.message, "Rate limit exceeded")
        self.assertEqual(error.code, ErrorCode.RATE_LIMITED)
        self.assertEqual(error.details["retry_after"], retry_after)

    def test_api_response_error(self):
        response = requests.Response()
        response.status_code = 500
        error = APIResponseError("Server error", response)
        self.assertEqual(error.message, "Server error")
        self.assertEqual(error.code, ErrorCode.INVALID_RESPONSE)
        self.assertEqual(error.response, response)

    def test_auth_error(self):
        details = {"token": "expired"}
        error = AuthError("Authentication failed", details)
        self.assertEqual(error.message, "Authentication failed")
        self.assertEqual(error.code, ErrorCode.AUTH_FAILED)
        self.assertEqual(error.details, details)

    def test_config_error(self):
        details = {"missing_key": "api_key"}
        error = ConfigError("Invalid configuration", details)
        self.assertEqual(error.message, "Invalid configuration")
        self.assertEqual(error.code, ErrorCode.CONFIG_INVALID)
        self.assertEqual(error.details, details)

    def test_validation_error(self):
        details = {"field": "date", "error": "invalid format"}
        error = ValidationError("Validation error", details)
        self.assertEqual(error.message, "Validation error")
        self.assertEqual(error.code, ErrorCode.VALIDATION_FAILED)
        self.assertEqual(error.details, details)

    def test_weather_error(self):
        details = {"provider": "test"}
        error = WeatherError("Weather service error", ErrorCode.SERVICE_ERROR, details)
        self.assertEqual(error.message, "Weather service error")
        self.assertEqual(error.code, ErrorCode.SERVICE_ERROR)
        self.assertEqual(error.details, details)

    def test_weather_service_unavailable(self):
        details = {"provider": "test", "status": "down"}
        error = WeatherServiceUnavailable("Service unavailable", details)
        self.assertEqual(error.message, "Service unavailable")
        self.assertEqual(error.code, ErrorCode.SERVICE_UNAVAILABLE)
        self.assertEqual(error.details, details)

    def test_weather_data_error(self):
        details = {"field": "temperature", "reason": "missing"}
        error = WeatherDataError("Invalid weather data", details)
        self.assertEqual(error.message, "Invalid weather data")
        self.assertEqual(error.code, ErrorCode.INVALID_RESPONSE)
        self.assertEqual(error.details, details)

    def test_calendar_error(self):
        details = {"calendar_id": "test"}
        error = CalendarError("Calendar error", ErrorCode.SERVICE_ERROR, details)
        self.assertEqual(error.message, "Calendar error")
        self.assertEqual(error.code, ErrorCode.SERVICE_ERROR)
        self.assertEqual(error.details, details)

    def test_calendar_write_error(self):
        file_path = "/path/to/calendar.ics"
        error = CalendarWriteError("Write failed", file_path)
        self.assertEqual(error.message, "Write failed")
        self.assertEqual(error.code, ErrorCode.SERVICE_ERROR)
        self.assertEqual(error.details["file_path"], file_path)

    def test_calendar_event_error(self):
        event_type = "tournament"
        details = {"start_date": "2024-01-01"}
        error = CalendarEventError("Invalid event", event_type, details)
        self.assertEqual(error.message, "Invalid event")
        self.assertEqual(error.code, ErrorCode.VALIDATION_FAILED)
        self.assertEqual(error.details["event_type"], event_type)
        self.assertEqual(error.details["start_date"], "2024-01-01")

    @patch('golfcal2.config.error_aggregator.aggregate_error')
    def test_error_handler(self, mock_aggregate_error):
        def fallback() -> str:
            return "fallback"

        # Test handling of specific error type
        with self.assertRaises(WeatherError):
            with handle_errors(WeatherError, "weather", "test"):
                raise WeatherError("Test error")
        mock_aggregate_error.assert_called_once()
        mock_aggregate_error.reset_mock()

        # Test fallback behavior
        with handle_errors(WeatherError, "weather", "test", fallback) as result:
            raise WeatherError("Test error with fallback")
            result = None  # This line should not be reached
        self.assertEqual(fallback(), "fallback")
        mock_aggregate_error.assert_called_once()
        mock_aggregate_error.reset_mock()

        # Test handling of unexpected error
        with self.assertRaises(ValueError):
            with handle_errors(WeatherError, "weather", "test"):
                raise ValueError("Unexpected error")
        mock_aggregate_error.assert_called_once()
        mock_aggregate_error.reset_mock()

        # Test fallback for unexpected error
        with handle_errors(WeatherError, "weather", "test", fallback) as result:
            raise ValueError("Unexpected error with fallback")
            result = None  # This line should not be reached
        self.assertEqual(fallback(), "fallback")
        mock_aggregate_error.assert_called_once()

if __name__ == '__main__':
    unittest.main() 