# MET.no Weather Service

## Overview

The MET.no weather service provides high-resolution weather forecasts for the Nordic region using the Norwegian Meteorological Institute's API. The service is free to use but requires proper attribution and adherence to usage guidelines.

## Coverage

- **Geographic Area**: Nordic region (55°N to 72°N, 3°E to 32°E)
- **Forecast Range**: Up to 10 days
- **Update Frequency**: Every hour
- **Resolution**: 
  - Hourly for first 48 hours
  - 6-hour blocks for 48-168 hours
  - 12-hour blocks beyond 168 hours

## Features

- High-resolution forecasts with altitude support
- No API key required
- 1-second rate limiting
- Caching support with 2-hour expiry
- Automatic data format conversion
- Comprehensive error handling
- Detailed logging with correlation IDs

## Implementation

### Configuration

```python
class MetWeatherService(WeatherService):
    """Service for handling weather data from MET.no API."""
    
    BASE_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz, utc_tz, config):
        super().__init__(local_tz, utc_tz)
        self.endpoint = self.BASE_URL
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': self.USER_AGENT
        }
        self.db = WeatherDatabase('met_weather', MET_SCHEMA)
        self._min_call_interval = timedelta(seconds=1)
```

### Data Fetching

The service supports altitude-based forecasts for more accurate temperature predictions:

```python
def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, altitude: Optional[int] = None):
    """Get weather data with optional altitude support."""
    # Generate cache key
    location = f"{lat},{lon}"
    if altitude:
        location += f",{altitude}"
    
    # Try cache first
    weather_data = self.db.get_weather_data(
        location=location,
        times=times_to_fetch,
        data_type='next_1_hours',
        fields=[
            'air_temperature', 'precipitation_amount', 'wind_speed',
            'wind_from_direction', 'probability_of_precipitation',
            'probability_of_thunder', 'summary_code'
        ]
    )
    
    if not weather_data:
        # Fetch from API if not in cache
        api_data = self._fetch_from_api(lat, lon, altitude)
        weather_data = self._parse_api_data(api_data, start_time, end_time)
```

### API Request Handling

```python
def _fetch_from_api(self, lat: float, lon: float, altitude: Optional[int] = None):
    """Fetch weather data from MET.no API with rate limiting."""
    # Apply rate limiting
    if self._last_api_call:
        elapsed = datetime.now() - self._last_api_call
        if elapsed < self._min_call_interval:
            sleep_time = (self._min_call_interval - elapsed).total_seconds()
            time.sleep(sleep_time)
    
    # Build request
    params = {
        'lat': f"{lat:.4f}",
        'lon': f"{lon:.4f}"
    }
    if altitude is not None:
        params['altitude'] = str(int(altitude))
    
    # Make request with error handling
    try:
        response = requests.get(
            self.endpoint,
            params=params,
            headers=self.headers,
            timeout=10
        )
        self._last_api_call = datetime.now()
        
        if response.status_code == 429:
            raise APIRateLimitError("Rate limit exceeded")
        response.raise_for_status()
        
        return response.json()
    except Exception as e:
        self.error(f"API request failed: {str(e)}")
        return None
```

### Data Parsing

```python
def _parse_api_data(self, data: Dict[str, Any], start_time: datetime, end_time: datetime):
    """Parse API response and prepare for caching."""
    if not data or data.get('type') != 'Feature':
        return None
    
    timeseries = data['properties']['timeseries']
    weather_data = {}
    
    for entry in timeseries:
        time = datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
        if start_time <= time <= end_time:
            instant = entry['data']['instant']['details']
            next_1_hours = entry['data'].get('next_1_hours', {})
            
            weather_data[time.strftime('%Y-%m-%dT%H:%M:%SZ')] = {
                'temperature': instant.get('air_temperature'),
                'precipitation': next_1_hours.get('details', {}).get('precipitation_amount'),
                'wind_speed': instant.get('wind_speed'),
                'wind_direction': instant.get('wind_from_direction'),
                'precipitation_probability': next_1_hours.get('details', {}).get('probability_of_precipitation'),
                'symbol': self._map_symbol_code(next_1_hours.get('summary', {}).get('symbol_code', ''))
            }
    
    return weather_data
```

### Block Size Determination

```python
def get_block_size(self, hours_ahead: float) -> int:
    """Get forecast block size based on hours ahead.
    
    MET.no provides:
    - Hourly forecasts for first 48 hours
    - 6-hour blocks for 48-168 hours
    - 12-hour blocks beyond 168 hours
    """
    if hours_ahead <= 48:
        return 1
    elif hours_ahead <= 168:
        return 6
    else:
        return 12
```

## Usage Guidelines

1. **Attribution**:
   - Must include MET.no attribution in user-facing applications
   - Link to MET.no website when using their data

2. **Rate Limiting**:
   - Minimum 1 second between API calls
   - Cache responses when possible
   - Use appropriate block sizes based on forecast time

3. **Error Handling**:
   - Handle rate limit errors with backoff
   - Cache failures should fallback to API calls
   - Invalid responses should be logged and reported

4. **Data Processing**:
   - Convert timestamps to UTC
   - Use metric units
   - Map weather codes to standard format

## Testing

1. **Unit Tests**:
   - Test weather code mapping
   - Test block size determination
   - Test data parsing

2. **Integration Tests**:
   - Test API connectivity
   - Test rate limiting
   - Test caching behavior

3. **Error Tests**:
   - Test rate limit handling
   - Test invalid response handling
   - Test timeout handling
