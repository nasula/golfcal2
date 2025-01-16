# AEMET Weather Service API

## Overview

AEMET (Agencia Estatal de Meteorología) provides weather forecasts for Spain and its territories. In GolfCal2, it serves as the primary weather service for the Iberian region, with OpenMeteo as a fallback.

## API Details

- **Base URL**: `https://opendata.aemet.es/opendata/api`
- **Authentication**: API key required
- **Rate Limit**: 30 requests/minute
- **Update Frequency**: 4 times daily
- **Forecast Range**:
  - 0-48 hours: Hourly forecasts
  - 2-4 days: 6-hour blocks
  - 5-7 days: Daily forecasts

## Authentication

The service requires an API key in the request headers:
```python
headers = {
    'Accept': 'application/json',
    'api_key': 'your-api-key'
}
```

## Coverage Area

The service covers:
- Spanish mainland
- Balearic Islands
- Canary Islands
- Ceuta and Melilla

## Endpoints

### Get Municipality Forecast

```
GET /prediccion/especifica/municipio/{municipio}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| municipio | string | Yes | Municipality code (5 digits) |

#### Example Request

```
GET /prediccion/especifica/municipio/28079
```

#### Response Format

The API uses a two-step process:
1. Initial request returns a data URL
2. Second request fetches actual forecast data

```json
// Step 1 Response
{
    "descripcion": "exito",
    "estado": 200,
    "datos": "https://opendata.aemet.es/opendata/sh/...",
    "metadatos": "https://opendata.aemet.es/opendata/sh/..."
}

// Step 2 Response (Forecast Data)
{
    "elaborado": "2024-01-23T10:00:00",
    "nombre": "Madrid",
    "provincia": "Madrid",
    "prediccion": {
        "dia": [
            {
                "fecha": "2024-01-23",
                "temperatura": {
                    "maxima": 25,
                    "minima": 15,
                    "dato": [
                        {
                            "hora": 6,
                            "value": 16
                        }
                    ]
                },
                "precipitacion": {
                    "probability": [
                        {
                            "period": "00-24",
                            "value": 0
                        }
                    ],
                    "value": 0
                },
                "viento": [
                    {
                        "direccion": "N",
                        "velocidad": 15
                    }
                ],
                "estadoCielo": [
                    {
                        "periodo": "00-24",
                        "descripcion": "Despejado",
                        "value": "11"
                    }
                ]
            }
        ]
    }
}
```

## Implementation

The service is implemented in `services/iberian_weather_service.py`:

```python
class IberianWeatherService(WeatherService):
    BASE_URL = "https://opendata.aemet.es/opendata/api"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal"
    
    # AEMET forecast ranges
    HOURLY_RANGE = 48    # 48 hours of hourly forecasts
    SIX_HOURLY_RANGE = 96  # Up to 96 hours (4 days) for 6-hourly
    DAILY_RANGE = 168    # Up to 168 hours (7 days) for daily
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        super().__init__(local_tz, utc_tz)
        self.headers = {
            'Accept': 'application/json',
            'api_key': config.global_config['api_keys']['weather']['aemet']
        }
```

## Weather Codes

AEMET uses a proprietary weather code system that is mapped to standardized WMO codes:

| AEMET Code | Description | WMO Code |
|------------|-------------|----------|
| 11 | Despejado (Clear) | 0 |
| 12-14 | Poco nuboso (Slightly cloudy) | 1 |
| 15-17 | Nuboso (Cloudy) | 2 |
| 18 | Cubierto (Overcast) | 3 |
| 71 | Niebla (Fog) | 45 |
| 24 | Lluvia débil (Light rain) | 61 |
| 25 | Lluvia (Rain) | 63 |
| 26 | Lluvia fuerte (Heavy rain) | 65 |
| 33 | Nieve débil (Light snow) | 71 |
| 34 | Nieve (Snow) | 73 |
| 35 | Nieve fuerte (Heavy snow) | 75 |
| 51-53 | Tormenta (Thunderstorm) | 95 |
| 57 | Tormenta con granizo (Thunderstorm with hail) | 96 |

## Error Handling

The service implements comprehensive error handling:

1. Service Errors
   - Network connectivity issues
   - Invalid API key
   - Rate limiting
   - Municipality not found
   - Parse errors

2. Recovery Strategies
   - Automatic fallback to OpenMeteo
   - Cache utilization for recent requests
   - Rate limit tracking
   - Municipality list caching

## Caching

Weather data is cached with the following rules:

1. Cache Duration:
   - Short-term forecasts (0-48h): 1 hour
   - Medium-term forecasts (2-4d): 3 hours
   - Long-term forecasts (5-7d): 6 hours

2. Cache Keys:
   ```python
   f"aemet_{municipality_code}_{start_time.isoformat()}_{end_time.isoformat()}"
   ```

## Data Mapping

### Units

All data is converted to standard units:
- Temperature: Celsius
- Wind Speed: m/s (converted from km/h)
- Precipitation: mm/h
- Direction: Compass points (N, NE, E, etc.)

## Usage Example

```python
service = IberianWeatherService(local_tz, utc_tz, config)
weather = service.get_weather(
    lat=40.4168,
    lon=-3.7038,
    start_time=datetime(...),
    end_time=datetime(...)
)
```

## Rate Limiting

Rate limiting is implemented using a simple counter:
```python
rate_limiter = RateLimiter(
    max_calls=30,
    time_window=60  # 60 seconds
)
```

## Logging

The service implements detailed logging:
```python
self.debug("Cache hit for AEMET forecast", coords=(lat, lon))
self.info("Fetching new forecast", coords=(lat, lon))
self.error("Failed to fetch AEMET forecast", exc_info=e)
```

## Configuration

Example configuration in `config.yaml`:
```yaml
weather:
  providers:
    aemet:
      api_key: "your-key"
      timeout: 10
      cache_duration: 3600
```

## Future Improvements

1. Cache municipality list for faster lookups
2. Implement forecast caching
3. Add IPMA support for Portugal
4. Better thunder probability calculation
5. More granular error recovery

## Related Documentation

- [AEMET OpenData API Documentation](https://opendata.aemet.es/centrodedescargas/inicio)
- [Weather Service Implementation](../../services/weather/README.md)
- [Weather Data Models](../../services/weather/data-models.md)
``` 