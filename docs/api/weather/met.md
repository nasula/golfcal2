# MET.no Weather Service API

## Overview

The Norwegian Meteorological Institute (MET.no) provides high-accuracy weather forecasts for the Nordic region. This service is used as the primary weather data provider for locations within 55°N-72°N and 4°E-32°E.

## API Details

- **Base URL**: `https://api.met.no/weatherapi/locationforecast/2.0/complete`
- **Authentication**: User-Agent required (no API key)
- **Rate Limit**: 1 request/second
- **Update Frequency**: Hourly
- **Forecast Range**: 
  - 0-48 hours: Hourly forecasts
  - 2-9 days: 6-hour blocks

## Authentication

The service requires only a User-Agent header:
```python
headers = {
    'User-Agent': 'golfcal2/1.0 https://github.com/jahonen/golfcal2'
}
```

## Endpoints

### Get Location Forecast

```
GET /weatherapi/locationforecast/2.0/complete
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| lat | float | Yes | Latitude (-90 to 90) |
| lon | float | Yes | Longitude (-180 to 180) |

#### Response Format

```json
{
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [lon, lat, altitude]
    },
    "properties": {
        "meta": {
            "updated_at": "2024-01-23T10:00:00Z",
            "units": {...}
        },
        "timeseries": [
            {
                "time": "2024-01-23T10:00:00Z",
                "data": {
                    "instant": {
                        "details": {
                            "air_temperature": 20.5,
                            "precipitation_rate": 0.0,
                            "relative_humidity": 82.3,
                            "wind_from_direction": 180.0,
                            "wind_speed": 5.2
                        }
                    },
                    "next_1_hours": {
                        "summary": {
                            "symbol_code": "cloudy"
                        },
                        "details": {
                            "precipitation_amount": 0.0
                        }
                    }
                }
            }
        ]
    }
}
```

## Implementation

The service is implemented in `services/met_weather_service.py`:

```python
class MetWeatherService(WeatherService):
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        # Check cache first
        cached_response = self.cache.get_response(
            service_type='met',
            latitude=lat,
            longitude=lon,
            start_time=start_time,
            end_time=end_time
        )
        
        # Fetch and cache if needed
        response = self._fetch_forecast(lat, lon, start_time, end_time)
        if response:
            self.cache.store_response(
                service_type='met',
                latitude=lat,
                longitude=lon,
                response_data=response,
                forecast_start=start_time,
                forecast_end=end_time,
                expires=datetime.now(self.utc_tz) + timedelta(hours=6)
            )
```

## Weather Codes

MET.no uses a proprietary weather code system that is mapped to standardized WMO codes:

| MET Code | Description | WMO Code |
|----------|-------------|----------|
| clearsky | Clear sky | 0 |
| cloudy | Cloudy | 3 |
| fair | Fair | 1 |
| fog | Fog | 45 |
| heavyrain | Heavy rain | 63 |
| heavysnow | Heavy snow | 73 |
| lightrain | Light rain | 61 |
| lightsnow | Light snow | 71 |
| partlycloudy | Partly cloudy | 2 |
| rain | Rain | 62 |
| rainshowers | Rain showers | 80 |
| sleet | Sleet | 68 |
| sleetshowers | Sleet showers | 69 |
| snow | Snow | 72 |
| snowshowers | Snow showers | 85 |
| thunder | Thunderstorm | 95 |

## Data Structure

The service returns weather data in a standardized format:

```python
@dataclass
class WeatherData:
    elaboration_time: datetime    # Forecast time
    block_duration: timedelta     # Duration of forecast block
    temperature: float           # Celsius
    precipitation: float        # mm/h
    wind_speed: float          # m/s
    wind_direction: float      # Degrees (0-360)
    precipitation_probability: float  # 0-100%
    thunder_probability: float  # Always 0.0 (not provided by MET)
    weather_code: str          # Default: 'cloudy'
    weather_description: str   # Empty string (not provided by MET)
```

## Caching

Weather data is cached with the following rules:

1. Cache Duration: 6 hours for all forecasts
2. Cache Keys:
   ```python
   f"met_{lat:.4f}_{lon:.4f}_{start_time.isoformat()}_{end_time.isoformat()}"
   ```

## Error Handling

The service implements comprehensive error handling:

1. Service Errors
   - Network connectivity issues (`requests.RequestException`)
   - Rate limiting (429 responses)
   - Invalid coordinates
   - Parse errors (JSON format)
   - Missing data fields

2. Recovery Strategies
   - Automatic fallback to OpenMeteo
   - Cache utilization for recent requests
   - Exponential backoff for rate limits

## Configuration

Example configuration in `config.yaml`:
```yaml
weather:
  providers:
    met:
      user_agent: "golfcal2/1.0 https://github.com/jahonen/golfcal2"
      timeout: 10
```

## Data Mapping

### Weather Codes

MET.no uses a proprietary weather code system that is mapped to standardized WMO codes:

| MET Code | Description | WMO Code |
|----------|-------------|----------|
| clearsky | Clear sky | 0 |
| cloudy | Cloudy | 3 |
| fair | Fair | 1 |
| fog | Fog | 45 |
| heavyrain | Heavy rain | 63 |
| heavysnow | Heavy snow | 73 |
| lightrain | Light rain | 61 |
| lightsnow | Light snow | 71 |
| partlycloudy | Partly cloudy | 2 |
| rain | Rain | 62 |
| rainshowers | Rain showers | 80 |
| sleet | Sleet | 68 |
| sleetshowers | Sleet showers | 69 |
| snow | Snow | 72 |
| snowshowers | Snow showers | 85 |
| thunder | Thunderstorm | 95 |

### Units

All data is converted to standard units:
- Temperature: Celsius
- Wind Speed: m/s
- Precipitation: mm/h
- Direction: Compass points (N, NE, E, etc.)

## Usage Example

```python
service = MetWeatherService(local_tz, utc_tz, config)
weather = service.get_weather(
    lat=60.1699,
    lon=24.9384,
    start_time=datetime(...),
    end_time=datetime(...)
)
```

## Logging

The service implements detailed logging:
```python
self.debug("Cache hit for MET forecast", coords=(lat, lon))
self.info("Fetching new forecast", coords=(lat, lon))
self.error("Failed to fetch MET forecast", exc_info=e)
```

## Related Documentation

- [MET.no API Documentation](https://api.met.no/weatherapi/locationforecast/2.0/documentation)
- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md) 