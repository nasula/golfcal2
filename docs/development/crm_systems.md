# Supported CRM Systems

## WiseGolf Systems

WiseGolf has two versions of their API that we support:

### WiseGolf (Version 1)

#### Authentication
- Uses JWT token-based authentication
- Requires username and password
- Token provided in Authorization header
- Example: `Authorization: Bearer <token>`

#### Reservation Data Format
```python
{
    "teeTime": "2024-01-01T10:00:00.000Z",  # UTC timezone
    "players": [
        {
            "firstName": "John",
            "lastName": "Doe",
            "handicap": 15.4,
            "homeClub": {
                "name": "Helsinki Golf Club",
                "abbreviation": "HGK"
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

### WiseGolf0 (Legacy Version)

#### Authentication
- Uses session-based authentication
- Headers include specific browser-like settings
- Requires specific session cookies

#### Reservation Data Format
```python
{
    "dateTimeStart": "2025-01-05 11:00:00",
    "dateTimeEnd": "2025-01-05 13:00:00",
    "firstName": "John",
    "familyName": "Doe",
    "clubAbbreviation": "VGC",
    "handicapActive": "29.90",
    "productName": "Simulaattorit",
    "variantName": "Simulaattori 1"
}
```

#### Special Features
- Separate endpoint for fetching flight players
- Maximum 4 players per flight
- Supports multiple reservations per flight

## NexGolf

### Authentication
- Cookie-based session authentication
- Uses member number and PIN code
- Example:
```python
auth_data = {
    'memberNumber': self.auth_details['member_id'],
    'pin': self.auth_details['pin']
}
```

### Reservation Data Format
```python
{
    "startDateTime": "2024-01-01 10:00",  # Local club timezone
    "bookingReference": "ABC123",
    "status": "confirmed",
    "players": [
        {
            "firstName": "John",
            "lastName": "Doe",
            "handicap": "15.4",  # Note: Comes as string
            "club": {
                "name": "Oslo Golfklubb",
                "code": "OGK"
            }
        }
    ]
}
```

### Implementation Notes
- Fetches reservations for one year ahead
- Converts handicap strings to float
- Uses local club timezone

## TeeTime

### Authentication
- API key based authentication
- Requires club ID
- Headers:
```python
headers = {
    'X-API-Key': auth_details['api_key'],
    'X-Club-ID': auth_details['club_id']
}
```

### Reservation Data Format
```python
{
    "teeTime": "2024-01-01 10:00:00",
    "playerList": [  # Note different field name
        {
            "name": {
                "first": "John",
                "last": "Doe"
            },
            "handicapIndex": 15.4,
            "memberClub": {
                "name": "Golf Club",
                "shortCode": "GC"
            }
        }
    ],
    "course": {
        "name": "Stadium Course",
        "holes": 18,
        "slope": 125
    }
}
```

## Common Integration Points

### Factory Creation
All golf clubs are created through `GolfClubFactory`:
```python
club = GolfClubFactory.create_club(
    club_details=club_config,
    membership=user_membership,
    auth_service=auth_service
)
```

### Configuration in clubs.json
```json
{
    "My Club": {
        "type": "wisegolf",  // or "wisegolf0", "nexgolf", "teetime"
        "name": "My Golf Club",
        "url": "https://api.example.com",
        "timezone": "Europe/Helsinki",
        "variant": "Main Course"  // Optional
    }
}
```

### Error Handling
All implementations use standard error classes:
- `APIError`: Base error class
- `APITimeoutError`: For timeouts
- `APIResponseError`: For invalid responses
- `APIAuthError`: For authentication failures 