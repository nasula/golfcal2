# CRM API Documentation

## WiseGolf API

### Authentication
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

### Reservations
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

Verify credentials:
```http
GET /api/verify
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

## Error Responses

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

### WiseGolf
- JWT-based authentication
- Token expires after 1 hour
- Rate limit: 60 requests/minute
- Timezone: UTC in responses

### NexGolf
- Cookie-based session
- Session expires after 24 hours
- Rate limit: 30 requests/minute
- Timezone: Local club timezone in responses

### TeeTime
- API key authentication
- No token expiration
- Rate limit: 100 requests/minute
- Timezone: Local club timezone in responses

## Common Patterns

### Date Formats
- WiseGolf: ISO 8601 with timezone (UTC)
- NexGolf: "YYYY-MM-DD HH:MM" (local)
- TeeTime: "YYYY-MM-DD HH:MM:SS" (local)

### Handicap Formats
- WiseGolf: Float
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
- TeeTime: slope
- NexGolf: none 