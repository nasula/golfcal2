# OpenWeather Service API

## Overview

The OpenWeather service provides global weather coverage and serves as both a primary service for regions not covered by specialized providers and a fallback service when regional services are unavailable.

## API Details

- **Base URL**: `https://api.openweathermap.org/data/2.5/forecast`
- **Documentation**: [OpenWeather API Documentation](https://openweathermap.org/api/one-call-3)
- **Authentication**: API key required
- **Rate Limit**: 60 calls/minute (free tier)
- **Update Frequency**: Every 3 hours
- **Geographic Coverage**: Global

## Implementation

```python
class OpenWeatherService(WeatherService):
    BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        super().__init__(local_tz, utc_tz)
        self.api_key = config.global_config['api_keys']['weather']['openweather']
        self.db = WeatherDatabase('open_weather', OPEN_WEATHER_SCHEMA)
```

## Request Format

### Headers

```python
headers = {
    'Accept': 'application/json'
}
```

### Parameters

```python
params = {
    'lat': 60.1699,          # Latitude
    'lon': 24.9384,          # Longitude
    'appid': 'YOUR_API_KEY', # API key
    'units': 'metric',       # Use metric units
    'lang': 'en'            # Language for descriptions
}
```

## Response Format

```json
{
    "cod": "200",
    "message": 0,
    "cnt": 40,
    "list": [
        {
            "dt": 1704808800,
            "main": {
                "temp": -3.1,
                "feels_like": -8.1,
                "temp_min": -3.1,
                "temp_max": -2.9,
                "pressure": 1015,
                "sea_level": 1015,
                "grnd_level": 1012,
                "humidity": 74,
                "temp_kf": -0.2
            },
            "weather": [
                {
                    "id": 600,
                    "main": "Snow",
                    "description": "light snow",
                    "icon": "13d"
                }
            ],
            "clouds": {
                "all": 100
            },
            "wind": {
                "speed": 6.0,
                "deg": 180,
                "gust": 13.0
            },
            "visibility": 10000,
            "pop": 0.74,
            "snow": {
                "3h": 0.7
            },
            "sys": {
                "pod": "d"
            },
            "dt_txt": "2024-01-09 13:00:00"
        }
    ],
    "city": {
        "id": 658225,
        "name": "Helsinki",
        "coord": {
            "lat": 60.1699,
            "lon": 24.9384
        },
        "country": "FI",
        "population": 558457,
        "timezone": 7200,
        "sunrise": 1704782580,
        "sunset": 1704806280
    }
}
```

## Weather Data Mapping

### Weather Codes

OpenWeather uses numeric ID codes that we map to our standard weather codes:

```python
WEATHER_CODE_MAP = {
    # Clear conditions
    800: lambda h: 'clearsky_day' if 6 <= h <= 18 else 'clearsky_night',
    
    # Cloud conditions
    801: lambda h: 'fair_day' if 6 <= h <= 18 else 'fair_night',
    802: lambda h: 'partlycloudy_day' if 6 <= h <= 18 else 'partlycloudy_night',
    803: 'cloudy',
    804: 'cloudy',
    
    # Rain
    500: 'lightrain',
    501: 'rain',
    502: 'heavyrain',
    
    # Thunderstorm
    200: 'lightrainandthunder',
    201: 'rainandthunder',
    202: 'heavyrainandthunder'
}
```

### Thunder Probability Mapping

Thunder probability is calculated based on weather codes:

```python
THUNDER_PROBABILITY_MAP = {
    200: 30.0,  # Light thunderstorm
    201: 60.0,  # Thunderstorm
    202: 90.0,  # Heavy thunderstorm
    210: 20.0,  # Light thunderstorm
    211: 50.0,  # Thunderstorm
    212: 80.0,  # Heavy thunderstorm
    221: 40.0,  # Ragged thunderstorm
    230: 25.0,  # Light thunderstorm with drizzle
    231: 45.0,  # Thunderstorm with drizzle
    232: 65.0   # Heavy thunderstorm with drizzle
}
```

## Error Handling

### Common Errors

1. **API Key Error**
   ```python
   if response.status_code == 401:
       raise WeatherError(
           "Invalid OpenWeather API key",
           ErrorCode.AUTH_ERROR,
           {"api_key": self.api_key}
       )
   ```

2. **Rate Limit Error**
   ```python
   if response.status_code == 429:
       raise WeatherError(
           "OpenWeather rate limit exceeded",
           ErrorCode.RATE_LIMIT_EXCEEDED,
           {"limit": "60 calls/minute"}
       )
   ```

### Rate Limiting

```python
def _handle_rate_limit(self):
    """Ensure we don't exceed 60 calls per minute."""
    now = time.time()
    if len(self._request_times) >= 60:
        oldest = self._request_times[0]
        if now - oldest < 60:
            sleep_time = 60 - (now - oldest)
            time.sleep(sleep_time)
        self._request_times = self._request_times[1:]
    self._request_times.append(now)
```

## Caching Strategy

- Cache key format: `{club}_{lat:.4f}_{lon:.4f}_{base_time}`
- Cache duration: 3 hours (matches API update frequency)
- Automatic cache invalidation on API updates

```python
def _get_cache_key(self, lat: float, lon: float, club: str, base_time: datetime) -> str:
    # Round to nearest 3-hour block
    rounded_time = base_time.replace(
        hour=(base_time.hour // 3) * 3,
        minute=0,
        second=0,
        microsecond=0
    )
    return f"{club}_{lat:.4f}_{lon:.4f}_{rounded_time.strftime('%Y%m%d%H')}"
```

## Best Practices

1. **Request Optimization**
   - Use metric units
   - Cache responses for 3 hours
   - Monitor rate limits
   - Batch requests when possible

2. **Error Handling**
   - Validate API key before requests
   - Handle rate limits with queuing
   - Implement request retries
   - Log all API interactions

3. **Data Processing**
   - Convert timestamps to UTC
   - Handle precipitation units
   - Calculate thunder probability
   - Process day/night variations

4. **Integration**
   - Use as fallback service
   - Handle timezone differences
   - Monitor API quota usage
   - Keep API key secure 