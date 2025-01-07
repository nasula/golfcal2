# Weather Service Implementation

## Overview

The Weather Service provides weather data for golf courses through multiple weather data providers. The system uses a region-based approach to select the most appropriate weather service for each location.

## Core Components

### 1. WeatherService Base Class

The base class for all weather services inherits from `EnhancedLoggerMixin` for advanced logging capabilities:

```python
class WeatherService(EnhancedLoggerMixin):
    def __init__(self, local_tz, utc_tz):
        """Initialize weather service with timezone information."""
        super().__init__()
        self.local_tz = local_tz
        self.utc_tz = utc_tz
        self.set_correlation_id()  # Generate unique ID for this service instance

    @log_execution(level='DEBUG')
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Get weather data for location and time range with comprehensive error handling."""
        # Main public interface for fetching weather data
        pass

    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Abstract method to be implemented by subclasses for actual API calls."""
        raise NotImplementedError("Subclasses must implement _fetch_forecasts")

    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size based on forecast time.
        
        Args:
            hours_ahead: Number of hours ahead of current time
            
        Returns:
            Block size in hours (e.g., 1 for hourly forecasts)
        """
        raise NotImplementedError("Subclasses must implement get_block_size")
```

### 2. Weather Data Models

#### WeatherData Class
```python
@dataclass
class WeatherData:
    """Weather data container for standardized forecast data."""
    temperature: float
    precipitation: float
    precipitation_probability: Optional[float]
    wind_speed: float
    wind_direction: Optional[str]
    symbol: str
    elaboration_time: datetime
    thunder_probability: Optional[float] = None
```

#### Weather Codes
```python
class WeatherCode(str, Enum):
    """Standard weather codes used across all weather services."""
    CLEARSKY_DAY = 'clearsky_day'
    CLEARSKY_NIGHT = 'clearsky_night'
    FAIR_DAY = 'fair_day'
    FAIR_NIGHT = 'fair_night'
    PARTLY_CLOUDY_DAY = 'partlycloudy_day'
    PARTLY_CLOUDY_NIGHT = 'partlycloudy_night'
    CLOUDY = 'cloudy'
    FOG = 'fog'
    LIGHTRAIN = 'lightrain'
    RAIN = 'rain'
    HEAVYRAIN = 'heavyrain'
    # ... and many more weather conditions
```

### 3. Error Handling

The system implements comprehensive error handling through several specialized exception classes:

```python
from golfcal2.exceptions import (
    WeatherError,          # Base class for weather-specific errors
    APIError,             # Base class for API-related errors
    APITimeoutError,      # For request timeouts
    APIRateLimitError,    # For rate limit violations
    APIResponseError,     # For invalid API responses
    ErrorCode,            # Enumeration of error codes
    handle_errors         # Context manager for error handling
)
```

Example error handling implementation:
```python
@log_execution(level='DEBUG')
def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime):
    try:
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            raise ValueError("start_time and end_time must be datetime objects")
        
        self.set_log_context(
            latitude=lat,
            longitude=lon,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat()
        )
        
        forecasts = self._fetch_forecasts(lat, lon, start_time, end_time)
        
        if not forecasts:
            self.warning("No forecasts found")
            return []
        
        return forecasts
        
    except Exception as e:
        self.error(
            "Failed to fetch weather data",
            exc_info=e,
            service=self.__class__.__name__
        )
        return []
    finally:
        self.clear_log_context()
```

### 4. Weather Service Manager

The `WeatherManager` class is the main entry point for weather services, handling service selection and coordination:

