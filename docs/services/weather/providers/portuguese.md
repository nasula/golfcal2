# Portuguese Weather Service (IPMA) API

## Overview

The Portuguese Weather Service uses IPMA's (Instituto Português do Mar e da Atmosfera) API to provide weather forecasts for Portugal. It handles both mainland Portugal and the islands, with city-based forecasts.

## API Details

- **Base URL**: `https://api.ipma.pt/open-data/`
- **Documentation**: [IPMA API Documentation](https://api.ipma.pt)
- **Authentication**: None required
- **Rate Limit**: None specified (use 1 request/second as courtesy)
- **Update Frequency**: Twice daily (10:00 and 20:00 UTC)
- **Geographic Coverage**: Portugal (36.5°N to 42.5°N, -9.5°E to -7.5°E)

## Implementation

```python
class PortugueseWeatherService(WeatherService):
    BASE_URL = "https://api.ipma.pt/open-data/"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        super().__init__(local_tz, utc_tz)
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': self.USER_AGENT
        }
        self.db = WeatherDatabase('portuguese_weather', PORTUGUESE_SCHEMA)
```

## Request Flow

### 1. Location Lookup

```python
def _get_location(self, lat: float, lon: float) -> str:
    # Try cache first
    cached = self.location_cache.get_ipma_location(lat, lon)
    if cached:
        return cached['code']
        
    # Fetch from API if not cached
    url = f"{self.BASE_URL}/distrits-islands.json"
    response = requests.get(url, headers=self.headers)
    locations = response.json()
    
    # Find nearest location
    nearest = min(
        locations,
        key=lambda l: self._haversine_distance(
            lat, lon,
            float(l['latitude']),
            float(l['longitude'])
        )
    )
    
    # Cache for future use
    self.location_cache.cache_ipma_location(
        lat=lat,
        lon=lon,
        location_code=nearest['globalIdLocal'],
        name=nearest['local']
    )
    
    return nearest['globalIdLocal']
```

### 2. Forecast Retrieval

```python
def _get_forecast(self, location_code: str) -> Dict:
    url = f"{self.BASE_URL}/forecast/meteorology/cities/daily/{location_code}.json"
    response = requests.get(url, headers=self.headers)
    return response.json()
```

## Response Format

```json
{
    "owner": "IPMA",
    "country": "PT",
    "data": [
        {
            "precipitaProb": 74.0,
            "tMin": -3.1,
            "tMax": 12.8,
            "predWindDir": "N",
            "idWeatherType": 6,
            "classWindSpeed": 2,
            "longitude": "-9.1333",
            "forecastDate": "2024-01-09",
            "latitude": "38.7167",
            "precipitaMax": 0.7,
            "idRegiao": "1110600",
            "globalIdLocal": 1110600,
            "dataUpdate": "2024-01-09T10:00:00",
            "humidity": {
                "min": 45,
                "max": 85
            },
            "windSpeed": {
                "min": 15,
                "max": 25
            }
        }
    ]
}
```

## Weather Data Mapping

### Weather Type Codes

IPMA uses numeric weather type codes:

```python
def _map_ipma_code(self, code: int, hour: int) -> str:
    is_day = 6 <= hour <= 18
    
    code_map = {
        1: 'clearsky_day' if is_day else 'clearsky_night',
        2: 'fair_day' if is_day else 'fair_night',
        3: 'partlycloudy_day' if is_day else 'partlycloudy_night',
        4: 'cloudy',
        5: 'fog',
        6: 'rain',
        7: 'lightrain',
        8: 'heavyrain',
        9: 'rainandthunder',
        10: 'heavyrainandthunder',
        11: 'lightsnow',
        12: 'snow',
        13: 'heavysnow',
        14: 'lightsleet',
        15: 'heavysleet'
    }
    
    return code_map.get(code, 'cloudy')
```

### Block Sizes

```python
def get_block_size(self, hours_ahead: float) -> int:
    """Get forecast block size based on hours ahead.
    
    IPMA provides:
    - Hourly forecasts for first 24 hours
    - 3-hour blocks for 24-72 hours
    - 6-hour blocks beyond 72 hours
    """
    if hours_ahead <= 24:
        return 1
    elif hours_ahead <= 72:
        return 3
    return 6
```

## Error Handling

### Common Errors

1. **Location Not Found**
   ```python
   if not locations:
       raise WeatherError(
           "No IPMA locations found",
           ErrorCode.INVALID_RESPONSE,
           {"lat": lat, "lon": lon}
       )
   ```

2. **Invalid Response**
   ```python
   if not isinstance(data, dict) or 'data' not in data:
       raise WeatherError(
           "Invalid IPMA response format",
           ErrorCode.INVALID_RESPONSE,
           {"response": data}
       )
   ```

### Rate Limiting

```python
def _handle_rate_limit(self):
    """Courtesy rate limiting of 1 request per second."""
    now = datetime.now()
    if self._last_request_time:
        elapsed = now - self._last_request_time
        if elapsed < timedelta(seconds=1):
            time.sleep(1 - elapsed.total_seconds())
    self._last_request_time = now
```

## Caching Strategy

- Location cache: Persistent storage of IPMA location codes
- Weather cache: 6-hour duration with update schedule alignment
- Cache key format: `{location_code}_{base_time}`

```python
def _get_cache_key(self, location_code: str, base_time: datetime) -> str:
    # Align with IPMA update schedule (10:00 and 20:00 UTC)
    hour = base_time.hour
    aligned_hour = 10 if hour < 20 else 20
    aligned_time = base_time.replace(hour=aligned_hour, minute=0, second=0, microsecond=0)
    return f"{location_code}_{aligned_time.strftime('%Y%m%d%H')}"
```

## Best Practices

1. **Request Optimization**
   - Cache location codes
   - Align with update schedule
   - Use appropriate block sizes
   - Implement courtesy rate limiting

2. **Error Handling**
   - Handle location lookup failures
   - Validate response format
   - Implement request retries
   - Log all API interactions

3. **Data Processing**
   - Convert timestamps to UTC
   - Handle day/night variations
   - Process thunder probability
   - Map weather codes correctly

4. **Integration**
   - Use for Portuguese locations only
   - Fall back to OpenWeather if needed
   - Handle timezone differences
   - Respect IPMA terms of use

## Attribution Requirements

1. **Required Headers**
   - Use appropriate User-Agent
   - Include Accept header

2. **Legal Requirements**
   - Inform webmaster@ipma.pt about usage
   - Cite IPMA as data source
   - Link to IPMA website
   - Follow usage guidelines

## Update Schedule

IPMA updates their forecasts twice daily:
1. Morning Update: 10:00 UTC
2. Evening Update: 20:00 UTC

Cache invalidation should be aligned with these update times for optimal data freshness. 