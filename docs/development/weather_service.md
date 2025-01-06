# Weather Service Implementation

## Overview

The Weather Service provides weather data for golf courses through multiple weather data providers. The system uses a region-based approach to select the most appropriate weather service for each location.

## Core Components

### 1. WeatherService Base Class

```python
class WeatherService(EnhancedLoggerMixin):
    def __init__(self, local_tz, utc_tz):
        # Initialize timezones and logging
        pass

    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        # Main public interface for fetching weather data
        pass

    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        # Abstract method to be implemented by subclasses
        pass

    def get_block_size(self, hours_ahead: float) -> int:
        # Get forecast block size based on forecast time
        pass
```

### 2. Weather Data Model

```python
class WeatherCode:
    CLEAR_DAY = "clearsky_day"
    CLEAR_NIGHT = "clearsky_night"
    FAIR_DAY = "fair_day"
    FAIR_NIGHT = "fair_night"
    PARTLY_CLOUDY_DAY = "partlycloudy_day"
    PARTLY_CLOUDY_NIGHT = "partlycloudy_night"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "lightrain"
    RAIN = "rain"
    HEAVY_RAIN = "heavyrain"
    RAIN_AND_THUNDER = "rainandthunder"
    HEAVY_RAIN_AND_THUNDER = "heavyrainandthunder"
    LIGHT_SNOW = "lightsnow"
    SNOW = "snow"
    HEAVY_SNOW = "heavysnow"
    LIGHT_SLEET = "lightsleet"
    HEAVY_SLEET = "heavysleet"
    FOG = "fog"
```

## Supported Weather Services

### 1. MET.no (Nordic Region)
- Coverage: 55°N to 72°N, 3°E to 32°E
- Features:
  - High-resolution forecasts
  - No API key required
  - 1-second rate limiting
  - Caching support with 2-hour expiry
  - Automatic data format conversion

#### Configuration
```python
class MetWeatherService(WeatherService):
    BASE_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz, utc_tz, config):
        super().__init__(local_tz, utc_tz)
        self.endpoint = self.BASE_URL
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': self.USER_AGENT
        }
        self._min_call_interval = timedelta(seconds=1)
```

#### Data Fetching
```python
def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime):
    # Apply rate limiting
    self._apply_rate_limit()
    
    # Prepare request
    params = {
        'lat': f"{lat:.4f}",
        'lon': f"{lon:.4f}"
    }
    
    # Make request
    response = requests.get(
        self.BASE_URL,
        params=params,
        headers=headers,
        timeout=(10, 30)  # (connect timeout, read timeout)
    )
```

#### Data Parsing
```python
def _parse_response(self, data: Dict[str, Any], start_time: datetime, end_time: datetime):
    forecasts = []
    timeseries = data['properties']['timeseries']
    
    for entry in timeseries:
        # Parse timestamp
        time_str = entry['time']
        forecast_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        
        # Skip forecasts outside time range
        if not (start_time <= forecast_time <= end_time):
            continue
        
        # Get instant data
        instant = entry['data']['instant']['details']
        
        # Get precipitation data from next_1_hours if available, else next_6_hours
        precip_data = (
            entry['data'].get('next_1_hours', {}).get('details', {}) or
            entry['data'].get('next_6_hours', {}).get('details', {})
        )
        
        # Get symbol from next_1_hours if available, else next_6_hours
        symbol_data = (
            entry['data'].get('next_1_hours', {}).get('summary', {}) or
            entry['data'].get('next_6_hours', {}).get('summary', {})
        )
        
        forecast = WeatherData(
            temperature=instant.get('air_temperature'),
            precipitation=precip_data.get('precipitation_amount', 0.0),
            precipitation_probability=precip_data.get('probability_of_precipitation'),
            wind_speed=instant.get('wind_speed', 0.0),
            wind_direction=self._get_wind_direction(instant.get('wind_from_direction')),
            symbol=symbol_data.get('symbol_code', 'cloudy'),
            elaboration_time=forecast_time,
            thunder_probability=entry['data'].get('probability_of_thunder', 0.0)
        )
        
        forecasts.append(forecast)
```