```python
class WeatherManager(EnhancedLoggerMixin):
    """Weather service manager for coordinating multiple weather services."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        """Initialize weather services.
        
        Args:
            local_tz: Local timezone object
            utc_tz: UTC timezone object
            config: Application configuration
        """
        super().__init__()
        
        # Initialize services
        self.services = {
            'mediterranean': MediterraneanWeatherService(self.local_tz, self.utc_tz, config),
            'iberian': IberianWeatherService(self.local_tz, self.utc_tz, config),
            'met': MetWeatherService(self.local_tz, self.utc_tz, config),
            'portuguese': PortugueseWeatherService(self.local_tz, self.utc_tz, config)
        }
        
        # Define service regions with precise boundaries
        self.regions = {
            'norway': {
                'service': 'met',
                'bounds': (57.0, 71.5, 4.0, 31.5)  # lat_min, lat_max, lon_min, lon_max
            },
            'mediterranean': {
                'service': 'mediterranean',
                'bounds': (35.0, 45.0, 20.0, 45.0)
            },
            'portugal': {
                'service': 'portuguese',
                'bounds': (36.5, 42.5, -9.5, -7.5)  # Mainland Portugal
            },
            'spain_mainland': {
                'service': 'iberian',
                'bounds': (36.0, 44.0, -7.5, 3.5)  # Mainland Spain
            },
            'spain_canary': {
                'service': 'iberian',
                'bounds': (27.5, 29.5, -18.5, -13.0)  # Canary Islands
            }
        }
```

The manager provides the following key features:

1. **Service Selection**: Automatically selects the appropriate weather service based on coordinates:
   ```python
   def _get_service_for_location(self, lat: float, lon: float, club: str) -> Optional[WeatherService]:
       """Select appropriate weather service based on coordinates."""
       for region, config in self.regions.items():
           lat_min, lat_max, lon_min, lon_max = config['bounds']
           if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
               return self.services[config['service']]
       
       # Default to Mediterranean service if no specific region matches
       return self.services['mediterranean']
   ```

2. **Weather Data Retrieval**: Handles weather data fetching with comprehensive validation:
   ```python
   def get_weather(
       self, 
       club: str, 
       teetime: datetime, 
       coordinates: Dict[str, float], 
       duration_minutes: Optional[int] = None
   ) -> Optional[str]:
       """Get weather data for a specific time and location."""
       # Validate coordinates
       lat = coordinates.get('lat')
       lon = coordinates.get('lon')
       
       if lat is None or lon is None:
           self.error("Missing coordinates", club=club)
           return None

       # Skip invalid dates
       if teetime < datetime.now(self.utc_tz):
           self.debug(f"Skipping past date {teetime}")
           return None

       if teetime > datetime.now(self.utc_tz) + timedelta(days=10):
           self.debug(f"Skipping future date {teetime}")
           return None

       # Get appropriate service and fetch weather
       weather_service = self._get_service_for_location(lat, lon, club)
       if not weather_service:
           self.error("No weather service available", club=club)
           return None

       return weather_service.get_weather(lat, lon, start_time, end_time)
   ```

3. **Error Aggregation**: Centralizes error handling and logging:
   ```python
   with handle_errors(WeatherError, "weather", f"get weather for club {club}"):
       # Weather fetching logic
       if error_condition:
           error = WeatherError(
               "Error description",
               ErrorCode.SPECIFIC_ERROR,
               {"context": "details"}
           )
           aggregate_error(str(error), "weather", None)
           return None
   ```

## Supported Weather Services

### 1. MET.no (Nordic Region)
- Coverage: Nordic region (55°N to 72°N, 3°E to 32°E)
- Features:
  - High-resolution forecasts with altitude support
  - No API key required
  - 1-second rate limiting
  - Caching support with 2-hour expiry
  - Automatic data format conversion
  - Comprehensive error handling
  - Detailed logging with correlation IDs

#### Configuration
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

