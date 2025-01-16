# TeeTime API

## Overview

TeeTime is a generic golf club management system that provides a simple API for accessing reservations and player data. It uses API key authentication and provides rich course information.

## Authentication

TeeTime uses API key authentication. All requests must include the following headers:
```http
X-API-Key: <api_key>
X-Club-ID: <club_id>
Accept: application/json, text/plain, */*
```

Verify credentials:
```http
GET /api/verify
X-API-Key: <api_key>
X-Club-ID: <club_id>
```

Response:
```json
{
    "status": "ok",
    "message": "Credentials verified"
}
```

## Endpoints

### Get Reservations

```http
GET /api/bookings
X-API-Key: <api_key>
X-Club-ID: <club_id>
```

Parameters:
- `member_id`: Member ID to fetch reservations for

Response:
```json
{
    "data": [
        {
            "teeTime": "2024-01-01 10:00:00",
            "playerList": [
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
                "name": "Main Course",
                "holes": 18,
                "slope": 125
            }
        }
    ]
}
```

## Implementation Details

```python
class TeeTimeImplementation(BaseCRMImplementation):
    """TeeTime CRM implementation"""
    
    def authenticate(self) -> None:
        self.session = requests.Session()
        
        # TeeTime uses API key authentication
        self.session.headers.update({
            'X-API-Key': self.auth_details['api_key'],
            'X-Club-ID': self.auth_details['club_id']
        })
        
        # Verify credentials
        test_response = self._make_request('GET', '/api/verify')
        if not test_response.ok:
            raise APIAuthError("Invalid API credentials")
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        response = self._make_request(
            'GET',
            '/api/bookings',
            params={'member_id': self.auth_details['member_id']}
        )
        return response.json()['data']
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["teeTime"], 
                fmt="%Y-%m-%d %H:%M:%S"
            ),
            players=self._parse_players(raw_reservation),
            course_info=self._parse_course_details(raw_reservation)
        )
    
    def _parse_players(self, raw_reservation: Dict[str, Any]) -> List[Player]:
        return [
            Player(
                first_name=player.get('name', {}).get('first', ''),
                family_name=player.get('name', {}).get('last', ''),
                handicap=player.get('handicapIndex'),
                club_abbreviation=player.get('memberClub', {}).get('shortCode', '')
            )
            for player in raw_reservation.get('playerList', [])
        ]
    
    def _parse_course_details(self, raw_reservation: Dict[str, Any]) -> CourseInfo:
        course = raw_reservation.get('course', {})
        return CourseInfo(
            name=course.get('name'),
            holes=course.get('holes'),
            slope=course.get('slope')
        )
```

## Error Handling

### Authentication Errors (401)
```json
{
    "error": "invalid_credentials",
    "message": "Invalid API key or club ID"
}
```

### Rate Limiting (429)
```json
{
    "error": "rate_limit_exceeded",
    "message": "Too many requests",
    "retry_after": 60
}
```

### General Errors (400, 500)
```json
{
    "error": "error_code",
    "message": "Human readable message",
    "details": {
        "field": "error description"
    }
}
```

## Implementation Notes

- API key authentication
- No token expiration
- Rate limit: 100 requests/minute
- Timezone: Local club timezone in responses
- Rich course information
- Player grouping support

## Data Formats

### Date/Time
- Format: "%Y-%m-%d %H:%M:%S"
- Timezone: Local club timezone
- Example: "2024-01-01 10:00:00"

### Handicap
- Format: Float
- Field name: `handicapIndex`
- Example: 15.4
- Range: 0.0 to 54.0

### Player Information
Required fields:
- Name object:
  - First name (`name.first`)
  - Last name (`name.last`)
- Handicap (`handicapIndex`)
- Club object:
  - Name (`memberClub.name`)
  - Code (`memberClub.shortCode`)

### Course Information
Required fields:
- Name (`name`)
- Number of holes (`holes`)
- Slope rating (`slope`)

## Data Model

### Reservation
```python
@dataclass
class Reservation:
    datetime_start: datetime
    players: List[Player]
    course_info: Optional[CourseInfo] = None
```

### Player
```python
@dataclass
class Player:
    first_name: str
    family_name: str
    handicap: Optional[float] = None
    club_abbreviation: Optional[str] = None
```

### CourseInfo
```python
@dataclass
class CourseInfo:
    name: str
    holes: int = 18
    slope: Optional[int] = None
``` 