#### Caching
```python
# Store in cache with 2-hour expiry
expires = (datetime.utcnow() + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
db_entries = []
for time_str, data in weather_data.items():
    entry = {
        'location': location,
        'time': time_str,
        'data_type': 'next_1_hours',
        'air_temperature': data.get('temperature'),
        'precipitation_amount': data.get('precipitation'),
        'wind_speed': data.get('wind_speed'),
        'wind_from_direction': data.get('wind_direction'),
        'probability_of_precipitation': data.get('precipitation_probability'),
        'probability_of_thunder': data.get('thunder_probability', 0.0),
        'summary_code': data.get('symbol')
    }
    db_entries.append(entry)

self.db.store_weather_data(db_entries, expires=expires)
```

#### Error Handling
1. **Rate Limiting**
   ```python
   if response.status_code == 429:  # Too Many Requests
       error = APIRateLimitError(
           "MET.no API rate limit exceeded",
           retry_after=int(response.headers.get('Retry-After', 60))
       )
       aggregate_error(str(error), "met_weather", None)
       return []
   ```

2. **Invalid Response**
   ```python
   if not data or data.get('type') != 'Feature':
       error = WeatherError(
           "Invalid API response format - not a GeoJSON Feature",
           ErrorCode.INVALID_RESPONSE,
           {"data": data}
       )
       aggregate_error(str(error), "met_weather", None)
       return None
   ```

3. **Timeout Handling**
   ```python
   except requests.exceptions.Timeout:
       error = APITimeoutError(
           "MET.no API request timed out",
           {"url": self.BASE_URL}
       )
       aggregate_error(str(error), "met_weather", None)
       return []
   ```

#### Weather Symbol Mapping
```python
def _map_symbol_code(self, symbol_code: str) -> str:
    """Map MET.no symbol codes to internal weather codes."""
    symbol_map = {
        'clearsky': 'CLEAR',
        'fair': 'PARTLY_CLOUDY',
        'partlycloudy': 'PARTLY_CLOUDY',
        'cloudy': 'CLOUDY',
        'fog': 'FOG',
        'rain': 'RAIN',
        'sleet': 'SLEET',
        'snow': 'SNOW',
        'rainshowers': 'RAIN_SHOWERS',
        'sleetshowers': 'SLEET_SHOWERS',
        'snowshowers': 'SNOW_SHOWERS',
        'lightrainshowers': 'LIGHT_RAIN',
        'heavyrainshowers': 'HEAVY_RAIN',
        'lightrain': 'LIGHT_RAIN',
        'heavyrain': 'HEAVY_RAIN',
        'lightsnow': 'LIGHT_SNOW',
        'heavysnow': 'HEAVY_SNOW',
        'thunder': 'THUNDER',
        'rainandthunder': 'RAIN_AND_THUNDER',
        'sleetandthunder': 'SLEET_AND_THUNDER',
        'snowandthunder': 'SNOW_AND_THUNDER'
    }
    return symbol_map.get(symbol_code, 'CLOUDY')
```

### 2. Iberian Weather Service (AEMET/IPMA)
- Coverage: Spain (-7°E to 5°E) and Portugal (-9.5°E to -6.2°E)
- Features:
  - Municipality-based forecasts
  - API key required
  - Location caching
  - Automatic municipality selection
  - Rate limiting with 1-second intervals

#### Authentication and Headers
```python
headers = {
    'Accept': 'application/json',
    'User-Agent': 'GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)',
    'api_key': config.global_config['api_keys']['weather']['aemet']
}
```

#### Municipality Handling
1. **Location Cache**
   ```python
   # Try cached municipality first
   cached_municipality = self.location_cache.get_municipality(lat, lon)
   if cached_municipality:
       municipality_code = cached_municipality['code']
   ```

