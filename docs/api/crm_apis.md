# CRM API Documentation

## Overview

GolfCal2 supports multiple golf club booking systems through a unified interface. Each system has its own API implementation while maintaining consistent data structures internally.

## Authentication Strategies

The system supports three main authentication strategies:

### 1. Token App Authentication (token_appauth)
Used by modern WiseGolf implementations.

Headers:
```http
Authorization: <token>
x-session-type: wisegolf
Accept: application/json, text/plain, */*
```

URL format:
```
<base_url>&appauth=<appauth_token>
```

### 2. Cookie Authentication (cookie)
Used by WiseGolf0 (legacy) and NexGolf systems.

WiseGolf0 format:
```http
Cookie: wisenetwork_session=<session_token>
Accept: application/json, text/plain, */*
Accept-Language: en-US,en;q=0.9
```

NexGolf format:
```http
Cookie: NGLOCALE=fi; JSESSIONID=<session_token>
Accept: application/json, text/plain, */*
```

### 3. Query Authentication (query)
Used by some legacy systems.

Headers:
```http
Accept: application/json, text/plain, */*
Content-Type: application/json
```

URL format:
```
<base_url>?token=<token>
```

## WiseGolf APIs

WiseGolf has two versions of their API, referred to as `wisegolf` and `wisegolf0`.

### WiseGolf (Modern)

#### Authentication
```http
POST /auth/login
Content-Type: application/json

{
    "username": "user",
    "password": "pass"
}
```

Response:
```json
{
    "token": "jwt-token",
    "expires_in": 3600
}
```

#### Reservations
```http
GET /reservations/my
Authorization: Bearer <token>
```

Response:
```json
{
    "reservations": [
        {
            "teeTime": "2024-01-01T10:00:00.000Z",
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

### WiseGolf0 (Legacy)

#### Authentication
Uses cookie-based authentication with session tokens.

#### User Reservations
```http
GET /pd/simulaattorit/18/simulaattorit/?controller=ajax&reservations=getusergolfreservations
Cookie: wisenetwork_session=<session-token>
```

Response:
```json
{
    "success": true,
    "rows": [
        {
            "reservationTimeId": 91588,
            "dateTimeStart": "2025-01-05 11:00:00",
            "dateTimeEnd": "2025-01-05 13:00:00",
            "resourceId": 1,
            "firstName": "John",
            "familyName": "Doe",
            "clubAbbreviation": "GC",
            "handicapActive": "15.40",
            "productName": "Simulators",
            "variantName": "Simulator 1: Sunday 05.01.2025 11:00 - John Doe"
        }
    ],
    "reservationsAdditionalResources": []
}
```

#### Flight Players
```http
GET /api/1.0/reservations/?productid=18&date=2025-01-03&golf=1
Cookie: wisenetwork_session=<session-token>
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

## NexGolf API

### Authentication
```http
POST /api/login
Content-Type: application/x-www-form-urlencoded

memberNumber=12345&pin=1234
```

Response: Session cookie in headers

### Reservations
```http
GET /api/reservations
Cookie: session=<cookie>
Query Parameters:
  - startDate: YYYY-MM-DD
  - endDate: YYYY-MM-DD
```

Response:
```json
{
    "bookings": [
        {
            "startDateTime": "2024-01-01 10:00",
            "bookingReference": "ABC123",
            "status": "confirmed",
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
            ]
        }
    ]
}
```

## TeeTime API

### Authentication
Headers required for all requests:
```http
X-API-Key: <api_key>
X-Club-ID: <club_id>
```

### Reservations
```http
GET /api/bookings
Query Parameters:
  - member_id: string
```

Response:
```json
{
    "data": [
        {
            "startTime": "2024-01-01 10:00:00",
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

## Error Handling

All APIs use standard HTTP status codes with additional details in response body:

### Authentication Errors (401)
```json
{
    "error": "authentication_failed",
    "message": "Invalid credentials"
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
    "message": "Human readable message"
}
```

## Implementation Notes

### WiseGolf (Modern)
- JWT-based authentication
- Token expires after 1 hour
- Rate limit: 60 requests/minute
- Timezone: UTC in responses
- Real-time availability
- Extended course details

### WiseGolf0 (Legacy)
- Cookie-based authentication
- Session-based auth
- Basic functionality
- Local timezone in responses
- Flight grouping support (1-4 players per flight)

### NexGolf
- Cookie-based session
- Session expires after 24 hours
- Rate limit: 30 requests/minute
- Timezone: Local club timezone in responses
- Booking reference support
- Cart management

### TeeTime
- API key authentication
- No token expiration
- Rate limit: 100 requests/minute
- Timezone: Local club timezone in responses
- Rich course information
- Player grouping support

## Common Patterns

### Date Formats
- WiseGolf: ISO 8601 with timezone (UTC)
- WiseGolf0: "YYYY-MM-DD HH:MM:SS" (local)
- NexGolf: "YYYY-MM-DD HH:MM" (local)
- TeeTime: "YYYY-MM-DD HH:MM:SS" (local)

### Handicap Formats
- WiseGolf: Float
- WiseGolf0: String (needs conversion)
- NexGolf: String (needs conversion)
- TeeTime: Float

### Player Information
All APIs provide:
- First name
- Last name
- Handicap
- Home club

### Course Information
Common fields:
- Name
- Number of holes

Additional fields vary:
- WiseGolf: par
- WiseGolf0: variant name
- NexGolf: booking reference
- TeeTime: slope rating