#### Data Fetching with Altitude Support
```python
def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, altitude: Optional[int] = None):
    """Get weather data with optional altitude for more precise temperature values."""
    # Try cache first
    location = f"{lat},{lon}"
    if altitude:
        location += f",{altitude}"
    
    # Generate hourly timestamps for the requested period
    times_to_fetch = []
    current = start_time
    while current <= end_time:
        times_to_fetch.append(current.strftime('%Y-%m-%dT%H:%M:%SZ'))
        current += timedelta(hours=1)
    
    # Check cache
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

#### API Request Handling
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

#### Data Parsing and Caching
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

#### Block Size Determination
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
- Coverage: Default fallback service for regions not covered by other services
- Features:
  - 5-day forecast with 3-hour intervals
  - API key required
  - Metric units (Celsius, meters/sec)
  - Precipitation probability
  - Thunder probability calculation
  - 1-second rate limiting
  - Caching support with 2-hour expiry

#### Configuration
```python
class MediterraneanWeatherService(WeatherService):
    """Weather service using OpenWeather API."""
    
    def __init__(self, local_tz, utc_tz, config):
        super().__init__(local_tz, utc_tz)
        
        # OpenWeather API configuration
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
    
    response = requests.get(
        forecast_url,
        params=params,
        headers=self.headers,
        timeout=10
    )
    
    data = response.json()
    forecasts = []
    
    for forecast in data['list']:
        # Convert timestamp to datetime
        time_str = forecast['dt_txt']
        forecast_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        forecast_time = forecast_time.replace(tzinfo=self.utc_tz)
        
        # Extract weather data
        main = forecast.get('main', {})
        wind = forecast.get('wind', {})
        weather = forecast.get('weather', [{}])[0]
        rain = forecast.get('rain', {})
        
        forecast_data = WeatherData(
            temperature=main.get('temp'),
            precipitation=rain.get('3h', 0.0) / 3.0,  # Convert 3h to 1h
            precipitation_probability=forecast.get('pop', 0.0) * 100,
            wind_speed=wind.get('speed'),
            wind_direction=self._get_wind_direction(wind.get('deg')),
            symbol=self._map_openweather_code(str(weather.get('id')), forecast_time.hour),
            elaboration_time=forecast_time,
            thunder_probability=self._calculate_thunder_probability(str(weather.get('id')))
        )
        forecasts.append(forecast_data)
```

#### Thunder Probability Calculation
```python
def _calculate_thunder_probability(self, weather_id: str) -> float:
    """Calculate thunder probability based on weather code."""
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
        return intensity_map.get(weather_id, 50.0)
    return 0.0
```

#### Wind Direction Mapping
```python
def _get_wind_direction(self, degrees: Optional[float]) -> Optional[str]:
    """Convert wind direction from degrees to cardinal direction."""
    if degrees is None:
        return None
    
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    index = round(degrees / 45) % 8
    return directions[index]
```

#### Block Size Determination
```python
def get_block_size(self, hours_ahead: float) -> int:
    """Get forecast block size based on hours ahead.
    
    OpenWeather provides:
    - 3-hour blocks for first 5 days
    """
    return 3  # OpenWeather always provides 3-hour blocks
```

### 4. Portuguese Weather Service (IPMA)
- Coverage: Portugal (36.5°N to 42.5°N, -9.5°E to -7.5°E)
- Features:
  - Daily forecasts for Portuguese cities and islands
  - Updates twice daily at 10:00 and 20:00 UTC
  - No API key required
  - Location-based forecasts using nearest city
  - Automatic data format conversion
  - 1-second rate limiting
  - Caching support with 2-hour expiry

#### Configuration
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
        self._min_call_interval = timedelta(seconds=1)
```

#### Location Handling
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

#### Data Fetching
```python
def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime):
    # Try cache first
    cached_location = self.location_cache.get_ipma_location(lat, lon)
    
    if not cached_location:
        # Find nearest location from IPMA API
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
    
    # Get forecasts for location
    forecast_url = f"{self.endpoint}/forecast/meteorology/cities/daily/{location_id}.json"
    response = requests.get(forecast_url, headers=self.headers)
    forecasts = response.json()
```

#### Weather Code Mapping
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

#### Block Size Determination
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