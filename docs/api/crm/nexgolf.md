# NexGolf API Documentation

This document describes the NexGolf API as implemented in the golf calendar application.

## Overview

NexGolf is a golf course management system used by Nordic golf clubs. The implementation supports two variants:
- NexGolf: Traditional system
- TeeTime: Modern variant with slightly different URL structures

## Authentication

The implementation supports multiple authentication strategies based on club configuration:

1. Cookie Authentication (`cookie`)
   ```python
   headers = {
       "Cookie": f"{cookie_name}={cookie_value}",
       "Accept-Encoding": "gzip, deflate, br"
   }
   ```

2. Query Authentication (`query`)
   - Appends authentication parameters to URL

3. Token App Authentication (`token_appauth`)
   ```python
   headers = {
       "Authorization": f"token {token}",
       "x-session-type": "wisegolf"
   }
   ```

## API Endpoints

### Reservations

**Endpoint**: Determined by club configuration (`clubs_details[club_key]`)
**Method**: GET
**Parameters**:
- `from`: Current date in YYYY-MM-DD format

The URL structure varies between NexGolf and TeeTime:
```python
# NexGolf
full_url = f"{base_url}?from={today}"
# TeeTime
full_url = f"{base_url}&from={today}"
```

### Club Details

**Endpoint**: `https://www.teetime.fi/backend/club/{club_id}`
**Method**: GET
**Parameters**:
- `token`: Authentication token

Used to fetch club address information.

## Data Structures

### Reservation Response

Based on the implementation, the API returns reservations with this structure:

```json
{
    "startTime": "HH:MM YYYY-MM-DD",
    "course": {
        "club": {
            "abbreviation": "string",
            "name": "string",
            "number": "string"
        }
    },
    "reservations": [
        {
            "player": {
                "firstName": "string",
                "lastName": "string",
                "handicap": float,
                "club": {
                    "abbreviation": "string"
                }
            }
        }
    ]
}
```

### Club Response

The club details endpoint returns at minimum:
```json
{
    "address": "string"
}
```

## Implementation Examples

### Fetching Reservations

```python
def fetch_nexgolf_reservations(membership, clubs_details):
    club_key = membership['club']
    auth_strategy = get_authentication_strategy(clubs_details[club_key]['auth_type'])
    headers = auth_strategy.create_headers(
        clubs_details[club_key]['cookie_name'], 
        membership['auth_details']
    )
    
    full_url = auth_strategy.build_full_url(clubs_details[club_key], membership)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if clubs_details[club_key]['crm'] == 'nexgolf':
        full_url = f"{full_url}?from={today}"
    else:
        full_url = f"{full_url}&from={today}"
        
    return make_api_request("GET", full_url, headers)
```

### Processing Player Details

```python
def fetch_nexgolf_player_details(reservation):
    player_details = []
    total_handicap = 0.0

    for player_info in reservation.get('reservations', []):
        player = player_info.get('player', {})
        handicap = player.get('handicap', 0.0)
        
        player_details.append({
            "name": f"{player.get('firstName', 'N/A')} {player.get('lastName', 'N/A')}",
            "clubAbbreviation": player.get('club', {}).get('abbreviation', 'N/A'),
            "handicap": handicap
        })
        
        total_handicap += float(handicap)

    return player_details, round(total_handicap, 1)
```

## Error Handling

The implementation handles:
- HTTP errors through requests.exceptions.HTTPError
- Timeout errors (connection and read timeouts)
- JSON decode errors
- Missing or invalid data in responses

Errors are logged using Python's logging system with these levels:
- ERROR: For request failures and API errors
- WARNING: For data validation issues
- DEBUG: For request/response details

## Request Configuration

Based on the implementation:
- Connection timeout: 7 seconds
- Read timeout: 20 seconds

## Notes

1. The implementation handles both NexGolf and TeeTime variants with different URL structures
2. All dates and times are handled in Europe/Helsinki timezone and converted to UTC for storage
3. Player details are extracted from reservation responses
4. The implementation includes validation of API response structures
5. Error handling includes graceful fallbacks for missing data 