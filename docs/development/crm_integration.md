# CRM Integration Guide

This document describes how to integrate new Customer Relationship Management (CRM) systems with the golf calendar application.

## Architecture Overview

The application uses a layered approach for CRM integration:

1. **Interface Layer**: `CRMInterface` defines the contract
2. **Base Implementation**: `BaseCRMImplementation` provides common functionality
3. **Specific Implementations**: Individual CRM system implementations
4. **Data Models**: Standardized models for cross-CRM compatibility

## Core Components

### 1. CRM Interface

The `CRMInterface` defines the required contract:

```python
class CRMInterface(ABC):
    """Interface defining required methods for CRM integrations"""
    
    @abstractmethod
    def authenticate(self) -> None:
        """Handle CRM-specific authentication"""
        pass
        
    @abstractmethod
    def get_reservations(self) -> List[Reservation]:
        """Fetch user's reservations from the CRM system"""
        pass
        
    @abstractmethod
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        """Convert CRM-specific reservation format to standard model"""
        pass
```

### 2. Base Implementation

The `BaseCRMImplementation` provides common functionality:

```python
class BaseCRMImplementation(CRMInterface):
    """Enhanced base class for CRM implementations"""
    
    def __init__(self, url: str, auth_details: Dict[str, Any]):
        self.url = url.rstrip('/')
        self.auth_details = auth_details
        self.session: Optional[requests.Session] = None
        self.timeout = 30
        self._retry_count = 3
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Enhanced request helper with authentication retry and error handling"""
        if not self.session:
            self.authenticate()
            
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            response = self.session.request(
                method,
                f"{self.url}/{endpoint.lstrip('/')}",
                **kwargs
            )
            response.raise_for_status()
            return response
            
        except requests.Timeout as e:
            raise APITimeoutError(
                f"Request timed out: {str(e)}",
                {"endpoint": endpoint, "method": method}
            )
            
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                # Try to reauthenticate once
                self.authenticate()
                response = self.session.request(
                    method,
                    f"{self.url}/{endpoint.lstrip('/')}",
                    **kwargs
                )
                response.raise_for_status()
                return response
            raise APIResponseError(
                f"HTTP error: {str(e)}",
                {"status_code": e.response.status_code}
            )
```

### 3. Data Models

```python
@dataclass
class Player:
    first_name: str
    family_name: str
    handicap: Optional[float] = None
    club_abbreviation: Optional[str] = None
    player_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

@dataclass
class CourseInfo:
    name: str
    holes: int = 18
    par: Optional[int] = None
    slope: Optional[float] = None
    course_rating: Optional[float] = None
    tee_color: Optional[str] = None
    club_id: Optional[str] = None

@dataclass
class Reservation:
    datetime_start: datetime
    players: List[Player]
    course_info: Optional[CourseInfo] = None
    booking_reference: Optional[str] = None
    status: Optional[str] = None
    cart: Optional[bool] = None
    notes: Optional[str] = None
    confirmation_sent: bool = False
```

## Implementation Guide

### 1. Create CRM Implementation

Create a new file in `api/crm/` directory:

```python
# api/crm/new_crm.py
from typing import Dict, Any, List, Optional
from datetime import datetime

from api.crm.base import BaseCRMImplementation
from api.models.reservation import Reservation, Player, CourseInfo
from api.errors import APIError, APIAuthError

class NewCRMImplementation(BaseCRMImplementation):
    def authenticate(self) -> None:
        """Implement CRM-specific authentication."""
        self.session = requests.Session()
        
        try:
            response = self.session.post(
                f"{self.url}/auth",
                json={
                    "username": self.auth_details["username"],
                    "password": self.auth_details["password"]
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            token = response.json()["token"]
            self.session.headers.update({
                "Authorization": f"Bearer {token}"
            })
            
        except Exception as e:
            raise APIAuthError(
                f"Authentication failed: {str(e)}",
                {"url": self.url}
            )
    
    def get_reservations(self) -> List[Reservation]:
        """Template method that handles retries and conversion."""
        if not self.session:
            self.authenticate()
        
        raw_reservations = self._fetch_reservations()
        return [self.parse_reservation(res) for res in raw_reservations]
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        """Implement raw reservation fetching."""
        response = self._make_request('GET', '/reservations')
        return response.json()['data']
    
    def parse_reservation(self, raw: Dict[str, Any]) -> Reservation:
        """Convert CRM format to standard Reservation model."""
        return Reservation(
            datetime_start=self._parse_datetime(
                raw["startTime"],
                fmt="%Y-%m-%dT%H:%M:%S"
            ),
            players=self._parse_players(raw),
            course_info=self._parse_course_info(raw),
            booking_reference=raw.get("reference"),
            status=raw.get("status"),
            cart=raw.get("cart", False),
            notes=raw.get("notes")
        )
```

### 2. Configuration

Add to `config/clubs.json`:

```json
{
    "new_club": {
        "name": "New Golf Club",
        "crm": {
            "type": "new_crm",
            "url": "https://api.newcrm.com/v1",
            "auth": {
                "username": "USERNAME",
                "password": "PASSWORD"
            }
        }
    }
}
```

## Error Handling

### 1. Error Types

```python
class APIError(Exception):
    """Base class for API-related errors"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.context = context or {}
        super().__init__(message)

class APITimeoutError(APIError):
    """Raised when API requests timeout"""
    pass

class APIResponseError(APIError):
    """Raised for invalid API responses"""
    pass

class APIAuthError(APIError):
    """Raised for authentication failures"""
    pass
```

### 2. Error Handling Patterns

```python
@handle_errors(APIError, "crm", "fetch reservations")
def get_reservations(self) -> List[Reservation]:
    try:
        raw_data = self._fetch_reservations()
        return [self.parse_reservation(res) for res in raw_data]
    except Exception as e:
        raise APIError(
            f"Failed to get reservations: {str(e)}",
            {"url": self.url}
        )
```

## Best Practices

### 1. Authentication
- Store credentials securely in configuration
- Implement token refresh mechanisms
- Handle authentication failures gracefully
- Use appropriate timeout values

### 2. Data Parsing
- Handle missing or null fields gracefully
- Convert data types appropriately
- Validate data ranges and formats
- Use timezone-aware datetime handling

### 3. Error Handling
- Use specific error types
- Include context in error messages
- Implement proper retries
- Log errors appropriately

### 4. Testing
- Test authentication flows
- Verify data parsing
- Test error scenarios
- Check timezone handling
- Validate retry mechanisms

### 5. Performance
- Use connection pooling
- Implement caching where appropriate
- Handle rate limiting
- Optimize request patterns

## Existing Implementations

Reference implementations available:

1. **WiseGolf**
   - Token-based authentication
   - Extended course details
   - Player handicap tracking

2. **NexGolf**
   - Cookie-based authentication
   - Booking reference support
   - Cart management

3. **TeeTime**
   - API key authentication
   - Rich course information
   - Player grouping support
``` 
</rewritten_file>