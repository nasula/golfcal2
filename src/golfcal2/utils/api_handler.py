from typing import Dict, Any, List, Union
import requests
from http import HTTPStatus

class APIResponseError(Exception):
    """Custom exception for API response errors."""
    pass

class APIResponseValidator:
    """Common API response validation."""
    
    @staticmethod
    def validate(
        response: requests.Response,
        required_fields: List[str] = None,
        expected_status: Union[int, List[int]] = HTTPStatus.OK
    ) -> Dict[str, Any]:
        """
        Validate API response structure.
        
        Args:
            response: The response object from the request
            required_fields: List of fields that must be present in the response
            expected_status: Expected HTTP status code(s)
            
        Returns:
            Validated response data as dictionary
            
        Raises:
            APIResponseError: If validation fails
        """
        # Validate status code
        if isinstance(expected_status, int):
            expected_status = [expected_status]
            
        if response.status_code not in expected_status:
            raise APIResponseError(
                f"API returned unexpected status code: {response.status_code}"
                f" (expected {expected_status})"
            )
        
        # Parse JSON response
        try:
            data = response.json()
        except ValueError as e:
            raise APIResponseError(f"Invalid JSON response: {str(e)}")
        
        # Validate required fields if specified
        if required_fields:
            missing_fields = [
                field for field in required_fields
                if field not in data
            ]
            if missing_fields:
                raise APIResponseError(
                    f"Missing required fields: {', '.join(missing_fields)}"
                )
        
        return data
    
    @staticmethod
    def validate_list_response(
        response: requests.Response,
        item_key: str,
        required_item_fields: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Validate API response that should contain a list of items.
        
        Args:
            response: The response object from the request
            item_key: The key containing the list of items
            required_item_fields: Fields that must be present in each item
            
        Returns:
            List of validated items
            
        Raises:
            APIResponseError: If validation fails
        """
        data = APIResponseValidator.validate(response, [item_key])
        items = data[item_key]
        
        if not isinstance(items, list):
            raise APIResponseError(
                f"Expected list for key '{item_key}', got {type(items)}"
            )
        
        if required_item_fields:
            for idx, item in enumerate(items):
                missing_fields = [
                    field for field in required_item_fields
                    if field not in item
                ]
                if missing_fields:
                    raise APIResponseError(
                        f"Item at index {idx} missing required fields: "
                        f"{', '.join(missing_fields)}"
                    )
        
        return items 