# Iberian Weather Service Implementation

## Overview
The `IberianWeatherService` class provides weather data for Spain and its territories using the AEMET (Agencia Estatal de Meteorología) OpenData API. The service handles both mainland Spain and the Canary Islands.

## Key Features
- Finds nearest municipality to given coordinates
- Fetches hourly weather forecasts
- Maps AEMET weather codes to standard weather symbols
- Handles rate limiting and error recovery
- Supports both day and night weather conditions

## Implementation Details

### Municipality Lookup
1. Fetches complete municipality list from AEMET
2. Uses Haversine formula to find nearest municipality to given coordinates
3. Extracts numeric ID from municipality URL
4. Formats ID with leading zeros (5 digits required)

### Forecast Data Processing
1. Fetches hourly forecast data for municipality
2. Processes each day's data:
   - Base data from temperature array
   - Matches other parameters by hour
   - Converts units (e.g., km/h to m/s for wind)
   - Maps weather codes to symbols

### Weather Code Mapping
- Handles day/night variations (6:00-20:00 = day)
- Maps AEMET numeric codes to standard symbols
- Includes special handling for:
  - Clear conditions (11-17)
  - Rain (23-26)
  - Snow (33-36)
  - Mixed precipitation (43-46)
  - Thunderstorms (51-74)

### Wind Direction Handling
- Converts cardinal directions to degrees
- Full 16-point compass support
- Returns None for invalid/missing directions

## Error Handling
1. API Errors:
   - Rate limiting (429)
   - Not found (404)
   - Invalid responses
2. Data Validation:
   - Municipality data format
   - Forecast data structure
   - Numeric conversions
3. Recovery:
   - Empty list for missing forecasts
   - Default values for missing data
   - Fallback weather codes

## Rate Limiting
- Minimum 1 second between requests
- Tracks last API call time
- Sleeps if needed to respect limits

## Data Flow
```
Coordinates → Find Municipality → Get Forecast URL → Get Forecast Data → Parse Hourly Data → Weather Objects
```

## Configuration
Required in `config.yaml`:
```yaml
api_keys:
  weather:
    aemet: "your-api-key"
```

## Usage Example
```python
service = IberianWeatherService(local_tz, utc_tz, config)
forecasts = service.get_weather(
    lat=28.0876,
    lon=-16.7408,
    start_time=datetime(...),
    end_time=datetime(...)
)
```

## Logging
- Detailed debug logging at each step
- Warning logs for recoverable issues
- Error logs for API failures
- Context logging for troubleshooting

## Future Improvements
1. Cache municipality list
2. Implement forecast caching
3. Add IPMA support for Portugal
4. Better thunder probability calculation
5. More granular error recovery 