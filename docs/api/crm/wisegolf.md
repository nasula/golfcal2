# WiseGolf API

## Overview

WiseGolf is a modern golf club management system that provides a REST API for accessing reservations and player data. This document covers both the modern WiseGolf and legacy WiseGolf0 implementations.

## Authentication

### Modern WiseGolf (JWT)

```http
POST /auth/login
Content-Type: application/json
Accept: application/json, text/plain, */*

{
    "username": "your-username",
    "password": "your-password"
}
```

Response:
```json
{
    "token": "jwt-token",
    "expires_in": 3600
}
```

After authentication, all requests must include:
```http
Authorization: Bearer <jwt-token>
Accept: application/json, text/plain, */*
```

### Legacy WiseGolf0 (Cookie)

Uses cookie-based authentication with session tokens:
```http
Cookie: wisenetwork_session=<session_token>
Accept: application/json, text/plain, */*
Accept-Language: en-US,en;q=0.9
```

## Endpoints

### 1. Get User Reservations

#### Modern WiseGolf
```http
GET /reservations/my
Authorization: Bearer <token>
```

Response:
```json
{
    "reservations": [
        {
            "teeTime": "2025-01-05T11:00:00.000Z",
            "players": [
                {
                    "firstName": "John",
                    "lastName": "Doe",
                    "handicap": 15.4,
                    "homeClub": {
                        "name": "Golf Club",
                        "abbreviation": "GC"
                    }
                }
            ],
            "course": {
                "name": "Main Course",
                "holes": 18,
                "par": 72
            }
        }
    ]
}
```

#### Legacy WiseGolf0
```http
GET /pd/simulaattorit/{product_id}/simulaattorit/?controller=ajax&reservations=getusergolfreservations
Cookie: wisenetwork_session=<session_token>
```

Response:
```json
{
    "success": true,
    "rows": [
        {
            "reservationTimeId": 91588,
            "reservationId": 4,
            "dateTimeStart": "2025-01-05 11:00:00",
            "dateTimeEnd": "2025-01-05 13:00:00",
            "resourceId": 1,
            "firstName": "John",
            "familyName": "Doe",
            "handicapActive": "15.40",
            "productName": "Simulators"
        }
    ]
}
```

### 2. Get Flight Players (WiseGolf0)

```http
GET /api/1.0/reservations/?productid={product_id}&date={date}&golf=1
Cookie: wisenetwork_session=<session_token>
```

Response:
```json
{
    "success": true,
    "errors": [],
    "reservationsGolfPlayers": [
        {
            "firstName": "John",
            "familyName": "Doe",
            "handicapActive": 15.4,
            "clubName": "Golf Club",
            "clubAbbreviation": "GC",
            "status": "active",
            "namePublic": 1
        }
    ]
}
```

## Implementation Details

### Modern WiseGolf

```python
class WiseGolfImplementation(BaseCRMImplementation):
    """WiseGolf CRM implementation"""
    
    def authenticate(self) -> None:
        self.session = requests.Session()
        
        auth_response = self._make_request(
            'POST',
            '/auth/login',
            json={
                'username': self.auth_details['username'],
                'password': self.auth_details['password']
            }
        )
        
        token = auth_response.json().get('token')
        if not token:
            raise APIAuthError("No token in authentication response")
            
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        response = self._make_request('GET', '/reservations/my')
        return response.json()['reservations']
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["teeTime"], 
                fmt="%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            players=self._parse_players(raw_reservation),
            course_info=self._parse_course_info(raw_reservation)
        )
```

## Error Handling

### Authentication Errors
```json
{
    "success": false,
    "error": "authentication_failed",
    "message": "Invalid credentials"
}
```

### Rate Limiting
```json
{
    "success": false,
    "error": "too_many_requests",
    "message": "Rate limit exceeded",
    "retry_after": 60
}
```

## Implementation Notes

### Modern WiseGolf
- JWT-based authentication
- Token expires after 1 hour
- Rate limit: 60 requests/minute
- Timezone: UTC in responses (ISO 8601 format)
- Real-time availability
- Extended course details

### Legacy WiseGolf0
- Cookie-based authentication
- Session-based auth
- Basic functionality
- Local timezone in responses
- Flight grouping support (1-4 players per flight)

## Data Formats

### Date/Time
- Modern WiseGolf: ISO 8601 with timezone (UTC)
  - Format: "%Y-%m-%dT%H:%M:%S.%fZ"
  - Example: "2025-01-05T11:00:00.000Z"
- Legacy WiseGolf0: Local timezone without offset
  - Format: "%Y-%m-%d %H:%M:%S"
  - Example: "2025-01-05 11:00:00"

### Handicap
- Modern WiseGolf: Float
  - Example: 15.4
- Legacy WiseGolf0: String (needs conversion)
  - Example: "15.40"

### Player Information
Both versions provide:
- First name
- Last name
- Handicap
- Home club (abbreviation)

### Course Information
Common fields:
- Name
- Resource ID

Additional fields:
- Modern WiseGolf: holes, par
- Legacy WiseGolf0: variant name, product name
``` 