2. **Municipality Discovery**
   ```python
   # If not in cache, fetch from API
   municipality_url = f"{self.endpoint}/maestro/municipios"
   response = requests.get(municipality_url, headers=self.headers)
   
   # Find nearest municipality
   nearest_municipality = find_nearest_municipality(lat, lon, municipalities)
   municipality_code = numeric_id.zfill(5)  # Ensure 5 digits with leading zeros
   
   # Cache for future use
   self.location_cache.cache_municipality(
       lat=lat,
       lon=lon,
       municipality_code=municipality_code,
       name=nearest_municipality.get('nombre', ''),
       mun_lat=float(nearest_municipality.get('latitud_dec', 0)),
       mun_lon=float(nearest_municipality.get('longitud_dec', 0)),
       distance=min_distance
   )
   ```

#### Forecast Fetching
```python
# Get forecast for municipality
forecast_url = f"{self.endpoint}/prediccion/especifica/municipio/horaria/{municipality_code}"

# Respect rate limits
if self._last_api_call:
    time_since_last = datetime.now() - self._last_api_call
    if time_since_last < self._min_call_interval:
        sleep_time = (self._min_call_interval - time_since_last).total_seconds()
        time.sleep(sleep_time)

response = requests.get(forecast_url, headers=self.headers)
self._last_api_call = datetime.now()
```

#### Error Handling
1. **Rate Limiting**
   ```python
   if response.status_code == 429:  # Too Many Requests
       error = APIRateLimitError(
           "AEMET API rate limit exceeded",
           retry_after=int(response.headers.get('Retry-After', 60))
       )
       aggregate_error(str(error), "iberian_weather", None)
       return []
   ```

2. **Data Availability**
   ```python
   if response.status_code == 404:  # Not Found - no data available
       self.warning(
           "No forecasts found",
           latitude=lat,
           longitude=lon,
           start_time=start_time.isoformat(),
           end_time=end_time.isoformat()
       )
       return []
   ```

3. **API Key Validation**
   ```python
   if not self.api_key:
       error = WeatherError(
           "AEMET API key not configured",
           ErrorCode.CONFIG_MISSING,
           {"setting": "api_keys.weather.aemet"}
       )
       aggregate_error(str(error), "iberian_weather", None)
       return []
   ```

#### Weather Code Mapping
The service includes comprehensive weather code mapping for AEMET codes:

```python
def _map_aemet_code(self, code: str, hour: int) -> str:
    base_code = code.rstrip('n')  # Strip night indicator
    code_map = {
        '11': WeatherCode.CLEAR_DAY,
        '11n': WeatherCode.CLEAR_NIGHT,
        '12': WeatherCode.FAIR_DAY,
        '12n': WeatherCode.FAIR_NIGHT,
        '13': WeatherCode.PARTLY_CLOUDY_DAY,
        '13n': WeatherCode.PARTLY_CLOUDY_NIGHT,
        '14': WeatherCode.CLOUDY,
        '15': WeatherCode.LIGHT_RAIN,
        '71': WeatherCode.RAIN_AND_THUNDER,
        '72': WeatherCode.RAIN_AND_THUNDER,
        '73': WeatherCode.HEAVY_RAIN_AND_THUNDER,
        '74': WeatherCode.HEAVY_RAIN_AND_THUNDER
    }
    return code_map.get(base_code, WeatherCode.CLOUDY)
```

### 3. Mediterranean Weather Service (OpenWeather)
- Coverage: Default fallback service
- Features:
  - Global coverage
  - API key required
  - 5-day forecast support
  - 3-hour forecast intervals
  - Metric units (Celsius, meters/sec)
  - Rate limiting with 1-second intervals

