# IPMA Weather Service

## Overview

The IPMA (Instituto Português do Mar e da Atmosfera) weather service provides official weather forecasts for Portugal through their OpenData API. The service covers mainland Portugal and its islands, offering location-based forecasts.

## Coverage

- **Geographic Area**: Portugal (36.5°N to 42.5°N, -9.5°E to -7.5°E)
- **Forecast Range**: Up to 5 days
- **Update Frequency**: Twice daily (10:00 and 20:00 UTC)
- **Resolution**: City/location-based forecasts

## Features

- Official Portuguese weather service
- No API key required
- Location-based forecasts using nearest city
- Automatic data format conversion
- 1-second rate limiting
- Caching support with 2-hour expiry
- Comprehensive error handling

## Implementation

### Configuration

```python
class PortugueseWeatherService(WeatherService):
    """Service for handling weather data for Portugal using IPMA API."""
    
    BASE_URL = "https://api.ipma.pt/open-data"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal"
    
    def __init__(self, local_tz, utc_tz, config):
        super().__init__(local_tz, utc_tz)
        self.endpoint = self.BASE_URL
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': self.USER_AGENT
        }
        self.db = WeatherDatabase('portuguese_weather', PORTUGUESE_SCHEMA)
        self.location_cache = WeatherLocationCache()
        self._min_call_interval = timedelta(seconds=1)
```

### Location Handling

The service uses the Haversine formula to find the nearest weather station:

```python
def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r
```

### Data Fetching

```python
def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime):
    """Fetch forecasts with location lookup."""
    # Try cached location first
    cached_location = self.location_cache.get_ipma_location(lat, lon)
    
    if not cached_location:
        # Get locations list from API
        locations_url = f"{self.endpoint}/distrits-islands.json"
        response = requests.get(locations_url, headers=self.headers)
        locations = response.json().get('data', [])
        
        # Find nearest location using Haversine distance
        nearest_location = min(
            locations,
            key=lambda x: self._haversine_distance(
                lat, lon,
                float(x['latitude']),
                float(x['longitude'])
            )
        )
        
        # Cache location for future use
        self.location_cache.cache_ipma_location(
            lat=lat,
            lon=lon,
            location_code=nearest_location['globalIdLocal'],
            name=nearest_location['local'],
            loc_lat=float(nearest_location['latitude']),
            loc_lon=float(nearest_location['longitude'])
        )
        location_id = nearest_location['globalIdLocal']
    else:
        location_id = cached_location['code']
    
    # Get forecasts for location
    forecast_url = f"{self.endpoint}/forecast/meteorology/cities/daily/{location_id}.json"
    response = requests.get(forecast_url, headers=self.headers)
    return response.json()
```

### Weather Code Mapping

```python
def _map_ipma_code(self, code: int, hour: int) -> str:
    """Map IPMA weather codes to standard weather codes."""
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

### Block Size Determination

```python
def get_block_size(self, hours_ahead: float) -> int:
    """Get forecast block size based on hours ahead.
    
    IPMA provides:
    - Hourly forecasts for first 24 hours
    - 6-hour blocks for 24-72 hours
    - 12-hour blocks beyond 72 hours
    """
    if hours_ahead <= 24:
        return 1
    elif hours_ahead <= 72:
        return 6
    else:
        return 12
```

## Usage Guidelines

1. **Attribution Requirements**:
   - Must inform webmaster@ipma.pt about usage
   - Cite IPMA as data source
   - Link to IPMA website

2. **Rate Limiting**:
   - Minimum 1 second between API calls
   - Cache responses when possible
   - Use appropriate block sizes
   - Monitor response headers

3. **Error Handling**:
   - Handle location lookup failures
   - Cache failures should fallback to API calls
   - Invalid responses should be logged and reported
   - Handle timezone conversions

4. **Data Processing**:
   - Convert timestamps to UTC
   - Use metric units
   - Map weather codes to standard format
   - Handle day/night variations

## Testing

1. **Unit Tests**:
   - Test weather code mapping
   - Test location distance calculation
   - Test block size determination
   - Test data parsing

2. **Integration Tests**:
   - Test API connectivity
   - Test location lookup
   - Test rate limiting
   - Test caching behavior

3. **Error Tests**:
   - Test location lookup failures
   - Test rate limit handling
   - Test invalid response handling
   - Test timeout handling

## API Documentation

For more information about the IPMA API:
- API Documentation: https://api.ipma.pt
- Terms of Use: https://api.ipma.pt/terms-of-service
- Contact: webmaster@ipma.pt

## Update Schedule

IPMA updates their forecasts twice daily:
1. Morning Update: 10:00 UTC
2. Evening Update: 20:00 UTC

Cache invalidation should be aligned with these update times for optimal data freshness.
