# AEMET Weather Service

## Overview

The AEMET (Agencia Estatal de Meteorología) weather service provides official weather forecasts for Spain through their OpenData API. The service covers both mainland Spain and the Canary Islands, offering municipality-based forecasts.

## Coverage

- **Geographic Areas**:
  - Mainland Spain (36.0°N to 44.0°N, -7.5°E to 3.5°E)
  - Canary Islands (27.5°N to 29.5°N, -18.5°E to -13.0°E)
- **Forecast Range**: Up to 7 days
- **Update Frequency**: Multiple times per day
- **Resolution**: Municipality-based forecasts

## Features

- Official Spanish weather service
- Municipality-based forecasts
- API key required
- Location caching
- Automatic municipality selection
- Rate limiting with 1-second intervals
- Caching support with 2-hour expiry

## Implementation

### Configuration

```python
class IberianWeatherService(WeatherService):
    """Service for handling weather data for Iberian region."""

    BASE_URL = "https://opendata.aemet.es/opendata/api"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal"
    
    def __init__(self, local_tz, utc_tz, config):
        super().__init__(local_tz, utc_tz)
        self.api_key = config.global_config['api_keys']['weather']['aemet']
        self.endpoint = self.BASE_URL
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': self.USER_AGENT,
            'api_key': self.api_key
        }
        self.db = WeatherDatabase('iberian_weather', IBERIAN_SCHEMA)
        self.location_cache = WeatherLocationCache()
        self._min_call_interval = timedelta(seconds=1)
```

### Municipality Handling

The service uses a two-step process to find the nearest municipality:

```python
def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime):
    """Fetch forecasts with municipality lookup."""
    # Try cached municipality first
    cached_municipality = self.location_cache.get_municipality(lat, lon)
    
    if not cached_municipality:
        # Get municipality list from API
        municipality_url = f"{self.endpoint}/maestro/municipios"
        response = requests.get(municipality_url, headers=self.headers)
        municipalities = response.json()
        
        # Find nearest municipality
        nearest_municipality = min(
            municipalities,
            key=lambda x: self._haversine_distance(
                lat, lon,
                float(x['latitud_dec']),
                float(x['longitud_dec'])
            )
        )
        
        # Cache for future use
        self.location_cache.cache_municipality(
            lat=lat,
            lon=lon,
            municipality_code=nearest_municipality['id'].zfill(5),
            name=nearest_municipality['nombre'],
            mun_lat=float(nearest_municipality['latitud_dec']),
            mun_lon=float(nearest_municipality['longitud_dec'])
        )
```

### Data Fetching

AEMET's API requires a two-step process for data retrieval:

```python
def _get_forecast_data(self, municipality_code: str):
    """Get forecast data using municipality code."""
    # First request gets the data URL
    forecast_url = f"{self.endpoint}/prediccion/especifica/municipio/horaria/{municipality_code}"
    response = requests.get(forecast_url, headers=self.headers)
    data_info = response.json()
    
    if 'datos' not in data_info:
        raise APIResponseError("Invalid AEMET response format")
    
    # Second request gets the actual forecast data
    data_url = data_info['datos']
    data_response = requests.get(data_url, headers=self.headers)
    return data_response.json()
```

### Weather Code Mapping

```python
def _map_aemet_code(self, code: str, hour: int) -> str:
    """Map AEMET weather codes to standard codes."""
    is_day = 6 <= hour <= 18
    base_code = code.rstrip('n')  # Strip night indicator
    
    code_map = {
        '11': 'clearsky_day' if is_day else 'clearsky_night',
        '12': 'fair_day' if is_day else 'fair_night',
        '13': 'partlycloudy_day' if is_day else 'partlycloudy_night',
        '14': 'cloudy',
        '15': 'lightrain',
        '16': 'rain',
        '17': 'heavyrain',
        '23': 'storm',
        '24': 'heavystorm',
        '43': 'lightsnow',
        '44': 'snow',
        '45': 'heavysnow',
        '71': 'rainandthunder',
        '72': 'rainandthunder',
        '73': 'heavyrainandthunder',
        '74': 'heavyrainandthunder'
    }
    
    return code_map.get(base_code, 'cloudy')
```

### Block Size Determination

```python
def get_block_size(self, hours_ahead: float) -> int:
    """Get forecast block size based on hours ahead.
    
    AEMET provides:
    - Hourly forecasts for first 48 hours
    - 6-hour blocks for 48-120 hours
    - 12-hour blocks beyond 120 hours
    """
    if hours_ahead <= 48:
        return 1
    elif hours_ahead <= 120:
        return 6
    else:
        return 12
```

## Usage Guidelines

1. **API Key Management**:
   - Required for all API calls
   - Store securely in configuration
   - Monitor usage limits
   - Register at https://opendata.aemet.es/

2. **Rate Limiting**:
   - Minimum 1 second between API calls
   - Cache responses when possible
   - Monitor rate limit headers
   - Use appropriate block sizes

3. **Error Handling**:
   - Handle two-step request process errors
   - Cache failures should fallback to API calls
   - Invalid responses should be logged and reported
   - Handle municipality lookup failures

4. **Data Processing**:
   - Convert timestamps to UTC
   - Use metric units
   - Map weather codes to standard format
   - Handle day/night variations

## Testing

1. **Unit Tests**:
   - Test weather code mapping
   - Test municipality distance calculation
   - Test block size determination
   - Test data parsing

2. **Integration Tests**:
   - Test API connectivity
   - Test municipality lookup
   - Test rate limiting
   - Test caching behavior

3. **Error Tests**:
   - Test API key validation
   - Test rate limit handling
   - Test invalid response handling
   - Test municipality lookup failures

## Attribution

When using AEMET data, proper attribution is required:

1. Include "Data provided by AEMET" in user-facing applications
2. Link to AEMET website (https://www.aemet.es)
3. Follow AEMET's data usage guidelines
