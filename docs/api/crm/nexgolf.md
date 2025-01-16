# NexGolf API

## Overview

NexGolf is a Nordic golf club management system that provides a comprehensive API for accessing reservations and player data. It uses cookie-based authentication and provides detailed booking information.

## Authentication

```http
POST /api/login
Content-Type: application/x-www-form-urlencoded

memberNumber=<member_id>&pin=<pin>
```

After successful authentication, the server returns session cookies that must be included in subsequent requests:
```http
Cookie: NGLOCALE=fi; JSESSIONID=<session_token>
Accept: application/json, text/plain, */*
```

## Endpoints

### Get Reservations

```http
GET /api/reservations
Cookie: JSESSIONID=<session_token>
```

Parameters:
- `startDate`: Start date in YYYY-MM-DD format (defaults to current date)
- `endDate`: End date in YYYY-MM-DD format (defaults to one year from start)

Response:
```json
{
    "bookings": [
        {
            "startDateTime": "2024-01-01 10:00",
            "players": [
                {
                    "firstName": "John",
                    "lastName": "Doe",
                    "handicap": "15.4",
                    "club": {
                        "name": "Golf Club",
                        "code": "GC"
                    }
                }
            ],
            "bookingReference": "ABC123",
            "status": "confirmed"
        }
    ]
}
```

## Implementation Details

```python
class NexGolfImplementation(BaseCRMImplementation):
    """NexGolf CRM implementation"""
    
    def authenticate(self) -> None:
        self.session = requests.Session()
        
        auth_response = self._make_request(
            'POST',
            '/api/login',
            data={
                'memberNumber': self.auth_details['member_id'],
                'pin': self.auth_details['pin']
            }
        )
        
        cookies = auth_response.cookies
        if not cookies:
            raise APIAuthError("No session cookies in authentication response")
            
        self.session.cookies.update(cookies)
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        end_date = datetime.now().replace(year=datetime.now().year + 1)
        
        response = self._make_request(
            'GET',
            '/api/reservations',
            params={
                'startDate': datetime.now().strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d')
            }
        )
        return response.json()['bookings']
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["startDateTime"], 
                fmt="%Y-%m-%d %H:%M"
            ),
            players=self._parse_players(raw_reservation),
            booking_reference=raw_reservation.get("bookingReference"),
            status=raw_reservation.get("status")
        )
    
    def _parse_players(self, raw_reservation: Dict[str, Any]) -> List[Player]:
        return [
            Player(
                first_name=player.get('firstName', ''),
                family_name=player.get('lastName', ''),
                handicap=float(player.get('handicap', 0)),
                club_abbreviation=player.get('club', {}).get('code', '')
            )
            for player in raw_reservation.get('players', [])
        ]
```

## Error Handling

### Authentication Errors (401)
```json
{
    "error": "authentication_failed",
    "message": "Invalid member number or PIN"
}
```

### Rate Limiting (429)
```json
{
    "error": "too_many_requests",
    "message": "Rate limit exceeded",
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

- Cookie-based session authentication
- Session expires after 24 hours
- Rate limit: 30 requests/minute
- Timezone: Local club timezone in responses
- Booking reference support
- Player grouping support (1-4 players per flight)

## Data Formats

### Date/Time
- Format: "%Y-%m-%d %H:%M"
- Timezone: Local club timezone
- Example: "2024-01-01 10:00"

### Handicap
- Format: String in API response, converted to float in implementation
- Example API: "15.4"
- Example parsed: 15.4
- Range: 0.0 to 54.0
- Default: 0.0 if not provided

### Player Information
Required fields:
- First name (`firstName`)
- Last name (`lastName`)
- Handicap (`handicap`)
- Club (name and code)

Optional fields:
- Member number
- Status

### Booking Information
Required fields:
- Start date/time (`startDateTime`)
- Players array
- Booking reference (`bookingReference`)
- Status (`status`)

## Data Model

### Reservation
```python
@dataclass
class Reservation:
    datetime_start: datetime
    players: List[Player]
    booking_reference: Optional[str] = None
    status: Optional[str] = None
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