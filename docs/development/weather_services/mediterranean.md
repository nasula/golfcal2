# Mediterranean Weather Service (OpenWeather)

## Overview

The Mediterranean Weather Service uses OpenWeather's API to provide weather forecasts for regions not covered by other specialized services. It serves as the default fallback service and provides comprehensive weather data with 3-hour resolution.

## Coverage

- **Geographic Area**: Default fallback service for regions not covered by other services
- **Forecast Range**: 5 days
- **Update Frequency**: Every 3 hours
- **Resolution**: 3-hour blocks throughout the forecast period

## Features

- 5-day forecast with 3-hour intervals
- API key required
- Metric units (Celsius, meters/sec)
- Precipitation probability
- Thunder probability calculation
- 1-second rate limiting
- Caching support with 2-hour expiry

## Implementation

### Configuration

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
        self.db = WeatherDatabase('mediterranean_weather', MEDITERRANEAN_SCHEMA)
        self._min_call_interval = timedelta(seconds=1)
```

### Data Fetching

```python
def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime):
    """Fetch forecasts from OpenWeather API."""
    # Build request
    forecast_url = f"{self.endpoint}/forecast"
    params = {
        'lat': lat,
        'lon': lon,
        'appid': self.api_key,
        'units': 'metric'  # Use Celsius and meters/sec
    }
    
    # Make request with error handling
    try:
        response = requests.get(
            forecast_url,
            params=params,
            headers=self.headers,
            timeout=10
        )
        
        if response.status_code == 429:
            raise APIRateLimitError("Rate limit exceeded")
        response.raise_for_status()
        
        data = response.json()
        forecasts = []
        
        for forecast in data['list']:
            # Convert timestamp to datetime
            time_str = forecast['dt_txt']
            forecast_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            forecast_time = forecast_time.replace(tzinfo=self.utc_tz)
            
            # Skip if outside requested time range
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
                precipitation_probability=forecast.get('pop', 0.0) * 100,
                wind_speed=wind.get('speed'),
                wind_direction=self._get_wind_direction(wind.get('deg')),
                symbol=self._map_openweather_code(str(weather.get('id')), forecast_time.hour),
                elaboration_time=forecast_time,
                thunder_probability=self._calculate_thunder_probability(str(weather.get('id')))
            )
            forecasts.append(forecast_data)
        
        return forecasts
        
    except Exception as e:
        self.error(f"API request failed: {str(e)}")
        return []
```

### Thunder Probability Calculation

The service provides unique thunder probability calculations based on weather codes:

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

### Weather Code Mapping

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

### Wind Direction Mapping

```python
def _get_wind_direction(self, degrees: Optional[float]) -> Optional[str]:
    """Convert wind direction from degrees to cardinal direction."""
    if degrees is None:
        return None
    
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    index = round(degrees / 45) % 8
    return directions[index]
```

### Block Size Determination

```python
def get_block_size(self, hours_ahead: float) -> int:
    """Get forecast block size based on hours ahead.
    
    OpenWeather provides:
    - 3-hour blocks for first 5 days
    """
    return 3  # OpenWeather always provides 3-hour blocks
```

## Usage Guidelines

1. **API Key Management**:
   - Required for all API calls
   - Store securely in configuration
   - Monitor usage limits

2. **Rate Limiting**:
   - Minimum 1 second between API calls
   - Cache responses when possible
   - Monitor rate limit headers

3. **Error Handling**:
   - Handle rate limit errors with backoff
   - Cache failures should fallback to API calls
   - Invalid responses should be logged and reported

4. **Data Processing**:
   - Convert precipitation from 3-hour to hourly rates
   - Convert probabilities to percentages
   - Map weather codes to standard format
   - Handle day/night variations in weather codes

## Testing

1. **Unit Tests**:
   - Test weather code mapping
   - Test thunder probability calculation
   - Test wind direction conversion
   - Test precipitation rate conversion

2. **Integration Tests**:
   - Test API connectivity
   - Test rate limiting
   - Test caching behavior
   - Test timezone handling

3. **Error Tests**:
   - Test API key validation
   - Test rate limit handling
   - Test invalid response handling
   - Test timeout handling
