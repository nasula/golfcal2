# Iberian Weather Service (AEMET) API

## Overview

The Iberian Weather Service uses AEMET's (Agencia Estatal de Meteorología) API to provide weather forecasts for Spain. It handles both mainland Spain and the Canary Islands, with municipality-based forecasts.

## API Details

- **Base URL**: `https://opendata.aemet.es/opendata/api`
- **Documentation**: [AEMET OpenData API](https://opendata.aemet.es/centrodedescargas/inicio)
- **Authentication**: API key required
- **Rate Limit**: 1 request per second
- **Update Frequency**: Multiple times per day
- **Geographic Coverage**: Spain (-7°E to 5°E)

## Implementation

```python
class IberianWeatherService(WeatherService):
    BASE_URL = "https://opendata.aemet.es/opendata/api"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        super().__init__(local_tz, utc_tz)
        self.api_key = config.global_config['api_keys']['weather']['aemet']
        self.headers = {
            'Accept': 'application/json',
            'api_key': self.api_key
        }
        self.db = WeatherDatabase('iberian_weather', IBERIAN_SCHEMA)
```

## Request Flow

### 1. Municipality Lookup

```python
def _get_municipality(self, lat: float, lon: float) -> str:
    # Try cache first
    cached = self.location_cache.get_municipality(lat, lon)
    if cached:
        return cached['code']
        
    # Fetch from API if not cached
    url = f"{self.BASE_URL}/maestro/municipios"
    response = requests.get(url, headers=self.headers)
    municipalities = response.json()
    
    # Find nearest municipality
    nearest = min(
        municipalities,
        key=lambda m: self._haversine_distance(
            lat, lon,
            float(m['latitud_dec']),
            float(m['longitud_dec'])
        )
    )
    
    # Cache for future use
    self.location_cache.cache_municipality(
        lat=lat,
        lon=lon,
        municipality_code=nearest['id'],
        name=nearest['nombre']
    )
    
    return nearest['id']
```

### 2. Forecast Retrieval

```python
def _get_forecast(self, municipality_code: str) -> Dict:
    # First request gets the data URL
    forecast_url = f"{self.BASE_URL}/prediccion/especifica/municipio/horaria/{municipality_code}"
    response = requests.get(forecast_url, headers=self.headers)
    data_info = response.json()
    
    # Second request gets the actual forecast data
    data_url = data_info['datos']
    data_response = requests.get(data_url, headers=self.headers)
    return data_response.json()
```

## Response Format

```json
{
    "origen": {
        "productor": "Agencia Estatal de Meteorología - AEMET",
        "web": "http://www.aemet.es",
        "enlace": "http://www.aemet.es/es/eltiempo/prediccion/municipios/madrid-id28079",
        "language": "es",
        "copyright": "© AEMET. Autorizado el uso de la información y su reproducción citando a AEMET como autora de la misma.",
        "notaLegal": "http://www.aemet.es/es/nota_legal"
    },
    "elaborado": "2024-01-09T13:00:00",
    "nombre": "Madrid",
    "provincia": "Madrid",
    "prediccion": {
        "dia": [
            {
                "fecha": "2024-01-09",
                "temperatura": [
                    {
                        "periodo": "0",
                        "value": "12.8"
                    }
                ],
                "precipitacion": [
                    {
                        "periodo": "0",
                        "value": "0.2"
                    }
                ],
                "probPrecipitacion": [
                    {
                        "periodo": "0006",
                        "value": "30"
                    }
                ],
                "estadoCielo": [
                    {
                        "periodo": "0",
                        "value": "11n",
                        "descripcion": "Despejado"
                    }
                ],
                "viento": [
                    {
                        "periodo": "0",
                        "direccion": "N",
                        "velocidad": 15
                    }
                ],
                "racha": [
                    {
                        "periodo": "0",
                        "value": 25
                    }
                ]
            }
        ]
    }
}
```

## Weather Data Mapping

### Weather Codes

AEMET uses numeric codes with day/night variants:

```python
def _map_aemet_code(self, code: str, hour: int) -> str:
    is_day = 6 <= hour <= 20
    base_code = code.rstrip('n')  # Strip night indicator
    
    code_map = {
        '11': 'clearsky_day' if is_day else 'clearsky_night',
        '12': 'fair_day' if is_day else 'fair_night',
        '13': 'partlycloudy_day' if is_day else 'partlycloudy_night',
        '14': 'cloudy',
        '15': 'cloudy',
        '23': 'lightrainshowers_day' if is_day else 'lightrainshowers_night',
        '24': 'lightrain',
        '25': 'rain',
        '26': 'rain',
        '51': 'rainandthunder',
        '52': 'rainandthunder',
        '53': 'heavyrainandthunder',
        '54': 'heavyrainandthunder'
    }
    
    return code_map.get(base_code, 'cloudy')
```

### Block Sizes

```python
def get_block_size(self, hours_ahead: float) -> int:
    """Get forecast block size based on hours ahead.
    
    AEMET provides:
    - Hourly forecasts for first 48 hours
    - 3-hour blocks beyond that
    """
    if hours_ahead <= 48:
        return 1
    return 3
```

## Error Handling

### Common Errors

1. **API Key Error**
   ```python
   if response.status_code == 401:
       raise WeatherError(
           "Invalid AEMET API key",
           ErrorCode.AUTH_ERROR,
           {"api_key": self.api_key}
       )
   ```

2. **Municipality Not Found**
   ```python
   if not municipalities:
       raise WeatherError(
           "No municipalities found",
           ErrorCode.INVALID_RESPONSE,
           {"lat": lat, "lon": lon}
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

- Municipality cache: Persistent storage of municipality codes
- Weather cache: 6-hour duration with automatic invalidation
- Cache key format: `{municipality_code}_{base_time}`

```python
def _get_cache_key(self, municipality_code: str, base_time: datetime) -> str:
    return f"{municipality_code}_{base_time.strftime('%Y%m%d%H')}"
```

## Best Practices

1. **Request Optimization**
   - Cache municipality codes
   - Use appropriate block sizes
   - Respect rate limits
   - Batch requests when possible

2. **Error Handling**
   - Validate API key
   - Handle municipality lookup failures
   - Implement request retries
   - Log all API interactions

3. **Data Processing**
   - Convert timestamps to UTC
   - Handle day/night variations
   - Process thunder probability
   - Map weather codes correctly

4. **Integration**
   - Use for Spanish locations only
   - Fall back to OpenWeather if needed
   - Handle timezone differences
   - Respect AEMET terms of use

## Attribution Requirements

1. **Required Headers**
   - Include API key in headers
   - Use appropriate User-Agent

2. **Legal Requirements**
   - Cite AEMET as data source
   - Include copyright notice
   - Link to AEMET website
   - Follow usage guidelines 