#### Configuration
```python
class MediterraneanWeatherService(WeatherService):
    def __init__(self, local_tz, utc_tz, config):
        super().__init__(local_tz, utc_tz)
        self.api_key = config.global_config['api_keys']['weather']['openweather']
        self.endpoint = 'https://api.openweathermap.org/data/2.5'
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'GolfCal/2.0 github.com/jahonen/golfcal'
        }
        self._min_call_interval = timedelta(seconds=1)
```

#### Data Fetching
```python
def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime):
    forecast_url = f"{self.endpoint}/forecast"
    params = {
        'lat': lat,
        'lon': lon,
        'appid': self.api_key,
        'units': 'metric'  # Use Celsius and meters/sec
    }
    
    # Respect rate limits
    if self._last_api_call:
        time_since_last = datetime.now() - self._last_api_call
        if time_since_last < self._min_call_interval:
            sleep_time = (self._min_call_interval - time_since_last).total_seconds()
            time.sleep(sleep_time)
            
    response = requests.get(
        forecast_url,
        params=params,
        headers=self.headers,
        timeout=10
    )
```

#### Data Processing
```python
# Process each forecast entry
for forecast in data['list']:
    # Convert timestamp to datetime
    time_str = forecast['dt_txt']
    forecast_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    forecast_time = forecast_time.replace(tzinfo=self.utc_tz)
    
    # Skip if outside our time range
    if forecast_time < start_time or forecast_time > end_time:
        continue
    
    # Extract weather data
    main = forecast.get('main', {})
    wind = forecast.get('wind', {})
    weather = forecast.get('weather', [{}])[0]
    rain = forecast.get('rain', {})
    
    forecast_data = WeatherData(
        temperature=main.get('temp'),
        precipitation=rain.get('3h', 0.0) / 3.0,  # Convert 3h to 1h
        precipitation_probability=forecast.get('pop', 0.0) * 100,  # Convert to percentage
        wind_speed=wind.get('speed'),
        wind_direction=self._get_wind_direction(wind.get('deg')),
        symbol=symbol_code,
        elaboration_time=forecast_time,
        thunder_probability=thunder_prob
    )
```

#### Thunder Probability Calculation
```python
# Calculate thunder probability based on weather code
thunder_prob = 0.0
if weather_id.startswith('2'):  # 2xx codes are thunderstorm conditions
    intensity_map = {
        '200': 30.0,  # Light thunderstorm
        '201': 60.0,  # Thunderstorm
        '202': 90.0,  # Heavy thunderstorm
        '210': 20.0,  # Light thunderstorm
        '211': 50.0,  # Thunderstorm
        '212': 80.0,  # Heavy thunderstorm
        '221': 40.0,  # Ragged thunderstorm
        '230': 25.0,  # Light thunderstorm with drizzle
        '231': 45.0,  # Thunderstorm with drizzle
        '232': 65.0   # Heavy thunderstorm with drizzle
    }
    thunder_prob = intensity_map.get(weather_id, 50.0)
```

#### Weather Code Mapping
```python
def _map_openweather_code(self, code: str, hour: int) -> str:
    """Map OpenWeather API codes to internal weather codes."""
    is_day = 6 <= hour <= 18
    
    code_map = {
        # Clear conditions
        '800': 'clearsky_day' if is_day else 'clearsky_night',
        '801': 'fair_day' if is_day else 'fair_night',
        '802': 'partlycloudy_day' if is_day else 'partlycloudy_night',
        '803': 'cloudy',
        '804': 'cloudy',
        
        # Rain
        '500': 'lightrain',
        '501': 'rain',
        '502': 'heavyrain',
        '511': 'sleet',
        '520': 'lightrainshowers_day' if is_day else 'lightrainshowers_night',
        '521': 'rainshowers_day' if is_day else 'rainshowers_night',
        '522': 'heavyrainshowers_day' if is_day else 'heavyrainshowers_night',
        
        # Snow
        '600': 'lightsnow',
        '601': 'snow',
        '602': 'heavysnow',
        '611': 'sleet',
        '612': 'lightsleet',
        '613': 'heavysleet',
        
        # Thunderstorm
        '200': 'rainandthunder',
        '201': 'rainandthunder',
        '202': 'heavyrainandthunder',
        '210': 'rainandthunder',
        '211': 'rainandthunder',
        '212': 'heavyrainandthunder'
    }
    
    return code_map.get(code, 'cloudy')  # Default to cloudy if code not found
```

