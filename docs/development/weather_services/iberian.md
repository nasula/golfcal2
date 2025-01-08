# Iberian Weather Service

## Overview

The Iberian Weather Service provides weather forecasts for Spain through the AEMET (Agencia Estatal de Meteorología) OpenData API. The service is implemented in the `IberianWeatherService` class and handles both mainland Spain and the Canary Islands.

## Configuration

```python
class IberianWeatherService(WeatherService):
    """Service for handling weather data for Iberian region."""
    
    BASE_URL = "https://opendata.aemet.es/opendata/api"
    USER_AGENT = "GolfCal/2.0 github.com/jahonen/golfcal (jarkko.ahonen@iki.fi)"
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        super().__init__(local_tz, utc_tz)
        self.api_key = config.global_config['api_keys']['weather']['aemet']
        self.endpoint = self.BASE_URL
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': self.USER_AGENT,
            'api_key': self.api_key
        }
        self.db = WeatherDatabase('iberian_weather', IBERIAN_SCHEMA)
        self.location_cache = WeatherLocationCache(config)
        self._min_call_interval = timedelta(seconds=1)
```

## Geographic Coverage
- Mainland Spain
  - Latitude: 36.0°N to 43.8°N
  - Longitude: 9.3°W to 3.3°E
- Canary Islands
  - Latitude: 27.6°N to 29.4°N
  - Longitude: 18.2°W to 13.4°W

## Features

### API Details
- Uses AEMET OpenData API
- Requires API key in headers
- Rate limited to 1 request per second
- Municipality-based forecasts
- Returns JSON format data

### Forecast Details
- Up to 7 days of forecasts
- Hourly resolution
- Timezone handling:
  - Mainland Spain: Europe/Madrid
  - Canary Islands: Atlantic/Canary
- Altitude-based adjustments

### Data Processing
- Automatic timezone conversion
- Unit standardization:
  - Temperature in Celsius
  - Wind speed conversion from km/h to m/s
  - Precipitation in mm
- Thunder probability calculation:
  - Based on weather description
  - 50% probability when "tormenta" is in description
  - Additional probability from weather codes

### Municipality Lookup
- Uses location cache for municipality mapping
- Haversine distance calculation
- Handles both mainland and island locations
- Automatic timezone selection based on longitude

### Caching System
- SQLite-based persistent storage
- Municipality-based caching
- Cache fields:
  - air_temperature
  - precipitation_amount
  - wind_speed
  - wind_from_direction
  - probability_of_precipitation
  - probability_of_thunder
  - summary_code
  - expires

### Error Handling
- Rate limit detection (429 responses)
- Invalid response format recovery
- Network timeout handling (10 seconds)
- Municipality not found handling
- Data validation and parsing errors
- Detailed logging with context

## API Response Format

### Example Response Structure
```json
{
    "prediccion": {
        "dia": [
            {
                "fecha": "2024-01-20T00:00:00",
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
                "vientoAndRachaMax": [
                    {
                        "periodo": "0",
                        "direccion": ["N"],
                        "velocidad": ["15"]
                    }
                ],
                "estadoCielo": [
                    {
                        "periodo": "0",
                        "value": "11n",
                        "descripcion": "Despejado"
                    }
                ]
            }
        ]
    }
}
```

## Weather Code Mapping

### AEMET to Standard Codes
```python
code_map = {
    # Clear conditions
    '11': 'clearsky_day' if is_day else 'clearsky_night',
    '12': 'fair_day' if is_day else 'fair_night',
    '13': 'partlycloudy_day' if is_day else 'partlycloudy_night',
    '14': 'cloudy',
    '15': 'cloudy',
    '16': 'cloudy',
    '17': 'partlycloudy_day' if is_day else 'partlycloudy_night',
    
    # Rain
    '23': 'lightrainshowers_day' if is_day else 'lightrainshowers_night',
    '24': 'lightrain',
    '25': 'rain',
    '26': 'rain',
    
    # Snow
    '33': 'lightsnowshowers_day' if is_day else 'lightsnowshowers_night',
    '34': 'lightsnow',
    '35': 'snow',
    '36': 'snow',
    
    # Mixed precipitation
    '43': 'sleetshowers_day' if is_day else 'sleetshowers_night',
    '44': 'lightsleet',
    '45': 'sleet',
    '46': 'sleet',
    
    # Thunderstorms
    '51': 'rainandthunder',
    '52': 'rainandthunder',
    '53': 'heavyrainandthunder',
    '54': 'heavyrainandthunder',
    
    # Snow with thunder
    '61': 'snowandthunder',
    '62': 'snowandthunder',
    '63': 'heavysnowandthunder',
    '64': 'heavysnowandthunder',
    
    # Rain and thunder
    '71': 'rainandthunder',
    '72': 'rainandthunder',
    '73': 'heavyrainandthunder',
    '74': 'heavyrainandthunder'
}
```

## Error Types

- `WeatherError`: Base class for weather-related errors
- `APITimeoutError`: Request timeout (10 seconds)
- `APIRateLimitError`: Rate limit exceeded (429 response)
- `APIResponseError`: Invalid response format
- `APIError`: General API errors

## Best Practices

1. **Rate Limiting**
   - Respect 1-second interval between requests
   - Use municipality caching to minimize API calls
   - Handle 429 responses with exponential backoff
   - Implement request queuing for high-load scenarios

2. **Data Validation**
   - Validate coordinates against coverage area
   - Check timestamp ranges (max 7 days ahead)
   - Verify municipality data completeness
   - Handle special cases like "Ip" (trace) precipitation
   - Validate numeric ranges for all weather parameters

3. **Error Handling**
   - Implement proper retries with backoff
   - Log errors with correlation IDs
   - Handle timezone conversion edge cases
   - Validate API response format
   - Graceful degradation on service failures

4. **Caching**
   - Cache municipality data
   - Implement forecast caching with proper expiry
   - Handle cache misses gracefully
   - Store all forecast data, not just requested range
   - Validate cached data before use

5. **Logging**
   - Use correlation IDs for request tracking
   - Log API request details (URL, params)
   - Log municipality lookup results
   - Log data processing steps
   - Include context in error logs

## Implementation Notes

1. **Municipality Handling**
   - Remove 'id' prefix from municipality codes
   - Format codes to 5 digits with leading zeros
   - Cache municipality lookup results
   - Handle special cases for islands

2. **Time Handling**
   - Convert local times to UTC
   - Handle daylight saving time
   - Use proper timezone for location
   - Process 6-hour blocks for probabilities

3. **Data Processing**
   - Convert units to standard format
   - Handle missing or invalid data
   - Calculate derived values
   - Validate output ranges
``` 