# Golf Club APIs

## Overview

GolfCal2 supports multiple golf club booking systems through a unified interface. Each club type implements a common interface while handling system-specific details internally.

## Golf Club Factory

### Usage

```python
from golfcal2.models.golf_club import GolfClubFactory
from golfcal2.services import AuthService
from golfcal2.config import AppConfig

club = GolfClubFactory.create_club(
    club_details: Dict[str, Any],
    membership: Membership,
    auth_service: AuthService,
    config: AppConfig
)
```

### Supported Club Types

1. **WiseGolf**
   - Modern REST API
   - Token authentication
   - Real-time availability

2. **WiseGolf0**
   - Legacy system
   - Cookie-based auth
   - Basic functionality

3. **NexGolf**
   - Nordic system
   - Query parameters
   - Advanced features

4. **TeeTime**
   - Generic system
   - Multiple auth methods
   - Basic features

## Base Interface

All golf club implementations must implement the following interface:

```python
class GolfClub(ABC):
    @abstractmethod
    def fetch_reservations(
        self,
        membership: Membership
    ) -> List[Dict[str, Any]]:
        """
        Fetch reservations for membership.
        
        Args:
            membership: User's membership details
            
        Returns:
            List of raw reservation data
            
        Raises:
            APIError: If fetching fails
        """
        pass
```

## WiseGolf Implementation

### Initialization

```python
class WiseGolfClub(GolfClub):
    def __init__(
        self,
        club_details: Dict[str, Any],
        membership: Membership,
        auth_service: AuthService,
        config: AppConfig
    ):
        self.base_url = club_details['api']['base_url']
        self.endpoints = club_details['api']['endpoints']
        self.auth_service = auth_service
```

### API Methods

#### fetch_reservations

```python
def fetch_reservations(
    self,
    membership: Membership
) -> List[Dict[str, Any]]:
    """
    Fetch reservations from WiseGolf API.
    
    Args:
        membership: User's membership details
        
    Returns:
        List of reservation data in WiseGolf format
        
    Raises:
        APIError: If API request fails
        APITimeoutError: If request times out
        APIRateLimitError: If rate limit exceeded
    """
```

### Authentication

```python
def _get_auth_headers(
    self,
    membership: Membership
) -> Dict[str, str]:
    """
    Get authentication headers.
    
    Args:
        membership: User's membership details
        
    Returns:
        Dictionary of headers including auth token
    """
```

## NexGolf Implementation

### Initialization

```python
class NexGolfClub(GolfClub):
    def __init__(
        self,
        club_details: Dict[str, Any],
        membership: Membership,
        auth_service: AuthService,
        config: AppConfig
    ):
        self.base_url = club_details['api']['base_url']
        self.club_id = club_details['club_id']
```

### API Methods

#### fetch_reservations

```python
def fetch_reservations(
    self,
    membership: Membership
) -> List[Dict[str, Any]]:
    """
    Fetch reservations from NexGolf API.
    
    Args:
        membership: User's membership details
        
    Returns:
        List of reservation data in NexGolf format
        
    Raises:
        APIError: If API request fails
        APITimeoutError: If request times out
    """
```

### Authentication

```python
def _build_auth_url(
    self,
    membership: Membership,
    endpoint: str
) -> str:
    """
    Build authenticated URL.
    
    Args:
        membership: User's membership details
        endpoint: API endpoint
        
    Returns:
        Full URL with auth parameters
    """
```

## Response Formats

### WiseGolf Format

```python
{
    'dateTimeStart': '2024-01-20 10:00:00',
    'dateTimeEnd': '2024-01-20 14:00:00',
    'resourceId': '123',
    'players': [
        {
            'name': 'Player Name',
            'memberId': '456'
        }
    ],
    'status': 'confirmed'
}
```

### NexGolf Format

```python
{
    'startTime': '2024-01-20T10:00:00+02:00',
    'duration': 240,
    'course': 'Main Course',
    'players': [
        {
            'playerName': 'Player Name',
            'membershipId': '456'
        }
    ]
}
```

## Error Handling

### Common Errors

```python
class APIError(Exception):
    """Base class for API errors."""
    pass

class APITimeoutError(APIError):
    """Request timed out."""
    pass

class APIRateLimitError(APIError):
    """Rate limit exceeded."""
    pass

class APIResponseError(APIError):
    """Invalid response from API."""
    pass
```

### Error Handling Example

```python
try:
    reservations = club.fetch_reservations(membership)
except APITimeoutError:
    # Handle timeout
    logger.error("Request timed out")
    retry_with_backoff()
except APIRateLimitError:
    # Handle rate limit
    logger.warning("Rate limit exceeded")
    wait_and_retry()
except APIError as e:
    # Handle other errors
    logger.error(f"API error: {str(e)}")
    raise
```

## Usage Examples

### WiseGolf Example

```python
# Initialize club
club_details = config.clubs['wisegolf_club']
membership = user.memberships[0]
club = GolfClubFactory.create_club(club_details, membership, auth_service, config)

# Fetch reservations
try:
    reservations = club.fetch_reservations(membership)
    for reservation in reservations:
        process_reservation(reservation)
except APIError as e:
    handle_error(e)
```

### NexGolf Example

```python
# Initialize club
club_details = config.clubs['nexgolf_club']
membership = user.memberships[0]
club = GolfClubFactory.create_club(club_details, membership, auth_service, config)

# Fetch reservations with date range
try:
    reservations = club.fetch_reservations(
        membership,
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=30)
    )
    process_reservations(reservations)
except APIError as e:
    handle_error(e)
``` 