#### Error Handling
1. **Rate Limiting**
   ```python
   if response.status_code == 429:  # Too Many Requests
       error = APIRateLimitError(
           "OpenWeather API rate limit exceeded",
           retry_after=int(response.headers.get('Retry-After', 60))
       )
       aggregate_error(str(error), "mediterranean_weather", None)
       return []
   ```

2. **Invalid Response**
   ```python
   if not data or 'list' not in data:
       error = WeatherError(
           "Invalid response format from OpenWeather API",
           ErrorCode.INVALID_RESPONSE,
           {"response": data}
       )
       aggregate_error(str(error), "mediterranean_weather", None)
       return []
   ```

3. **API Key Validation**
   ```python
   if not self.api_key:
       error = WeatherError(
           "OpenWeather API key not configured",
           ErrorCode.CONFIG_MISSING,
           {"setting": "api_keys.weather.openweather"}
       )
       aggregate_error(str(error), "mediterranean_weather", None)
       return []
   ```

## Service Selection

The system automatically selects the appropriate weather service based on coordinates:

```python
def select_weather_service(lat: float, lon: float) -> WeatherService:
    if 55 <= lat <= 72 and 3 <= lon <= 32:  # Nordic
        return MetNoWeatherService()
    elif -9.5 <= lon <= -6.2:  # Portugal
        return IberianWeatherService()  # IPMA
    elif -7 <= lon <= 5:  # Spain
        return IberianWeatherService()  # AEMET
    else:  # Mediterranean
        return MediterraneanWeatherService()  # OpenWeather
```

## Error Handling

The service implements comprehensive error handling:

1. **API Errors**
   - `WeatherError`: Base class for weather-specific errors
   - `APITimeoutError`: For request timeouts
   - `APIResponseError`: For invalid responses
   - `APIRateLimitError`: For rate limit violations

2. **Recovery Strategies**
   - Automatic retries for transient failures
   - Rate limit handling with backoff
   - Fallback to cached data when possible

3. **Logging**
   - Enhanced logging with context
   - Debug level for API interactions
   - Warning level for service issues
   - Error level for critical failures

## Best Practices

1. **Rate Limiting**
   - Respect service-specific rate limits
   - Implement exponential backoff
   - Cache successful responses

2. **Data Validation**
   - Validate coordinates before requests
   - Verify response formats
   - Handle missing data gracefully

3. **Error Recovery**
   - Implement automatic retries
   - Cache successful responses
   - Provide fallback data when possible

4. **Testing**
   - Test different coordinate ranges
   - Verify service selection logic
   - Test error handling scenarios
   - Validate rate limiting behavior

## Implementation Example

Here's an example of implementing a new weather service:

```python
class NewWeatherService(WeatherService):
    def __init__(self, local_tz, utc_tz, config):
        super().__init__(local_tz, utc_tz)
        self.api_key = config.global_config['api_keys']['weather']['new_service']
        self.endpoint = "https://api.example.com/weather"
        self._min_call_interval = timedelta(seconds=1)

    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        response = requests.get(
            f"{self.endpoint}/forecast",
            params={
                'lat': lat,
                'lon': lon,
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            headers={'Authorization': f'Bearer {self.api_key}'}
        )
        response.raise_for_status()
        return self._parse_response(response.json())

    def get_block_size(self, hours_ahead: float) -> int:
        if hours_ahead <= 48:
            return 1  # Hourly forecasts for first 48 hours
        return 6  # 6-hour blocks beyond that
``` 