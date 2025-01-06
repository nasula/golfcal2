# Supported CRM Systems

## WiseGolf (Finland)

### Overview
WiseGolf is used by many Finnish golf clubs. It provides a REST API with JWT authentication.

### Authentication Flow
1. User provides username and password
2. System obtains JWT token via `/auth/login`
3. Token is used in Authorization header
4. Token expires after 1 hour and needs refresh

### Reservation Data Structure
```python
{
    "teeTime": "2024-01-01T10:00:00.000Z",  # UTC timezone
    "players": [
        {
            "firstName": "John",
            "lastName": "Doe",
            "handicap": 15.4,  # Float
            "homeClub": {
                "name": "Helsinki Golf Club",
                "abbreviation": "HGK"  # Standard Finnish club codes
            }
        }
    ],
    "course": {
        "name": "Master Course",
        "holes": 18,
        "par": 72
    }
}
```

### Known Limitations
- Rate limited to 60 requests/minute
- No bulk reservation fetch
- Token refresh requires full re-authentication

## NexGolf (Sweden, Norway)

### Overview
NexGolf is common in Nordic countries. Uses cookie-based authentication with PIN codes.

### Authentication Flow
1. User provides member number and PIN
2. System posts to `/api/login`
3. Session cookie is stored
4. Session valid for 24 hours

### Reservation Data Structure
```python
{
    "startDateTime": "2024-01-01 10:00",  # Local club timezone
    "bookingReference": "ABC123",
    "status": "confirmed",
    "players": [
        {
            "firstName": "John",
            "lastName": "Doe",
            "handicap": "15.4",  # String, needs conversion
            "club": {
                "name": "Oslo Golfklubb",
                "code": "OGK"  # Nordic club codes
            }
        }
    ]
}
```

### Known Issues
- Session timeouts not properly indicated
- Handicaps come as strings
- Rate limiting varies by club

## TeeTime (Spain, Portugal)

### Overview
TeeTime is used in Southern Europe. Uses API key authentication.

### Authentication Flow
1. Club provides API key and club ID
2. These are included in every request header
3. No token expiration
4. Credentials verified via `/api/verify`

### Reservation Data Structure
```python
{
    "teeTime": "2024-01-01 10:00:00",  # Local timezone
    "playerList": [  # Note different field name
        {
            "name": {  # Nested name structure
                "first": "John",
                "last": "Doe"
            },
            "handicapIndex": 15.4,
            "memberClub": {
                "name": "PGA Catalunya",
                "shortCode": "PGA"
            }
        }
    ],
    "course": {
        "name": "Stadium Course",
        "holes": 18,
        "slope": 125  # Includes slope rating
    }
}
```

### Special Considerations
- Different field names from other systems
- Includes slope ratings
- Nested name structures
- Some clubs require additional headers

## Common Integration Points

### Club Configuration
```json
{
    "Example Club": {
        "type": "wise_golf",  // or "nex_golf", "teetime"
        "name": "Example Golf Club",
        "url": "https://api.example-club.com",
        "timezone": "Europe/Helsinki",
        "auth_type": "token"  // or "cookie", "apikey"
    }
}
```

### Data Mapping
All systems map to our standard `Reservation` model:
```python
@dataclass
class Reservation:
    datetime_start: datetime  # Always converted to UTC
    players: List[Player]
    course_info: Optional[CourseInfo] = None
    booking_reference: Optional[str] = None
    status: Optional[str] = None
```

### Error Handling
Common error patterns across systems:
- Authentication failures (401)
- Rate limiting (429)
- Invalid data format (400)
- Server errors (500)

### Timezone Handling
- WiseGolf: Provides UTC
- NexGolf: Local club time
- TeeTime: Local club time
- All converted to UTC internally 