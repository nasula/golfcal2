# MET.no Weather Service API

## Overview

The MET.no weather service provides high-resolution weather forecasts for the Nordic region using the Norwegian Meteorological Institute's API. This service is particularly suitable for golf courses in Norway, Sweden, Finland, and Denmark.

## API Details

- **Base URL**: `https://api.met.no/weatherapi/locationforecast/2.0/complete`
- **Documentation**: [MET.no API Documentation](https://api.met.no/weatherapi/locationforecast/2.0/documentation)
- **Authentication**: No API key required, but User-Agent header must be set
- **Rate Limit**: 1 request per second
- **Update Frequency**: Hourly
- **Geographic Coverage**: Nordic region (55°N to 72°N, 3°E to 32°E)

## Implementation

```python
class MetWeatherService(WeatherService):
    BASE_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        super().__init__(local_tz, utc_tz)
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': self.USER_AGENT
        }
        self.db = WeatherDatabase('met_weather', MET_SCHEMA)
```

## Request Format

### Headers

```python
headers = {
    'Accept': 'application/json',
    'User-Agent': 'GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)'
}
```

### Parameters

```python
params = {
    'lat': 60.1699,  # Latitude
    'lon': 24.9384,  # Longitude
    'altitude': 0    # Optional, meters above sea level
}
```

## Response Format

```json
{
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [24.9384, 60.1699]
    },
    "properties": {
        "meta": {
            "updated_at": "2024-01-09T12:00:00Z",
            "units": {
                "air_temperature": "celsius",
                "precipitation_amount": "mm",
                "wind_speed": "m/s"
            }
        },
        "timeseries": [
            {
                "time": "2024-01-09T13:00:00Z",
                "data": {
                    "instant": {
                        "details": {
                            "air_temperature": -3.1,
                            "wind_speed": 6.0,
                            "wind_from_direction": 180,
                            "relative_humidity": 74.0
                        }
                    },
                    "next_1_hours": {
                        "summary": {
                            "symbol_code": "lightsnow"
                        },
                        "details": {
                            "precipitation_amount": 0.7,
                            "probability_of_precipitation": 74.0,
                            "probability_of_thunder": 0.0
                        }
                    }
                }
            }
        ]
    }
}
```

## Weather Data Mapping

### Symbol Codes

MET.no uses standardized weather symbol codes that map directly to our internal codes:

```python
SYMBOL_MAP = {
    'clearsky_day': WeatherCode.CLEARSKY_DAY,
    'clearsky_night': WeatherCode.CLEARSKY_NIGHT,
    'fair_day': WeatherCode.FAIR_DAY,
    'fair_night': WeatherCode.FAIR_NIGHT,
    'partlycloudy_day': WeatherCode.PARTLYCLOUDY_DAY,
    'partlycloudy_night': WeatherCode.PARTLYCLOUDY_NIGHT,
    'cloudy': WeatherCode.CLOUDY,
    'rainshowers_day': WeatherCode.RAINSHOWERS_DAY,
    'rainshowers_night': WeatherCode.RAINSHOWERS_NIGHT,
    'rain': WeatherCode.RAIN,
    'thunder': WeatherCode.THUNDER
}
```

### Block Sizes

The service provides different forecast resolutions based on how far ahead the forecast is:

```python
def get_block_size(self, hours_ahead: float) -> int:
    if hours_ahead <= 48:
        return 1    # Hourly forecasts for first 48 hours
    elif hours_ahead <= 168:
        return 6    # 6-hour blocks for days 3-7
    else:
        return 12   # 12-hour blocks beyond day 7
```

## Error Handling

### Common Errors

1. **Rate Limit Exceeded**
   ```python
   if response.status_code == 429:
       raise WeatherError(
           "MET.no rate limit exceeded",
           ErrorCode.RATE_LIMIT_EXCEEDED,
           {"retry_after": response.headers.get("Retry-After")}
       )
   ```

2. **Invalid Response Format**
   ```python
   if not data or data.get('type') != 'Feature':
       raise WeatherError(
           "Invalid API response format",
           ErrorCode.INVALID_RESPONSE,
           {"data": data}
       )
   ```

### Rate Limiting

```python
def _handle_rate_limit(self):
    now = datetime.now()
    if self._last_request_time:
        elapsed = now - self._last_request_time
        if elapsed < self._min_call_interval:
            sleep_time = (self._min_call_interval - elapsed).total_seconds()
            time.sleep(sleep_time)
    self._last_request_time = now
```

## Caching Strategy

- Cache key format: `{club}_{lat:.4f}_{lon:.4f}_{base_time}`
- Cache duration: 1 hour
- Automatic cache invalidation on API updates

```python
def _get_cache_key(self, lat: float, lon: float, club: str, base_time: datetime) -> str:
    return f"{club}_{lat:.4f}_{lon:.4f}_{base_time.strftime('%Y%m%d%H')}"
```

## Best Practices

1. **Request Optimization**
   - Cache responses for 1 hour
   - Respect rate limits (1 request/second)
   - Use appropriate block sizes
   - Include User-Agent header

2. **Error Handling**
   - Handle rate limits with backoff
   - Validate response format
   - Cache failures gracefully
   - Log detailed error information

3. **Data Processing**
   - Convert timestamps to UTC
   - Use metric units
   - Handle day/night variations
   - Process thunder probability

4. **Integration**
   - Use for Nordic region only
   - Fall back to OpenWeather if unavailable
   - Handle timezone conversions
   - Respect service terms of use 