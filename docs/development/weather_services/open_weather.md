# OpenWeather Service

## Overview

The OpenWeather service uses OpenWeather's API to provide weather forecasts globally. It serves as a fallback service for regions not covered by specialized services and provides comprehensive weather data through the OpenWeather API.

## Implementation

```python
class OpenWeatherService(WeatherService):
    """OpenWeather API implementation."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        """Initialize OpenWeather service."""
        super().__init__(local_tz, utc_tz)
        self.api_key = config.get('openweather_key')
        self.db = WeatherDatabase('open_weather', OPEN_WEATHER_SCHEMA)
```

## Features

1. **Coverage**:
   - Global coverage (fallback service)
   - 5-day forecast with 3-hour intervals
   - Comprehensive weather data

2. **Data Points**:
   - Temperature
   - Precipitation amount and probability
   - Wind speed and direction
   - Weather conditions
   - Thunder probability

3. **Caching**:
   - Location-based caching
   - 6-hour cache duration
   - Automatic cache invalidation

4. **Error Handling**:
   - Rate limit management
   - API error handling
   - Fallback mechanisms

## Configuration

1. **API Key**:
   ```yaml
   weather:
     openweather_key: "your-api-key"
   ```

2. **Service Region**:
   ```python
   'global': {
       'service': 'openweather',
       'bounds': {
           'min_lat': -90.0,
           'max_lat': 90.0,
           'min_lon': -180.0,
           'max_lon': 180.0
       }
   }
   ```

## API Details

1. **Endpoints**:
   - Base URL: `https://api.openweathermap.org/data/2.5/`
   - Forecast: `/forecast`

2. **Rate Limits**:
   - 60 calls per minute (free tier)
   - Automatic rate limiting
   - Exponential backoff

3. **Response Format**:
   ```json
   {
       "list": [
           {
               "dt": 1609459200,
               "main": {
                   "temp": 20.5,
                   "feels_like": 19.8,
                   "pressure": 1015
               },
               "weather": [
                   {
                       "id": 800,
                       "main": "Clear",
                       "description": "clear sky"
                   }
               ],
               "wind": {
                   "speed": 5.0,
                   "deg": 180
               },
               "rain": {
                   "3h": 0.0
               },
               "pop": 0.0
           }
       ]
   }
   ```

## Weather Codes

OpenWeather uses numeric codes for weather conditions:

1. **Clear Sky**:
   - 800: Clear sky

2. **Clouds**:
   - 801: Few clouds (11-25%)
   - 802: Scattered clouds (25-50%)
   - 803: Broken clouds (51-84%)
   - 804: Overcast clouds (85-100%)

3. **Rain**:
   - 500: Light rain
   - 501: Moderate rain
   - 502: Heavy rain
   - 503: Very heavy rain
   - 504: Extreme rain

4. **Thunderstorm**:
   - 200: Thunderstorm with light rain
   - 201: Thunderstorm with rain
   - 202: Thunderstorm with heavy rain
   - 210: Light thunderstorm
   - 211: Thunderstorm
   - 212: Heavy thunderstorm

## Error Handling

1. **API Errors**:
   ```python
   try:
       response = requests.get(url, params=params, timeout=10)
       response.raise_for_status()
   except requests.Timeout:
       raise WeatherServiceUnavailable("OpenWeather API request timed out")
   except requests.RequestException as e:
       raise WeatherServiceUnavailable(f"OpenWeather API request failed: {str(e)}")
   ```

2. **Rate Limiting**:
   ```python
   # Wait for rate limit
   sleep_time = self.rate_limiter.get_sleep_time()
   if sleep_time > 0:
       logger.debug(f"Rate limit: sleeping for {sleep_time} seconds")
       time.sleep(sleep_time)
   ```

## Best Practices

1. **API Usage**:
   - Use appropriate units (metric)
   - Handle rate limits properly
   - Cache responses
   - Validate responses

2. **Error Handling**:
   - Catch specific exceptions
   - Provide context in errors
   - Log error details
   - Use fallback mechanisms

3. **Data Processing**:
   - Convert units consistently
   - Validate data ranges
   - Handle missing data
   - Map weather codes correctly

4. **Performance**:
   - Use connection pooling
   - Implement caching
   - Handle rate limits
   - Monitor response times
