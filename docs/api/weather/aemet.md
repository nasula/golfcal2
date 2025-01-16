# AEMET Weather Service API

## Overview

The AEMET (Agencia Estatal de Meteorología) service provides weather data for Spain and its territories through their OpenData API. It is implemented as the `IberianWeatherService` class and handles both mainland Spain and the Canary Islands.

## Features

- High-resolution forecasts for Spain and its territories
- Municipality-based weather data
- Multiple forecast ranges (hourly, 6-hourly, and daily)
- Automatic municipality lookup based on coordinates
- Day/night weather condition support
- Built-in caching for both weather data and municipality information

## Implementation

```python
class IberianWeatherService(WeatherService):
    """Service for handling weather data for Iberian region."""

    BASE_URL = "https://opendata.aemet.es/opendata/api"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal"
    
    # AEMET forecast ranges
    HOURLY_RANGE = 48    # 48 hours of hourly forecasts
    SIX_HOURLY_RANGE = 96  # Up to 96 hours (4 days) for 6-hourly
    DAILY_RANGE = 168    # Up to 168 hours (7 days) for daily
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        super().__init__(local_tz, utc_tz)
        self.config = config
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.cache = WeatherResponseCache(os.path.join(data_dir, 'weather_cache.db'))
        self.location_cache = WeatherLocationCache(os.path.join(data_dir, 'weather_locations.db'))
        
        # Rate limiting
        self._min_call_interval = timedelta(seconds=1)
        
        # API configuration
        self.headers = {
            'Accept': 'application/json',
            'api_key': config.global_config['api_keys']['weather']['aemet']
        }
```

## API Details

- **Base URL**: `https://opendata.aemet.es/opendata/api`
- **Authentication**: API key required in headers
- **Rate Limit**: Enforced with retry-after headers, minimum 1-second interval
- **Update Schedule**: Four times daily (03:00, 09:00, 15:00, 21:00 UTC)
- **Geographic Coverage**: Spain and its territories
- **Forecast Ranges**:
  - Hourly data: Next 48 hours
  - 6-hourly data: Up to 96 hours (4 days)
  - Daily data: Up to 168 hours (7 days)

## Municipality Lookup

The service automatically finds the nearest municipality to given coordinates:

1. Initialization:
   - Fetches complete municipality list from AEMET
   - Caches municipality data for 90 days
   - Includes metadata like province, region, and altitude

2. Lookup Process:
   - Uses cached municipality data
   - Calculates distances using Haversine formula
   - Returns nearest municipality with its metadata

## Weather Codes

AEMET uses a proprietary weather code system that is mapped to internal codes:

| AEMET Code | Description | Internal Code |
|------------|-------------|---------------|
| 11/11n | Clear sky | clearsky_day/night |
| 12/12n | Few clouds | fair_day/night |
| 13/13n | Variable clouds | partlycloudy_day/night |
| 14/14n | Cloudy | cloudy |
| 15/15n | Very cloudy | cloudy |
| 16/16n | Overcast | cloudy |
| 23/23n | Rain | rain |
| 24/24n | Snow | snow |
| 25/25n | Sleet | sleet |
| 33/33n | Light rain | lightrain |
| 34/34n | Light snow | lightsnow |
| 43/43n | Heavy rain | heavyrain |
| 44/44n | Heavy snow | heavysnow |
| 51/51n | Rain showers | rainshowers |
| 52/52n | Snow showers | snowshowers |
| 81/81n | Thunder | thunder |

Note: Suffix 'n' indicates night conditions (20:00-06:00).

## Error Handling

The service implements comprehensive error handling:

1. Service Errors
   - Network connectivity issues (`requests.RequestException`)
   - Authentication errors (invalid API key)
   - Rate limiting (429 responses with retry-after)
   - Invalid coordinates or municipality codes
   - Parse errors (JSON format)
   - Missing data fields

2. Recovery Strategies
   - Automatic retries with minimum interval
   - Cache utilization for both weather and location data
   - Graceful degradation for partial data
   - Detailed error logging with context

## Caching

The service implements two types of caching:

1. Weather Cache:
   - Location: `data/weather_cache.db`
   - Implementation: `WeatherResponseCache`
   - Cache duration: Based on AEMET update schedule
   - Cache key format: `f"aemet_{municipality_code}_{start_time.isoformat()}_{end_time.isoformat()}"`

2. Municipality Cache:
   - Location: `data/weather_locations.db`
   - Implementation: `WeatherLocationCache`
   - Cache duration: 90 days
   - Includes full municipality metadata

## Data Mapping

### Units

All data is automatically converted to standard units:
- Temperature: Celsius
- Wind Speed: m/s (converted from km/h)
- Precipitation: mm/h
- Direction: Degrees (0-360)
- Probabilities: 0-100%

## Usage Example

```python
service = IberianWeatherService(local_tz, utc_tz, config)
weather = service.get_weather(
    lat=40.4168,  # Madrid
    lon=-3.7038,
    start_time=datetime(...),
    end_time=datetime(...)
)
```

## Logging

The service implements detailed logging with context:
```python
self.debug("Looking up in cache", location=location, time=time.isoformat())
self.info("Cache hit", location=location, time=aligned_time.isoformat())
self.error("Failed to fetch forecast", exc_info=e, coords=(lat, lon))
```

## Configuration

Example configuration in `config.yaml`:
```yaml
weather:
  providers:
    aemet:
      api_key: "your-api-key"
      timeout: 10
      cache_duration: 3600  # 1 hour for short-term forecasts
```

## Related Documentation

- [AEMET OpenData API Documentation](https://opendata.aemet.es/centrodedescargas/inicio)
- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md)
``` 