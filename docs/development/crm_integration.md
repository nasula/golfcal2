# CRM Integration Guide

This document describes how to integrate new Customer Relationship Management (CRM) systems with the golf calendar application.

## Overview

The application supports multiple CRM systems through a standardized architecture. Each CRM integration requires implementing:

1. A CRM-specific implementation class that extends `BaseCRMImplementation`
2. Configuration in `clubs.json`

## Core Components

### 1. Data Models

The application uses standardized data models (`api/models/reservation.py`) for consistency:

```python
@dataclass
class Player:
    first_name: str
    family_name: str
    handicap: Optional[float] = None
    club_abbreviation: Optional[str] = None

@dataclass
class CourseInfo:
    name: str
    holes: int = 18
    par: Optional[int] = None
    slope: Optional[float] = None

@dataclass
class Reservation:
    datetime_start: datetime
    players: List[Player]
    course_info: Optional[CourseInfo] = None
    booking_reference: Optional[str] = None
    status: Optional[str] = None
```

### 2. Base CRM Implementation

The `BaseCRMImplementation` (`api/crm/base.py`) provides common functionality:

- HTTP request handling with retries
- Authentication management
- Error handling
- Datetime parsing
- Standard interfaces for data conversion

Required methods to implement:

```python
class YourCRMImplementation(BaseCRMImplementation):
    def authenticate(self) -> None:
        """Implement CRM-specific authentication"""
        pass
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        """Implement raw reservation fetching"""
        pass
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        """Convert CRM format to standard Reservation model"""
        pass
```

## Implementation Steps

1. Create CRM Implementation:
   - Create a new file in `api/crm/` directory (e.g., `new_crm.py`)
   - Extend `BaseCRMImplementation`
   - Implement required methods
   - Add data parsing to match standard models

2. Add Configuration Support:
   - Add new CRM type to `clubs.json`
   - Document required authentication fields

## Example Implementation

Here's a minimal example of a new CRM integration:

```python
# api/crm/new_crm.py
from api.crm.base import BaseCRMImplementation
from api.models.reservation import Reservation, Player, CourseInfo

class NewCRMImplementation(BaseCRMImplementation):
    def authenticate(self) -> None:
        self.session = requests.Session()
        # Implement authentication...
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        response = self._make_request('GET', '/reservations')
        return response.json()['data']
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["startTime"],
                fmt="%Y-%m-%dT%H:%M:%S"
            ),
            players=self._parse_players(raw_reservation),
            course_info=self._parse_course_info(raw_reservation)
        )
    
    def _parse_players(self, raw_reservation: Dict[str, Any]) -> List[Player]:
        return [
            Player(
                first_name=player.get('firstName', ''),
                family_name=player.get('lastName', ''),
                handicap=player.get('handicap'),
                club_abbreviation=player.get('club', '')
            )
            for player in raw_reservation.get('players', [])
        ]
```

## Error Handling

The base implementation provides several error classes:

- `APIError`: Base class for API errors
- `APITimeoutError`: For timeout issues (with automatic retries)
- `APIResponseError`: For invalid responses
- `APIAuthError`: For authentication failures

## Best Practices

1. **Authentication**:
   - Use the base class's `_make_request` method for automatic retry and error handling
   - Store sensitive data in `auth_details`
   - Implement token refresh if needed

2. **Data Parsing**:
   - Use the provided data models
   - Handle missing fields gracefully with `.get()`
   - Convert data types appropriately (e.g., string to datetime)
   - Set sensible defaults for optional fields

3. **Error Handling**:
   - Let the base class handle common errors
   - Raise appropriate error types
   - Add detailed error messages

4. **Testing**:
   - Test authentication flows
   - Verify data parsing with sample responses
   - Test error scenarios
   - Verify datetime handling across timezones

## Existing Implementations

For reference, see these existing implementations:

- WiseGolf: Token-based authentication with course details
- NexGolf: Cookie-based authentication with booking references
- TeeTime: API key authentication with extended course information

Each demonstrates different approaches while maintaining consistent interfaces through the standard data models. 